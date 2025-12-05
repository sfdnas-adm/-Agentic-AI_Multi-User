# review_bot/main.py
import asyncio
import logging
import os

from fastapi import FastAPI, Request
from pydantic import BaseModel

from review_bot.services.github_service import GitHubService
from review_bot.services.langgraph_service import ReviewWorkflow
from review_bot.services.memory_service import PostgresMemoryService

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Pydantic Schema for incoming GitLab MR data (minimal) ---
# This is what we expect from the webhook payload


class GitHubPullRequest(BaseModel):
    action: str
    number: int
    pull_request: dict
    repository: dict


class GitHubComment(BaseModel):
    action: str
    issue: dict
    comment: dict
    repository: dict


# --- The core review processing function (TBD in Phase 2) ---
# We make this function async and separate it from the main request handler


# Initialize services globally with error handling
github_tool = None
review_workflow = None
memory_service = None

github_tool = GitHubService()
logger.info("GitHub service initialized")

review_workflow = ReviewWorkflow()
logger.info("Review workflow initialized")

# Try to initialize memory service, but don't crash if DB unavailable
memory_service = None
if os.getenv("DATABASE_URL") or os.getenv("DB_HOST"):
    memory_service = PostgresMemoryService()
    logger.info("Memory service initialized")
else:
    logger.warning("No database configuration found - memory service disabled")


async def process_review_workflow(project_id: int, pr_number: int):
    if not github_tool:
        logger.error("GitHub service not initialized")
        return
    if not review_workflow:
        logger.error("Review workflow not initialized")
        return

    logger.info("STARTING review for PR #%d", pr_number)

    # --- 1. Use the new Tool to fetch the code diff ---
    diff_text = github_tool.fetch_pr_diff(pr_number)
    if not diff_text or diff_text.startswith("Error fetching"):
        logger.error("Failed to fetch diff for PR #%d", pr_number)
        return
    logger.info("Successfully fetched diff (Size: %d characters)", len(diff_text))

    # --- 2. Run LangGraph workflow ---
    logger.info("Starting LangGraph workflow for PR #%d", pr_number)
    result = review_workflow.run_review(project_id, pr_number, diff_text)

    logger.info("Workflow result keys: %s", list(result.keys()))

    if result.get("error_message"):
        logger.error("Review workflow error: %s", result["error_message"])
    else:
        # Save context for potential human feedback
        final_review = result.get("judge_output", "")
        logger.info(
            "Final review length: %d characters",
            len(final_review) if final_review else 0,
        )

        if memory_service:
            success = memory_service.save_review_context(
                project_id, pr_number, diff_text, final_review
            )
            logger.info("Saved review context: %s", success)

    logger.info("COMPLETED review for PR #%d", pr_number)


app = FastAPI(title="AI Code Review Bot")


@app.post("/webhook/pull_request")
async def handle_pull_request(pr_event: GitHubPullRequest, request: Request):
    # 1. Check for the correct action
    if pr_event.action not in ["opened", "reopened", "synchronize"]:
        return {
            "status": "ignored",
            "reason": f"Not a relevant PR action: {pr_event.action}",
        }

    pr_number = pr_event.number
    repo_name = pr_event.repository.get("name")

    # Check if repository is allowed
    allowed_repo = os.getenv("GITHUB_REPO", "-Agentic-AI_Multi-User")
    if repo_name != allowed_repo:
        return {
            "status": "ignored",
            "reason": f"Repository {repo_name} not allowed. Only {allowed_repo} is supported.",
        }

    # Check if services are ready
    if not github_tool or not review_workflow:
        return {"status": "error", "reason": "Services not initialized"}

    logger.info("Received PR Webhook: Repository %s, PR #%d", repo_name, pr_number)

    # 2. Crucial: Respond immediately and process heavy work asynchronously
    asyncio.create_task(
        process_review_workflow(0, pr_number)
    )  # Use 0 as dummy project_id

    return {
        "status": "accepted",
        "message": f"Processing PR #{pr_number} asynchronously.",
    }


async def process_human_feedback(project_id: int, pr_number: int, human_comment: str):
    """Process human feedback on AI review"""
    if not memory_service:
        logger.error("Memory service not initialized")
        return
    if not review_workflow:
        logger.error("Review workflow not initialized")
        return

    logger.info(
        "Processing human feedback for PR #%d (comment length: %d)",
        pr_number,
        len(human_comment),
    )

    # Load context from PostgreSQL
    diff_text, ai_review = memory_service.load_review_context(project_id, pr_number)

    if not diff_text:
        logger.warning(
            "No previous context found for PR #%d. Ignoring comment.", pr_number
        )
        return

    # Run justification workflow
    result = review_workflow.run_justification(
        project_id, pr_number, diff_text, ai_review, human_comment
    )
    if result.get("error_message"):
        logger.error("Justification workflow error: %s", result["error_message"])

    logger.info("COMPLETED justification for PR #%d", pr_number)


@app.post("/webhook/comment")
async def handle_comment(comment_event: GitHubComment, request: Request):
    """Handle GitHub comment webhook for human feedback"""
    if comment_event.action != "created":
        return {"status": "ignored", "reason": "Not a comment creation event"}

    pr_number = comment_event.issue.get("number")
    repo_name = comment_event.repository.get("name")
    comment_body = comment_event.comment.get("body", "")

    # Check if repository is allowed
    allowed_repo = os.getenv("GITHUB_REPO", "-Agentic-AI_Multi-User")
    if repo_name != allowed_repo:
        return {
            "status": "ignored",
            "reason": f"Repository {repo_name} not allowed. Only {allowed_repo} is supported.",
        }

    # Check if services are ready
    if not memory_service or not review_workflow:
        return {"status": "error", "reason": "Services not initialized"}

    logger.info("Received comment webhook: Repository %s, PR #%d", repo_name, pr_number)

    # Process feedback asynchronously
    asyncio.create_task(process_human_feedback(0, pr_number, comment_body))

    return {"status": "accepted", "message": f"Processing feedback for PR #{pr_number}"}


@app.get("/")
def health_check():
    services_status = {
        "github_service": github_tool is not None,
        "review_workflow": review_workflow is not None,
        "memory_service": memory_service is not None,
        "database_connection": memory_service.health_check()
        if memory_service
        else False,
    }

    all_ready = all(services_status.values())

    return {
        "status": "ok" if all_ready else "partial",
        "service": "AI Code Review Bot",
        "services": services_status,
    }
