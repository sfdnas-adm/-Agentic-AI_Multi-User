# review_bot/services/github_service.py
import os

import requests


class GitHubService:
    """
    A service class to wrap all necessary GitHub API interactions.
    This acts as a Tool callable by the LLM orchestration framework (LangGraph).
    """

    def __init__(self, github_token: str | None = None):
        """Initializes the GitHub client."""
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self.repo_owner = os.environ.get("GITHUB_OWNER", "sfdnas-adm")
        self.repo_name = os.environ.get("GITHUB_REPO", "-Agentic-AI_Multi-User")
        self.base_url = "https://api.github.com"

        if not self.github_token:
            raise ValueError("GITHUB_TOKEN must be set in the environment.")

        # Debug: Log token info (first/last 4 chars only for security)
        token_preview = (
            f"{self.github_token[:4]}...{self.github_token[-4:]}"
            if len(self.github_token) > 8
            else "[short_token]"
        )
        print(f"GitHub token configured: {token_preview}")

        # Set up headers for GitHub API
        self.headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def fetch_pr_diff(self, pr_number: int) -> str:
        """
        Fetches the complete code diff (changes) for a Pull Request.
        """
        try:
            # Get PR diff directly
            diff_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}/files"
            diff_response = requests.get(diff_url, headers=self.headers)
            diff_response.raise_for_status()
            files_data = diff_response.json()

            # Process diff for LLM
            full_diff_text = []
            for file_data in files_data:
                if "patch" in file_data:
                    full_diff_text.append(
                        f"--- File: {file_data['filename']} ---\n{file_data['patch']}\n"
                    )

            diff_content = "\n".join(full_diff_text)

            # Add issue context
            issue_context = self.fetch_issue_details(pr_number)
            if issue_context and "No linked issues" not in issue_context:
                return f"=== LINKED ISSUES ===\n{issue_context}\n\n=== CODE CHANGES ===\n{diff_content}"

            return diff_content

        except requests.exceptions.RequestException as e:
            return f"Error fetching PR changes: {e}"
        except Exception as e:
            return f"An unexpected error occurred: {e}"

    def post_review_comment(self, pr_number: int, comment_body: str) -> bool:
        """
        Posts the final synthesized review as a comment on the Pull Request.
        """
        try:
            comment_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/issues/{pr_number}/comments"
            comment_data = {"body": comment_body}

            response = requests.post(
                comment_url, headers=self.headers, json=comment_data
            )
            response.raise_for_status()

            print(f"Posted review comment to PR #{pr_number}")
            return True

        except requests.exceptions.RequestException as e:
            print(f"Error posting comment to PR #{pr_number}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error posting comment: {e}")
            return False

    def fetch_issue_details(self, pr_number: int) -> str:
        """Fetch linked issue details for context."""
        try:
            # Get PR details
            pr_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}"
            pr_response = requests.get(pr_url, headers=self.headers)
            pr_response.raise_for_status()
            pr_data = pr_response.json()

            # Get PR description and title
            description = pr_data.get("body") or ""
            title = pr_data.get("title") or ""

            # Look for issue references (#123, closes #123, etc.)
            import re

            issue_refs = re.findall(r"#(\d+)", f"{title} {description}")

            if not issue_refs:
                return "No linked issues found"

            issue_details = []
            for issue_id in set(issue_refs):  # Remove duplicates
                try:
                    issue_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/issues/{issue_id}"
                    issue_response = requests.get(issue_url, headers=self.headers)
                    issue_response.raise_for_status()
                    issue_data = issue_response.json()

                    labels = [label["name"] for label in issue_data.get("labels", [])]
                    issue_details.append(
                        f"Issue #{issue_id}: {issue_data['title']}\n"
                        f"Description: {issue_data.get('body') or 'No description'}\n"
                        f"Labels: {', '.join(labels) if labels else 'None'}\n"
                        f"State: {issue_data['state']}"
                    )
                except Exception:
                    continue

            return (
                "\n\n".join(issue_details)
                if issue_details
                else "No accessible issues found"
            )

        except requests.exceptions.RequestException as e:
            return f"Error fetching issue details: {e}"
        except Exception as e:
            return f"Error processing issues: {e}"
