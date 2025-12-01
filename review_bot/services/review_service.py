from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class MRReviewState(TypedDict):
    """State for the MR review workflow"""

    diff_text: str
    project_id: int
    mr_iid: int
    review_a_output: str | None
    review_b_output: str | None
    judge_output: str | None
    error_message: Annotated[list, add_messages]
    # For feedback loop
    original_review: str | None
    human_comment: str | None
    justified_review_text: str | None
