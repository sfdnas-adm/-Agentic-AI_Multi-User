# review_bot/main.py
import asyncio
import logging
import os

from fastapi import FastAPI, Request
from pydantic import BaseModel

from review_bot.services.gitlab_service import GitHubService
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
gitlab_tool = None
review_workflow = None
memory_service = None

try:
    github_tool = GitHubService()
    logger.info("GitHub service initialized")
except Exception as e:
    logger.error(f"Failed to initialize GitHub service: {e}")

try:
    review_workflow = ReviewWorkflow()
    logger.info("Review workflow initialized")
except Exception as e:
    logger.error(f"Failed to initialize review workflow: {e}")

try:
    memory_service = PostgresMemoryService()
    logger.info("Memory service initialized")
except Exception as e:
    logger.error(f"Failed to initialize memory service: {e}")


async def process_review_workflow(project_id: int, mr_iid: int):
    if not github_tool or not review_workflow:
        logger.error("Services not initialized properly")
        return

    logger.info(f"STARTING review for MR !{mr_iid} in Project {project_id}...")

    # --- 1. Use the new Tool to fetch the code diff ---
    diff_text = github_tool.fetch_pr_diff(
        mr_iid
    )  # GitHub uses PR numbers, not project_id

    if "Error" in diff_text:
        logger.error(f"Failed to fetch diff for MR !{mr_iid}: {diff_text}")
        return

    logger.info(f"Successfully fetched diff (Size: {len(diff_text)} characters).")

    # --- 2. Run LangGraph workflow ---
    try:
        result = review_workflow.run_review(project_id, mr_iid, diff_text)
        if result.get("error_message"):
            logger.error(f"Review workflow error: {result['error_message']}")
        else:
            # Save context for potential human feedback
            final_review = result.get("judge_output", "")
            if memory_service:
                memory_service.save_review_context(
                    project_id, mr_iid, diff_text, final_review
                )
    except Exception as e:
        logger.error(f"Review workflow failed: {e}")

    logger.info(f"COMPLETED review for MR !{mr_iid}.")


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

    logger.info(f"Received PR Webhook: Repository {repo_name}, PR #{pr_number}")

    # 2. Crucial: Respond immediately and process heavy work asynchronously
    asyncio.create_task(
        process_review_workflow(0, pr_number)
    )  # Use 0 as dummy project_id

    return {
        "status": "accepted",
        "message": f"Processing PR #{pr_number} asynchronously.",
    }


async def process_human_feedback(project_id: int, mr_iid: int, human_comment: str):
    """Process human feedback on AI review"""
    if not memory_service or not review_workflow:
        logger.error("Services not initialized properly")
        return

    logger.info(f"Processing human feedback for MR !{mr_iid}")

    # Load context from PostgreSQL
    diff_text, ai_review = memory_service.load_review_context(project_id, mr_iid)

    if not diff_text:
        logger.warning(f"No previous context found for MR !{mr_iid}. Ignoring comment.")
        return

    try:
        # Run justification workflow
        result = review_workflow.run_justification(
            project_id, mr_iid, diff_text, ai_review, human_comment
        )
        if result.get("error_message"):
            logger.error(f"Justification workflow error: {result['error_message']}")
    except Exception as e:
        logger.error(f"Justification workflow failed: {e}")

    logger.info(f"COMPLETED justification for MR !{mr_iid}")


@app.post("/webhook/comment")
async def handle_comment(comment_event: GitHubComment, request: Request):
    """Handle GitLab comment webhook for human feedback"""
    if (
        comment_event.object_kind != "note"
        or comment_event.object_attributes.get("noteable_type") != "MergeRequest"
    ):
        return {"status": "ignored", "reason": "Not a MR comment event"}

    mr_iid = comment_event.merge_request.get("iid")
    project_id = comment_event.project_id
    comment_body = comment_event.object_attributes.get("note", "")

    # Check if project is allowed
    allowed_project_id = int(os.getenv("ALLOWED_PROJECT_ID", "8462"))
    if project_id != allowed_project_id:
        return {
            "status": "ignored",
            "reason": f"Project {project_id} not allowed. Only project {allowed_project_id} is supported.",
        }

    # Check if services are ready
    if not memory_service or not review_workflow:
        return {"status": "error", "reason": "Services not initialized"}

    logger.info(f"Received comment webhook: Project {project_id}, MR !{mr_iid}")

    # Process feedback asynchronously
    asyncio.create_task(process_human_feedback(project_id, mr_iid, comment_body))

    return {"status": "accepted", "message": f"Processing feedback for MR !{mr_iid}"}


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
