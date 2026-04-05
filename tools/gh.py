"""
These commands are used to interact and make changes to GitHub.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import logging

from ptscripts import Context, command_group

import tools.precommit.workflows
import tools.utils
import tools.utils.gh

log = logging.getLogger(__name__)

WORKFLOWS = tools.utils.REPO_ROOT / ".github" / "workflows"
TEMPLATES = WORKFLOWS / "templates"

# Define the command group
cgroup = command_group(
    name="gh",
    help="GitHub Related Commands",
    description=__doc__,
)


@cgroup.command(
    name="list-discussions",
    arguments={
        "repository": {
            "help": "GitHub repository (owner/name).",
        },
        "category": {
            "help": "Filter by discussion category name or slug.",
        },
        "limit": {
            "help": "Maximum number of discussions to return.",
        },
    },
)
def list_discussions(
    ctx: Context,
    repository: str = "saltstack/salt",
    category: str | None = None,
    limit: int = 20,
):
    """
    List discussions in a GitHub repository.
    """
    github_token = tools.utils.gh.get_github_token(ctx)
    if github_token is None:
        ctx.error("Listing discussions requires being authenticated to GitHub.")
        ctx.info(
            "Either set 'GITHUB_TOKEN' to a valid token, or configure the 'gh' tool such that "
            "'gh auth token' returns a token."
        )
        ctx.exit(1)

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with ctx.web as web:
        web.headers.update(headers)

        category_id: str | None = None
        if category is not None:
            repo_info = tools.utils.gh.get_repository_info(ctx, web, repository)
            if repo_info is None:
                ctx.exit(1)
            category_id = tools.utils.gh.get_discussion_category_id(
                ctx, repo_info["discussionCategories"], category
            )
            if category_id is None:
                ctx.exit(1)

        owner, name = repository.split("/", 1)
        query = """
query ListDiscussions($owner: String!, $name: String!, $first: Int!, $categoryId: ID) {
  repository(owner: $owner, name: $name) {
    discussions(first: $first, categoryId: $categoryId) {
      nodes {
        number
        title
        url
        createdAt
        author {
          login
        }
        category {
          name
        }
        comments {
          totalCount
        }
      }
    }
  }
}
"""
        variables = {
            "owner": owner,
            "name": name,
            "first": limit,
        }
        if category_id is not None:
            variables["categoryId"] = category_id

        data = tools.utils.gh.run_graphql_query(ctx, web, query, variables)
        if data is None:
            ctx.exit(1)

        discussions = data["repository"]["discussions"]["nodes"]
        if not discussions:
            ctx.info("No discussions found.")
            return

        for discussion in discussions:
            ctx.info(
                f"#{discussion['number']}  [{discussion['category']['name']}]  "
                f"{discussion['title']}  ({discussion['comments']['totalCount']} comments)  "
                f"by {discussion['author']['login']}  {discussion['url']}"
            )


@cgroup.command(
    name="create-discussion",
    arguments={
        "repository": {
            "help": "GitHub repository (owner/name).",
        },
        "title": {
            "help": "Title of the discussion.",
            "required": True,
        },
        "body": {
            "help": "Body text of the discussion (Markdown).",
            "required": True,
        },
        "category": {
            "help": "Discussion category name or slug.",
            "required": True,
        },
    },
)
def create_discussion(
    ctx: Context,
    title: str,
    body: str,
    category: str,
    repository: str = "saltstack/salt",
):
    """
    Create a new discussion in a GitHub repository.
    """
    github_token = tools.utils.gh.get_github_token(ctx)
    if github_token is None:
        ctx.error("Creating discussions requires being authenticated to GitHub.")
        ctx.info(
            "Either set 'GITHUB_TOKEN' to a valid token, or configure the 'gh' tool such that "
            "'gh auth token' returns a token."
        )
        ctx.exit(1)

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with ctx.web as web:
        web.headers.update(headers)

        repo_info = tools.utils.gh.get_repository_info(ctx, web, repository)
        if repo_info is None:
            ctx.exit(1)

        category_id = tools.utils.gh.get_discussion_category_id(
            ctx, repo_info["discussionCategories"], category
        )
        if category_id is None:
            ctx.exit(1)

        mutation = """
mutation CreateDiscussion($repositoryId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
  createDiscussion(input: {
    repositoryId: $repositoryId
    categoryId: $categoryId
    title: $title
    body: $body
  }) {
    discussion {
      number
      url
    }
  }
}
"""
        variables = {
            "repositoryId": repo_info["id"],
            "categoryId": category_id,
            "title": title,
            "body": body,
        }
        data = tools.utils.gh.run_graphql_query(ctx, web, mutation, variables)
        if data is None:
            ctx.exit(1)

        discussion = data["createDiscussion"]["discussion"]
        ctx.info(
            f"Created discussion #{discussion['number']}: {discussion['url']}"
        )


@cgroup.command(
    name="comment-on-discussion",
    arguments={
        "repository": {
            "help": "GitHub repository (owner/name).",
        },
        "discussion_number": {
            "help": "The number of the discussion to comment on.",
            "required": True,
        },
        "body": {
            "help": "Comment text (Markdown).",
            "required": True,
        },
    },
)
def comment_on_discussion(
    ctx: Context,
    discussion_number: int,
    body: str,
    repository: str = "saltstack/salt",
):
    """
    Add a comment to an existing GitHub discussion.
    """
    github_token = tools.utils.gh.get_github_token(ctx)
    if github_token is None:
        ctx.error("Commenting on discussions requires being authenticated to GitHub.")
        ctx.info(
            "Either set 'GITHUB_TOKEN' to a valid token, or configure the 'gh' tool such that "
            "'gh auth token' returns a token."
        )
        ctx.exit(1)

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with ctx.web as web:
        web.headers.update(headers)

        owner, name = repository.split("/", 1)
        lookup_query = """
