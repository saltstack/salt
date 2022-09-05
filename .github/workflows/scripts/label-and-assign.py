import argparse
import datetime
import json
import operator
import os
import pathlib
import random
import sys

import github
from github.GithubException import GithubException

CACHE_FILENAME = pathlib.Path(".cache", "last-user-assigned")


def get_last_account_assigned():
    if not CACHE_FILENAME.exists():
        return

    try:
        data = json.loads(CACHE_FILENAME.read_text())
        return data["username"]
    except (ValueError, KeyError):
        return


def get_team_members(options):
    g = github.Github(os.environ["READ_ORG_TOKEN"])
    org = g.get_organization(options.org)
    team = org.get_team_by_slug(options.team)
    return sorted(list(team.get_members()), key=operator.attrgetter("login"))


def get_triage_next_account(options):
    team_members = get_team_members(options)
    last_account_assigned = get_last_account_assigned()
    if last_account_assigned is None:
        return random.choice(team_members)

    previous_account = None
    for member in team_members:
        if previous_account and previous_account.login == last_account_assigned:
            return member
        previous_account = member
    else:
        # The previously assigned account is not longer part of the team members
        # or the team was switched
        return random.choice(team_members)


def label_and_assign_issue(options):
    g = github.Github(os.environ["GITHUB_TOKEN"])
    org = g.get_organization(options.org)
    print(f"Loaded Organization: {org.login}", file=sys.stderr, flush=True)
    repo = org.get_repo(options.repo)
    print(f"Loaded Repository: {repo.full_name}", file=sys.stderr, flush=True)
    issue = repo.get_issue(options.issue)
    print(f"Loaded Issue: {issue}", file=sys.stderr, flush=True)
    next_triage_account = get_triage_next_account(options)
    print(
        f"Next account up for triage: {next_triage_account.login}",
        file=sys.stderr,
        flush=True,
    )
    print(f"Adding label {options.label} to {issue}", file=sys.stderr, flush=True)
    issue.add_to_labels(options.label)
    print(
        f"Assigning {issue} to {next_triage_account.login}", file=sys.stderr, flush=True
    )
    issue.add_to_assignees(next_triage_account)
    CACHE_FILENAME.write_text(
        json.dumps(
            {
                "username": next_triage_account.login,
                "when": str(datetime.datetime.utcnow()),
            }
        )
    )
    print("Done!", file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", required=True, help="The Github Organization")
    parser.add_argument("--team", required=True, help="The Organization Team Slug")
    parser.add_argument("--repo", required=True, help="The Organization Repository")
    parser.add_argument("--issue", required=True, type=int, help="The issue number")
    parser.add_argument("--label", required=True, help="The issue label to assign")

    if not os.environ.get("GITHUB_TOKEN"):
        parser.exit(status=1, message="GITHUB_TOKEN environment variable not set")
    if not os.environ.get("READ_ORG_TOKEN"):
        parser.exit(status=1, message="READ_ORG_TOKEN environment variable not set")

    options = parser.parse_args()
    print(
        f"Last assignment cache file path: {CACHE_FILENAME}",
        file=sys.stderr,
        flush=True,
    )
    if CACHE_FILENAME.parent.is_dir() is False:
        CACHE_FILENAME.parent.mkdir()

    try:
        label_and_assign_issue(options)
        parser.exit(0)
    except GithubException as exc:
        parser.exit(1, message=str(exc))


if __name__ == "__main__":
    main()
