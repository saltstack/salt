import argparse
import os
import pathlib
import sys

import github
from github.GithubException import GithubException

COMMENT_HEADER = "### Hi! I'm your friendly PR bot!"
COMMENT_TEMPLATE = """\
{comment_header}

You might be wondering what I'm doing commenting here on your PR.

**Yes, as a matter of fact, I am...**

I'm just here to help us improve the documentation. I can't respond to
questions or anything, but what I *can* do, I do well!

**Okay... so what do you do?**

I detect modules that are missing docstrings or "CLI Example" on existing docstrings!
When I was created we had a *lot* of these. The documentation for these
modules need some love and attention to make Salt better for our users.

**So what does that have to do with my PR?**

I noticed that in this PR there are some files changed that have some of these
issues. So I'm leaving this comment to let you know your options.

**Okay, what are they?**

Well, my favorite, is that since you were making changes here I'm hoping that
you would be the most familiar with this module and be able to add some other
examples or fix any of the reported issues.

**If I can, then what?**

Well, you can either add them to this PR or add them to another PR. Either way is fine!

**Well... what if I can't, or don't want to?**

That's also fine! We appreciate *all* contributions to the Salt Project. If you
can't add those other examples, either because you're too busy, or unfamiliar,
or you just aren't interested, we still appreciate the contributions that
you've made already.

Whatever approach you decide to take, just drop a comment here letting us know!

<details>
<summary>Detected Issues (click me)</summary>
<pre>{issues_output}</pre>
</details>

---

Thanks again!
"""


def get_previous_comments(pr):
    for comment in pr.get_issue_comments():
        if comment.user.login != "github-actions[bot]":
            # Not a comment made by this bot
            continue
        if not comment.body.startswith(COMMENT_HEADER):
            # This comment does not start with our header
            continue
        yield comment


def comment_on_pr(options, issues_output):
    gh = github.Github(os.environ["GITHUB_TOKEN"])
    org = gh.get_organization(options.org)
    print(f"Loaded Organization: {org.login}", file=sys.stderr, flush=True)
    repo = org.get_repo(options.repo)
    print(f"Loaded Repository: {repo.full_name}", file=sys.stderr, flush=True)
    pr = repo.get_pull(options.issue)
    print(f"Loaded PR: {pr}", file=sys.stderr, flush=True)
    comment = pr.create_issue_comment(
        COMMENT_TEMPLATE.format(
            comment_header=COMMENT_HEADER, issues_output=issues_output
        )
    )
    new_comment_content = COMMENT_TEMPLATE.format(
        comment_header=COMMENT_HEADER, issues_output=issues_output
    )
    for comment in get_previous_comments(pr):
        if comment.body.strip() != new_comment_content.strip():
            # The content has changed.
            print(f"Deleting previous comment {comment}")
            comment.delete()

    comment = pr.create_issue_comment(new_comment_content)
    print(f"Created Comment: {comment}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", required=True, help="The Github Organization")
    parser.add_argument("--repo", required=True, help="The Organization Repository")
    parser.add_argument("--issue", required=True, type=int, help="The issue number")
    parser.add_argument(
        "issues_output_path", metavar="ISSUES_OUTPUT_PATH", type=pathlib.Path
    )

    if not os.environ.get("GITHUB_TOKEN"):
        parser.exit(status=1, message="GITHUB_TOKEN environment variable not set")

    options = parser.parse_args()
    if not options.issues_output_path.is_file():
        parser.exit(1, message=f"The path {options.issues_output_path} is not a file")
    issues_output = options.issues_output_path.read_text().strip()
    if not issues_output:
        parser.exit(1, message=f"The file {options.issues_output_path} is empty")
    try:
        comment_on_pr(options, issues_output)
        parser.exit(0)
    except GithubException as exc:
        parser.exit(1, message=str(exc))


if __name__ == "__main__":
    main()