query GetDiscussion($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    discussion(number: $number) {
      id
      title
      url
    }
  }
}
"""
        lookup_data = tools.utils.gh.run_graphql_query(
            ctx,
            web,
            lookup_query,
            {"owner": owner, "name": name, "number": discussion_number},
        )
        if lookup_data is None:
            ctx.exit(1)

        discussion_node = lookup_data["repository"]["discussion"]
        if discussion_node is None:
            ctx.error(
                f"Discussion #{discussion_number} not found in repository {repository!r}"
            )
            ctx.exit(1)

        mutation = """
mutation AddDiscussionComment($discussionId: ID!, $body: String!) {
  addDiscussionComment(input: {
    discussionId: $discussionId
    body: $body
  }) {
    comment {
      id
      url
    }
  }
}
"""
        data = tools.utils.gh.run_graphql_query(
            ctx,
            web,
            mutation,
            {"discussionId": discussion_node["id"], "body": body},
        )
        if data is None:
            ctx.exit(1)

        comment = data["addDiscussionComment"]["comment"]
        ctx.info(f"Comment added: {comment['url']}")


@cgroup.command(
    name="sync-os-labels",
    arguments={
        "repository": {
            "help": "Github repository.",
        },
    },
)
def sync_os_labels(
    ctx: Context, repository: str = "saltstack/salt", color: str = "C2E0C6"
):
    """
    Synchronize the GitHub labels to the OS known to be tested.
    """
    description_prefix = "Run Tests Against"
    known_os = {
        "test:os:all": {
            "name": "test:os:all",
            "color": color,
            "description": f"{description_prefix} ALL OS'es",
        },
    }
    for slug in tools.precommit.workflows.slugs():
        name = f"test:os:{slug}"
        known_os[name] = {
            "name": name,
            "color": color,
            "description": f"{description_prefix} {slug}",
        }

    ctx.info(known_os)

    github_token = tools.utils.gh.get_github_token(ctx)
    if github_token is None:
        ctx.error("Querying labels requires being authenticated to GitHub.")
        ctx.info(
            "Either set 'GITHUB_TOKEN' to a valid token, or configure the 'gh' tool such that "
            "'gh auth token' returns a token."
        )
        ctx.exit(1)

    existing_labels = set()
    labels_to_update = []
    labels_to_delete = set()
    shared_context = tools.utils.get_cicd_shared_context()
    for slug in shared_context["mandatory_os_slugs"]:
        label = f"test:os:{slug}"
        labels_to_delete.add(label)

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with ctx.web as web:
        web.headers.update(headers)
        page = 0
        while True:
            page += 1
            params = {
                "per_page": 100,
                "page": page,
            }
            ret = web.get(
                f"https://api.github.com/repos/{repository}/labels",
                params=params,
            )
            if ret.status_code != 200:
                ctx.error(
                    f"Failed to get the labels for repository {repository!r}: {ret.reason}"
                )
                ctx.exit(1)
            data = ret.json()
            if not data:
                break
            for details in data:
                label = details["name"]
                if not label.startswith("test:os:"):
                    continue

                existing_labels.add(label)

                if label not in known_os:
                    labels_to_delete.add(details["name"])
                    continue

                if label in known_os:
                    update_details = known_os.pop(label)
                    if label in labels_to_delete:
                        continue
                    for key, value in update_details.items():
                        if details[key] != value:
                            labels_to_update.append(update_details)
                            break
                    continue

        for slug in shared_context["mandatory_os_slugs"]:
            label = f"test:os:{slug}"
            if label in known_os:
                labels_to_delete.add(label)
                known_os.pop(label)

            if label in labels_to_update:
                labels_to_delete.add(label)
                known_os.pop(label)

        for label in labels_to_delete:
            if label not in existing_labels:
                continue
            ctx.info(f"Deleting label '{label}' ...")
            ret = web.delete(
                f"https://api.github.com/repos/{repository}/labels/{label}",
            )
            if ret.status_code != 204:
                ctx.error(
                    f"Failed to delete label '{label}' for repository {repository!r}: {ret.reason}"
                )

        ctx.info("Updating OS Labels in GitHub...")
        for details in labels_to_update:
            label = details["name"]
            ctx.info(f"Updating label '{label}' ...")
            ret = web.patch(
                f"https://api.github.com/repos/{repository}/labels/{label}",
                params=details,
            )
            if ret.status_code != 200:
                ctx.error(
                    f"Failed to update label '{details['name']}' for repository {repository!r}: {ret.reason}"
                )

        for label, details in known_os.items():
            details["name"] = label
            ctx.info(f"Creating label: {details} ...")
            ret = web.post(
                f"https://api.github.com/repos/{repository}/labels",
                json=details,
            )
            if ret.status_code != 201:
                ctx.error(
                    f"Failed to create label '{details['name']}' for repository {repository!r}: {ret.reason}"
                )
                print(ret.content)
