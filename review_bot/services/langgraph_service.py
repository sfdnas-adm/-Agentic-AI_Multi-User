import logging
import os
from typing import Any

from langgraph.graph import END, START, StateGraph

from review_bot.llm_clients.base_client import GeminiClient
from review_bot.services.github_service import GitHubService
from review_bot.services.review_service import MRReviewState

logger = logging.getLogger(__name__)


class ReviewWorkflow:
    def __init__(self):
        self.github_service = GitHubService()

        # Initialize all models with Gemini for cloud deployment
        self.reviewer_a_client = GeminiClient(
            os.getenv("REVIEWER_A_MODEL", "gemini-2.0-flash-exp")
        )
        self.reviewer_b_client = GeminiClient(
            os.getenv("REVIEWER_B_MODEL", "gemini-2.0-flash-exp")
        )
        self.judge_client = GeminiClient(
            os.getenv("JUDGE_MODEL", "gemini-2.0-flash-exp")
        )

        self.graph = self._build_graph()

        # Load prompts
        self.prompts = self._load_prompts()

    def _load_prompts(self) -> dict[str, str]:
        """Load all prompt templates"""
        prompts = {}
        prompt_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")

        for prompt_file in [
            "reviewer_a_prompt.txt",
            "reviewer_b_prompt.txt",
            "judge_prompt.txt",
            "justify_prompt.txt",
        ]:
            try:
                with open(f"{prompt_dir}/{prompt_file}") as f:
                    key = prompt_file.replace("_prompt.txt", "")
                    prompts[key] = f.read().strip()
            except FileNotFoundError:
                logger.warning(f"Prompt file {prompt_file} not found")
                prompts[prompt_file.replace("_prompt.txt", "")] = ""

        return prompts

    def reviewer_a_node(self, state: MRReviewState) -> MRReviewState:
        """Security and performance reviewer"""
        logger.info("=== REVIEWER A (Security/Performance) ===")
        logger.info("Input diff size: %d characters", len(state["diff_text"]))
        logger.info(
            "System prompt: %s", self.prompts.get("reviewer_a", "NO PROMPT")[:200]
        )

        response = self.reviewer_a_client.generate_structured_response(
            prompt=f"Code diff to review:\n\n{state['diff_text']}",
            system_prompt=self.prompts.get("reviewer_a", ""),
        )

        logger.info("Reviewer A output: %s", str(response)[:500])
        state["review_a_output"] = str(response)
        return state

    def reviewer_b_node(self, state: MRReviewState) -> MRReviewState:
        """Readability and maintainability reviewer"""
        logger.info("=== REVIEWER B (Code Quality) ===")
        logger.info("Input diff size: %d characters", len(state["diff_text"]))
        logger.info(
            "System prompt: %s", self.prompts.get("reviewer_b", "NO PROMPT")[:200]
        )

        response = self.reviewer_b_client.generate_structured_response(
            prompt=f"Code diff to review:\n\n{state['diff_text']}",
            system_prompt=self.prompts.get("reviewer_b", ""),
        )

        logger.info("Reviewer B output: %s", str(response)[:500])
        state["review_b_output"] = str(response)
        return state

    def judge_node(self, state: MRReviewState) -> MRReviewState:
        """Synthesize reviews and post final comment"""
        logger.info("=== JUDGE (Synthesis) ===")

        judge_input = f"""
Original Code Diff:
{state["diff_text"]}

Security/Performance Review:
{state.get("review_a_output", "No output")}

Readability/Maintainability Review:
{state.get("review_b_output", "No output")}
"""

        logger.info("Judge input size: %d characters", len(judge_input))
        logger.info("System prompt: %s", self.prompts.get("judge", "NO PROMPT")[:200])

        response = self.judge_client.generate_structured_response(
            prompt=judge_input, system_prompt=self.prompts.get("judge", "")
        )

        final_review = response if isinstance(response, str) else str(response)
        logger.info("Judge output: %s", final_review[:500])
        state["judge_output"] = final_review

        # Post the review
        success = self.github_service.post_review_comment(state["mr_iid"], final_review)
        logger.info("Posted review comment: %s", success)

        return state

    def justify_node(self, state: MRReviewState) -> MRReviewState:
        """Handle human feedback and justify/correct review"""
        try:
            justify_input = f"""
Original Code Diff:
{state["diff_text"]}

Original AI Review:
{state.get("original_review", "")}

Human Feedback:
{state.get("human_comment", "")}
"""

            response = self.judge_client.generate_structured_response(
                prompt=justify_input, system_prompt=self.prompts.get("justify", "")
            )

            justified_review = response if isinstance(response, str) else str(response)
            state["justified_review_text"] = justified_review

            # Post justification as reply
            self.github_service.post_review_comment(state["mr_iid"], justified_review)

        except Exception as e:
            logger.error(f"Justify failed: {e}")
            state["error_message"] = [f"Justify error: {str(e)}"]

        return state

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        graph = StateGraph(MRReviewState)

        # Add nodes
        graph.add_node("reviewer_a", self.reviewer_a_node)
        graph.add_node("reviewer_b", self.reviewer_b_node)
        graph.add_node("judge", self.judge_node)
        graph.add_node("justify", self.justify_node)

        # Sequential review flow to avoid concurrent updates
        graph.add_edge(START, "reviewer_a")
        graph.add_edge("reviewer_a", "reviewer_b")
        graph.add_edge("reviewer_b", "judge")
        graph.add_edge("judge", END)

        # Justification flow (separate entry point)
        graph.add_edge("justify", END)

        return graph.compile()

    def run_review(
        self, project_id: int, mr_iid: int, diff_text: str
    ) -> dict[str, Any]:
        """Run the main review workflow"""
        initial_state = MRReviewState(
            diff_text=diff_text,
            project_id=project_id,
            mr_iid=mr_iid,
            review_a_output=None,
            review_b_output=None,
            judge_output=None,
            error_message=[],
            original_review=None,
            human_comment=None,
            justified_review_text=None,
        )

        result = self.graph.invoke(initial_state)
        return result

    def run_justification(
        self,
        project_id: int,
        mr_iid: int,
        diff_text: str,
        original_review: str,
        human_comment: str,
    ) -> dict[str, Any]:
        """Run justification workflow for human feedback"""
        initial_state = MRReviewState(
            diff_text=diff_text,
            project_id=project_id,
            mr_iid=mr_iid,
            review_a_output=None,
            review_b_output=None,
            judge_output=None,
            error_message=[],
            original_review=original_review,
            human_comment=human_comment,
            justified_review_text=None,
        )

        # Create a separate graph instance for justification
        justify_graph = StateGraph(MRReviewState)
        justify_graph.add_node("justify", self.justify_node)
        justify_graph.add_edge(START, "justify")
        justify_graph.add_edge("justify", END)

        compiled_justify_graph = justify_graph.compile()
        result = compiled_justify_graph.invoke(initial_state)
        return result
