# review_bot/services/gitlab_service.py
import os

import gitlab


class GitLabService:
    """
    A service class to wrap all necessary GitLab API interactions.
    This acts as a Tool callable by the LLM orchestration framework (LangGraph).
    """

    def __init__(self, gitlab_url: str | None = None, private_token: str | None = None):
        """Initializes the GitLab client."""
        self.gitlab_url = gitlab_url or os.environ.get(
            "GITLAB_URL", "https://gitlab.rz.uni-bamberg.de"
        )
        self.private_token = private_token or os.environ.get("GITLAB_TOKEN")
        self.allowed_project_id = int(os.environ.get("ALLOWED_PROJECT_ID", "8462"))

        if (
            not self.private_token
            or self.private_token == "your_gitlab_personal_access_token"
        ):
            raise ValueError(
                "GITLAB_TOKEN must be set to a valid token in the environment."
            )

        # Debug: Log token info (first/last 4 chars only for security)
        token_preview = (
            f"{self.private_token[:4]}...{self.private_token[-4:]}"
            if len(self.private_token) > 8
            else "[short_token]"
        )
        print(f"GitLab token configured: {token_preview}")

        # Initialize the Gitlab client
        self.gl = gitlab.Gitlab(self.gitlab_url, private_token=self.private_token)

    def fetch_mr_diff(self, project_id: int, mr_iid: int) -> str:
        """
        Fetches the complete code diff (changes) for a Merge Request.

        :param project_id: The project ID.
        :param mr_iid: The internal ID (IID) of the Merge Request.
        :return: A single string containing all file changes in unified diff format.
        """
        # Check if project is allowed
        if project_id != self.allowed_project_id:
            return f"Error: Project {project_id} not allowed. Only project {self.allowed_project_id} is supported."

        try:
            # 1. Get the project object
            project = self.gl.projects.get(project_id)

            # 2. Get the specific Merge Request object
            mr = project.mergerequests.get(mr_iid)

            # 3. Retrieve the changes data
            # The .changes() method gets the MR's diff content.
            changes_data = mr.changes()

            # 4. Process and format the diff for the LLM
            full_diff_text = []

            # Iterate through all files changed in the MR
            for change in changes_data.get("changes", []):
                file_diff = change.get("diff", "")
                if file_diff:
                    # Append the diff for each file. This is the crucial input context.
                    full_diff_text.append(
                        f"--- File: {change.get('old_path')} -> {change.get('new_path')} ---\n{file_diff}\n"
                    )

            diff_content = "\n".join(full_diff_text)

            # Add issue context
            issue_context = self.fetch_issue_details(project_id, mr_iid)
            if (
                issue_context
                and "Error" not in issue_context
                and "No" not in issue_context
            ):
                return f"=== LINKED ISSUES ===\n{issue_context}\n\n=== CODE CHANGES ===\n{diff_content}"

            return diff_content

        except gitlab.exceptions.GitlabGetError as e:
            return f"Error fetching MR changes: {e}"
        except Exception as e:
            return f"An unexpected error occurred: {e}"

    def post_review_comment(
        self, project_id: int, mr_iid: int, comment_body: str
    ) -> bool:
        """
        Posts the final synthesized review as a comment on the Merge Request.

        :param project_id: The project ID.
        :param mr_iid: The internal ID (IID) of the Merge Request.
        :return: True if successful, False otherwise.
        """
        # Check if project is allowed
        if project_id != self.allowed_project_id:
            print(
                f"Error: Project {project_id} not allowed. Only project {self.allowed_project_id} is supported."
            )
            return False

        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)

            # Use the .notes.create() method to add a comment (also called a "note" in the API)
            mr.notes.create({"body": comment_body})
            return True
        except Exception as e:
            print(f"Error posting comment to MR !{mr_iid}: {e}")
            return False

    def fetch_issue_details(self, project_id: int, mr_iid: int) -> str:
        """Fetch linked issue details for context."""
        if project_id != self.allowed_project_id:
            return "Error: Project not allowed"

        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)

            # Get MR description to find issue references
            description = mr.description or ""
            title = mr.title or ""

            # Look for issue references (#123, closes #123, etc.)
            import re

            issue_refs = re.findall(r"#(\d+)", f"{title} {description}")

            if not issue_refs:
                return "No linked issues found"

            issue_details = []
            for issue_id in set(issue_refs):  # Remove duplicates
                try:
                    issue = project.issues.get(int(issue_id))
                    issue_details.append(
                        f"Issue #{issue_id}: {issue.title}\n"
                        f"Description: {issue.description or 'No description'}\n"
                        f"Labels: {', '.join(issue.labels) if issue.labels else 'None'}\n"
                        f"State: {issue.state}"
                    )
                except Exception:
                    continue

            return (
                "\n\n".join(issue_details)
                if issue_details
                else "No accessible issues found"
            )

        except Exception as e:
            return f"Error fetching issue details: {e}"
