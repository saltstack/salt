"""
Module for interacting with the GitHub v3 API.

.. versionadded:: 2016.3.0

:depends: PyGithub python module

Configuration
-------------

Configure this module by specifying the name of a configuration
profile in the minion config, minion pillar, or master config. The module
will use the 'github' key by default, if defined.

For example:

.. code-block:: yaml

    github:
      token: abc1234
      org_name: my_organization

      # optional: some functions require a repo_name, which
      # can be set in the config file, or passed in at the CLI.
      repo_name: my_repo

      # optional: it can be dangerous to change the privacy of a repository
      # in an automated way. set this to True to allow privacy modifications
      allow_repo_privacy_changes: False
"""

import logging

import salt.utils.http
from salt.exceptions import CommandExecutionError

HAS_LIBS = False
try:
    # pylint: disable=no-name-in-module
    import github
    import github.NamedUser
    import github.PaginatedList
    from github.GithubException import UnknownObjectException

    # pylint: enable=no-name-in-module
    HAS_LIBS = True
except ImportError:
    pass

log = logging.getLogger(__name__)

__virtualname__ = "github"


def __virtual__():
    """
    Only load this module if PyGithub is installed on this minion.
    """
    if HAS_LIBS:
        return __virtualname__
    return (
        False,
        "The github execution module cannot be loaded: "
        "PyGithub library is not installed.",
    )


def _get_config_value(profile, config_name):
    """
    Helper function that returns a profile's configuration value based on
    the supplied configuration name.

    profile
        The profile name that contains configuration information.

    config_name
        The configuration item's name to use to return configuration values.
    """
    config = __salt__["config.option"](profile)
    if not config:
        raise CommandExecutionError(
            "Authentication information could not be found for the "
            "'{}' profile.".format(profile)
        )

    config_value = config.get(config_name)
    if config_value is None:
        raise CommandExecutionError(
            "The '{}' parameter was not found in the '{}' profile.".format(
                config_name, profile
            )
        )

    return config_value


def _get_client(profile):
    """
    Return the GitHub client, cached into __context__ for performance
    """
    token = _get_config_value(profile, "token")
    key = "github.{}:{}".format(token, _get_config_value(profile, "org_name"))

    if key not in __context__:
        __context__[key] = github.Github(token, per_page=100)
    return __context__[key]


def _get_members(organization, params=None):
    return github.PaginatedList.PaginatedList(
        github.NamedUser.NamedUser,
        organization._requester,
        organization.url + "/members",
        params,
    )


def _get_repos(profile, params=None, ignore_cache=False):
    # Use cache when no params are given
    org_name = _get_config_value(profile, "org_name")
    key = f"github.{org_name}:repos"

    if key not in __context__ or ignore_cache or params is not None:
        org_name = _get_config_value(profile, "org_name")
        client = _get_client(profile)
        organization = client.get_organization(org_name)

        result = github.PaginatedList.PaginatedList(
            github.Repository.Repository,
            organization._requester,
            organization.url + "/repos",
            params,
        )

        # Only cache results if no params were given (full scan)
        if params is not None:
            return result

        next_result = []

        for repo in result:
            next_result.append(repo)

            # Cache a copy of each repo for single lookups
            repo_key = f"github.{org_name}:{repo.name.lower()}:repo_info"
            __context__[repo_key] = _repo_to_dict(repo)

        __context__[key] = next_result

    return __context__[key]


def list_users(profile="github", ignore_cache=False):
    """
    List all users within the organization.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached users.

        .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_users
        salt myminion github.list_users profile='my-github-profile'
    """
    org_name = _get_config_value(profile, "org_name")
    key = f"github.{org_name}:users"
    if key not in __context__ or ignore_cache:
        client = _get_client(profile)
        organization = client.get_organization(org_name)
        __context__[key] = [member.login for member in _get_members(organization, None)]
    return __context__[key]


def get_user(name, profile="github", user_details=False):
    """
    Get a GitHub user by name.

    name
        The user for which to obtain information.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    user_details
        Prints user information details. Defaults to ``False``. If the user is
        already in the organization and user_details is set to False, the
        get_user function returns ``True``. If the user is not already present
        in the organization, user details will be printed by default.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_user github-handle
        salt myminion github.get_user github-handle user_details=true

    """

    if not user_details and name in list_users(profile):
        # User is in the org, no need for additional Data
        return True

    response = {}
    client = _get_client(profile)
    organization = client.get_organization(_get_config_value(profile, "org_name"))

    try:
        user = client.get_user(name)
    except UnknownObjectException:
        log.exception("Resource not found")
        return False

    response["company"] = user.company
    response["created_at"] = user.created_at
    response["email"] = user.email
    response["html_url"] = user.html_url
    response["id"] = user.id
    response["login"] = user.login
    response["name"] = user.name
    response["type"] = user.type
    response["url"] = user.url

    try:
        headers, data = organization._requester.requestJsonAndCheck(
            "GET", organization.url + "/memberships/" + user._identity
        )
    except UnknownObjectException:
        response["membership_state"] = "nonexistent"
        response["in_org"] = False
        return response

    response["in_org"] = organization.has_in_members(user)
    response["membership_state"] = data.get("state")

    return response


def add_user(name, profile="github"):
    """
    Add a GitHub user.

    name
        The user for which to obtain information.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.add_user github-handle
    """

    client = _get_client(profile)
    organization = client.get_organization(_get_config_value(profile, "org_name"))

    try:
        github_named_user = client.get_user(name)
    except UnknownObjectException:
        log.exception("Resource not found")
        return False

    headers, data = organization._requester.requestJsonAndCheck(
        "PUT", organization.url + "/memberships/" + github_named_user._identity
    )

    return data.get("state") == "pending"


def remove_user(name, profile="github"):
    """
    Remove a Github user by name.

    name
        The user for which to obtain information.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_user github-handle
    """

    client = _get_client(profile)
    organization = client.get_organization(_get_config_value(profile, "org_name"))

    try:
        git_user = client.get_user(name)
    except UnknownObjectException:
        log.exception("Resource not found")
        return False

    if organization.has_in_members(git_user):
        organization.remove_from_members(git_user)

    return not organization.has_in_members(git_user)


def get_issue(issue_number, repo_name=None, profile="github", output="min"):
    """
    Return information about a single issue in a named repository.

    .. versionadded:: 2016.11.0

    issue_number
        The number of the issue to retrieve.

    repo_name
        The name of the repository from which to get the issue. This argument is
        required, either passed via the CLI, or defined in the configured
        profile. A ``repo_name`` passed as a CLI argument will override the
        repo_name defined in the configured profile, if provided.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    output
        The amount of data returned by each issue. Defaults to ``min``. Change
        to ``full`` to see all issue output.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_issue 514
        salt myminion github.get_issue 514 repo_name=salt
    """
    org_name = _get_config_value(profile, "org_name")
    if repo_name is None:
        repo_name = _get_config_value(profile, "repo_name")

    action = "/".join(["repos", org_name, repo_name])
    command = "issues/" + str(issue_number)

    ret = {}
    issue_data = _query(profile, action=action, command=command)

    issue_id = issue_data.get("id")
    if output == "full":
        ret[issue_id] = issue_data
    else:
        ret[issue_id] = _format_issue(issue_data)

    return ret


def get_issue_comments(
    issue_number, repo_name=None, profile="github", since=None, output="min"
):
    """
    Return information about the comments for a given issue in a named repository.

    .. versionadded:: 2016.11.0

    issue_number
        The number of the issue for which to retrieve comments.

    repo_name
        The name of the repository to which the issue belongs. This argument is
        required, either passed via the CLI, or defined in the configured
        profile. A ``repo_name`` passed as a CLI argument will override the
        repo_name defined in the configured profile, if provided.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    since
        Only comments updated at or after this time are returned. This is a
        timestamp in ISO 8601 format: ``YYYY-MM-DDTHH:MM:SSZ``.

    output
        The amount of data returned by each issue. Defaults to ``min``. Change
        to ``full`` to see all issue output.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_issue_comments 514
        salt myminion github.get_issue 514 repo_name=salt
    """
    org_name = _get_config_value(profile, "org_name")
    if repo_name is None:
        repo_name = _get_config_value(profile, "repo_name")

    action = "/".join(["repos", org_name, repo_name])
    command = "/".join(["issues", str(issue_number), "comments"])

    args = {}
    if since:
        args["since"] = since

    comments = _query(profile, action=action, command=command, args=args)

    ret = {}
    for comment in comments:
        comment_id = comment.get("id")
        if output == "full":
            ret[comment_id] = comment
        else:
            ret[comment_id] = {
                "id": comment.get("id"),
                "created_at": comment.get("created_at"),
                "updated_at": comment.get("updated_at"),
                "user_login": comment.get("user").get("login"),
            }
    return ret


def get_issues(
    repo_name=None,
    profile="github",
    milestone=None,
    state="open",
    assignee=None,
    creator=None,
    mentioned=None,
    labels=None,
    sort="created",
    direction="desc",
    since=None,
    output="min",
    per_page=None,
):
    """
    Returns information for all issues in a given repository, based on the search options.

    .. versionadded:: 2016.11.0

    repo_name
        The name of the repository for which to list issues. This argument is
        required, either passed via the CLI, or defined in the configured
        profile. A ``repo_name`` passed as a CLI argument will override the
        repo_name defined in the configured profile, if provided.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    milestone
        The number of a GitHub milestone, or a string of either ``*`` or
        ``none``.

        If a number is passed, it should refer to a milestone by its number
        field. Use the ``github.get_milestone`` function to obtain a milestone's
        number.

        If the string ``*`` is passed, issues with any milestone are
        accepted. If the string ``none`` is passed, issues without milestones
        are returned.

    state
        Indicates the state of the issues to return. Can be either ``open``,
        ``closed``, or ``all``. Default is ``open``.

    assignee
        Can be the name of a user. Pass in ``none`` (as a string) for issues
        with no assigned user or ``*`` for issues assigned to any user.

    creator
        The user that created the issue.

    mentioned
        A user that's mentioned in the issue.

    labels
        A string of comma separated label names. For example, ``bug,ui,@high``.

    sort
        What to sort results by. Can be either ``created``, ``updated``, or
        ``comments``. Default is ``created``.

    direction
        The direction of the sort. Can be either ``asc`` or ``desc``. Default
        is ``desc``.

    since
        Only issues updated at or after this time are returned. This is a
        timestamp in ISO 8601 format: ``YYYY-MM-DDTHH:MM:SSZ``.

    output
        The amount of data returned by each issue. Defaults to ``min``. Change
        to ``full`` to see all issue output.

    per_page
        GitHub paginates data in their API calls. Use this value to increase or
        decrease the number of issues gathered from GitHub, per page. If not set,
        GitHub defaults are used. Maximum is 100.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_issues my-github-repo
    """
    org_name = _get_config_value(profile, "org_name")
    if repo_name is None:
        repo_name = _get_config_value(profile, "repo_name")

    action = "/".join(["repos", org_name, repo_name])
    args = {}

    # Build API arguments, as necessary.
    if milestone:
        args["milestone"] = milestone
    if assignee:
        args["assignee"] = assignee
    if creator:
        args["creator"] = creator
    if mentioned:
        args["mentioned"] = mentioned
    if labels:
        args["labels"] = labels
    if since:
        args["since"] = since
    if per_page:
        args["per_page"] = per_page

    # Only pass the following API args if they're not the defaults listed.
    if state and state != "open":
        args["state"] = state
    if sort and sort != "created":
        args["sort"] = sort
    if direction and direction != "desc":
        args["direction"] = direction

    ret = {}
    issues = _query(profile, action=action, command="issues", args=args)

    for issue in issues:
        # Pull requests are included in the issue list from GitHub
        # Let's not include those in the return.
        if issue.get("pull_request"):
            continue
        issue_id = issue.get("id")
        if output == "full":
            ret[issue_id] = issue
        else:
            ret[issue_id] = _format_issue(issue)

    return ret


def get_milestones(
    repo_name=None,
    profile="github",
    state="open",
    sort="due_on",
    direction="asc",
    output="min",
    per_page=None,
):
    """
    Return information about milestones for a given repository.

    .. versionadded:: 2016.11.0

    repo_name
        The name of the repository for which to list issues. This argument is
        required, either passed via the CLI, or defined in the configured
        profile. A ``repo_name`` passed as a CLI argument will override the
        repo_name defined in the configured profile, if provided.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    state
        The state of the milestone. Either ``open``, ``closed``, or ``all``.
        Default is ``open``.

    sort
        What to sort results by. Either ``due_on`` or ``completeness``. Default
        is ``due_on``.

    direction
        The direction of the sort. Either ``asc`` or ``desc``. Default is ``asc``.

    output
        The amount of data returned by each issue. Defaults to ``min``. Change
        to ``full`` to see all issue output.

    per_page
        GitHub paginates data in their API calls. Use this value to increase or
        decrease the number of issues gathered from GitHub, per page. If not set,
        GitHub defaults are used.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_milestones

    """
    org_name = _get_config_value(profile, "org_name")
    if repo_name is None:
        repo_name = _get_config_value(profile, "repo_name")

    action = "/".join(["repos", org_name, repo_name])
    args = {}

    if per_page:
        args["per_page"] = per_page

    # Only pass the following API args if they're not the defaults listed.
    if state and state != "open":
        args["state"] = state
    if sort and sort != "due_on":
        args["sort"] = sort
    if direction and direction != "asc":
        args["direction"] = direction

    ret = {}
    milestones = _query(profile, action=action, command="milestones", args=args)

    for milestone in milestones:
        milestone_id = milestone.get("id")
        if output == "full":
            ret[milestone_id] = milestone
        else:
            milestone.pop("creator")
            milestone.pop("html_url")
            milestone.pop("labels_url")
            ret[milestone_id] = milestone

    return ret


def get_milestone(
    number=None, name=None, repo_name=None, profile="github", output="min"
):
    """
    Return information about a single milestone in a named repository.

    .. versionadded:: 2016.11.0

    number
        The number of the milestone to retrieve. If provided, this option
        will be favored over ``name``.

    name
        The name of the milestone to retrieve.

    repo_name
        The name of the repository for which to list issues. This argument is
        required, either passed via the CLI, or defined in the configured
        profile. A ``repo_name`` passed as a CLI argument will override the
        repo_name defined in the configured profile, if provided.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    output
        The amount of data returned by each issue. Defaults to ``min``. Change
        to ``full`` to see all issue output.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_milestone 72
        salt myminion github.get_milestone name=my_milestone

    """
    ret = {}

    if not any([number, name]):
        raise CommandExecutionError(
            "Either a milestone 'name' or 'number' must be provided."
        )

    org_name = _get_config_value(profile, "org_name")
    if repo_name is None:
        repo_name = _get_config_value(profile, "repo_name")

    action = "/".join(["repos", org_name, repo_name])
    if number:
        command = "milestones/" + str(number)
        milestone_data = _query(profile, action=action, command=command)
        milestone_id = milestone_data.get("id")
        if output == "full":
            ret[milestone_id] = milestone_data
        else:
            milestone_data.pop("creator")
            milestone_data.pop("html_url")
            milestone_data.pop("labels_url")
            ret[milestone_id] = milestone_data
        return ret

    else:
        milestones = get_milestones(repo_name=repo_name, profile=profile, output=output)
        for key, val in milestones.items():
            if val.get("title") == name:
                ret[key] = val
                return ret

    return ret


def _repo_to_dict(repo):
    ret = {}
    ret["id"] = repo.id
    ret["name"] = repo.name
    ret["full_name"] = repo.full_name
    ret["owner"] = repo.owner.login
    ret["private"] = repo.private
    ret["html_url"] = repo.html_url
    ret["description"] = repo.description
    ret["fork"] = repo.fork
    ret["homepage"] = repo.homepage
    ret["size"] = repo.size
    ret["stargazers_count"] = repo.stargazers_count
    ret["watchers_count"] = repo.watchers_count
    ret["language"] = repo.language
    ret["open_issues_count"] = repo.open_issues_count
    ret["forks"] = repo.forks
    ret["open_issues"] = repo.open_issues
    ret["watchers"] = repo.watchers
    ret["default_branch"] = repo.default_branch
    ret["has_issues"] = repo.has_issues
    ret["has_wiki"] = repo.has_wiki
    ret["has_downloads"] = repo.has_downloads
    return ret


def get_repo_info(repo_name, profile="github", ignore_cache=False):
    """
    Return information for a given repo.

    .. versionadded:: 2016.11.0

    repo_name
        The name of the repository.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_repo_info salt
        salt myminion github.get_repo_info salt profile='my-github-profile'
    """

    org_name = _get_config_value(profile, "org_name")
    key = "github.{}:{}:repo_info".format(
        _get_config_value(profile, "org_name"), repo_name.lower()
    )

    if key not in __context__ or ignore_cache:
        client = _get_client(profile)
        try:
            repo = client.get_repo("/".join([org_name, repo_name]))
            if not repo:
                return {}

            # client.get_repo can return a github.Repository.Repository object,
            # even if the repo is invalid. We need to catch the exception when
            # we try to perform actions on the repo object, rather than above
            # the if statement.
            ret = _repo_to_dict(repo)

            __context__[key] = ret
        except github.UnknownObjectException:
            raise CommandExecutionError(
                "The '{}' repository under the '{}' organization could not "
                "be found.".format(repo_name, org_name)
            )
    return __context__[key]


def get_repo_teams(repo_name, profile="github"):
    """
    Return teams belonging to a repository.

    .. versionadded:: 2017.7.0

    repo_name
        The name of the repository from which to retrieve teams.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_repo_teams salt
        salt myminion github.get_repo_teams salt profile='my-github-profile'
    """
    ret = []
    org_name = _get_config_value(profile, "org_name")
    client = _get_client(profile)

    try:
        repo = client.get_repo("/".join([org_name, repo_name]))
    except github.UnknownObjectException:
        raise CommandExecutionError(
            "The '{}' repository under the '{}' organization could not "
            "be found.".format(repo_name, org_name)
        )
    try:
        teams = repo.get_teams()
        for team in teams:
            ret.append(
                {"id": team.id, "name": team.name, "permission": team.permission}
            )
    except github.UnknownObjectException:
        raise CommandExecutionError(
            "Unable to retrieve teams for repository '{}' under the '{}' "
            "organization.".format(repo_name, org_name)
        )
    return ret


def list_repos(profile="github"):
    """
    List all repositories within the organization. Includes public and private
    repositories within the organization Dependent upon the access rights of
    the profile token.

    .. versionadded:: 2016.11.0

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_repos
        salt myminion github.list_repos profile='my-github-profile'
    """
    return [repo.name for repo in _get_repos(profile)]


def list_private_repos(profile="github"):
    """
    List private repositories within the organization. Dependent upon the access
    rights of the profile token.

    .. versionadded:: 2016.11.0

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_private_repos
        salt myminion github.list_private_repos profile='my-github-profile'
    """
    repos = []
    for repo in _get_repos(profile):
        if repo.private is True:
            repos.append(repo.name)
    return repos


def list_public_repos(profile="github"):
    """
    List public repositories within the organization.

    .. versionadded:: 2016.11.0

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_public_repos
        salt myminion github.list_public_repos profile='my-github-profile'
    """
    repos = []
    for repo in _get_repos(profile):
        if repo.private is False:
            repos.append(repo.name)
    return repos


def add_repo(
    name,
    description=None,
    homepage=None,
    private=None,
    has_issues=None,
    has_wiki=None,
    has_downloads=None,
    auto_init=None,
    gitignore_template=None,
    license_template=None,
    profile="github",
):
    """
    Create a new github repository.

    name
        The name of the team to be created.

    description
        The description of the repository.

    homepage
        The URL with more information about the repository.

    private
        The visiblity of the repository. Note that private repositories require
        a paid GitHub account.

    has_issues
        Whether to enable issues for this repository.

    has_wiki
        Whether to enable the wiki for this repository.

    has_downloads
        Whether to enable downloads for this repository.

    auto_init
        Whether to create an initial commit with an empty README.

    gitignore_template
        The desired language or platform for a .gitignore, e.g "Haskell".

    license_template
        The desired LICENSE template to apply, e.g "mit" or "mozilla".

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.add_repo 'repo_name'

    .. versionadded:: 2016.11.0
    """
    try:
        client = _get_client(profile)
        organization = client.get_organization(_get_config_value(profile, "org_name"))
        given_params = {
            "description": description,
            "homepage": homepage,
            "private": private,
            "has_issues": has_issues,
            "has_wiki": has_wiki,
            "has_downloads": has_downloads,
            "auto_init": auto_init,
            "gitignore_template": gitignore_template,
            "license_template": license_template,
        }
        parameters = {"name": name}
        for param_name, param_value in given_params.items():
            if param_value is not None:
                parameters[param_name] = param_value

        organization._requester.requestJsonAndCheck(
            "POST", organization.url + "/repos", input=parameters
        )
        return True
    except github.GithubException:
        log.exception("Error creating a repo")
        return False


def edit_repo(
    name,
    description=None,
    homepage=None,
    private=None,
    has_issues=None,
    has_wiki=None,
    has_downloads=None,
    profile="github",
):
    """
    Updates an existing Github repository.

    name
        The name of the team to be created.

    description
        The description of the repository.

    homepage
        The URL with more information about the repository.

    private
        The visiblity of the repository. Note that private repositories require
        a paid GitHub account.

    has_issues
        Whether to enable issues for this repository.

    has_wiki
        Whether to enable the wiki for this repository.

    has_downloads
        Whether to enable downloads for this repository.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.add_repo 'repo_name'

    .. versionadded:: 2016.11.0
    """

    try:
        allow_private_change = _get_config_value(profile, "allow_repo_privacy_changes")
    except CommandExecutionError:
        allow_private_change = False

    if private is not None and not allow_private_change:
        raise CommandExecutionError(
            "The private field is set to be changed for "
            "repo {} but allow_repo_privacy_changes "
            "disallows this.".format(name)
        )

    try:
        client = _get_client(profile)
        organization = client.get_organization(_get_config_value(profile, "org_name"))
        repo = organization.get_repo(name)

        given_params = {
            "description": description,
            "homepage": homepage,
            "private": private,
            "has_issues": has_issues,
            "has_wiki": has_wiki,
            "has_downloads": has_downloads,
        }
        parameters = {"name": name}
        for param_name, param_value in given_params.items():
            if param_value is not None:
                parameters[param_name] = param_value

        organization._requester.requestJsonAndCheck("PATCH", repo.url, input=parameters)
        get_repo_info(name, profile=profile, ignore_cache=True)  # Refresh cache
        return True
    except github.GithubException:
        log.exception("Error editing a repo")
        return False


def remove_repo(name, profile="github"):
    """
    Remove a Github repository.

    name
        The name of the repository to be removed.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_repo 'my-repo'

    .. versionadded:: 2016.11.0
    """
    repo_info = get_repo_info(name, profile=profile)
    if not repo_info:
        log.error("Repo %s to be removed does not exist.", name)
        return False
    try:
        client = _get_client(profile)
        organization = client.get_organization(_get_config_value(profile, "org_name"))
        repo = organization.get_repo(name)
        repo.delete()
        _get_repos(profile=profile, ignore_cache=True)  # refresh cache
        return True
    except github.GithubException:
        log.exception("Error deleting a repo")
        return False


def get_team(name, profile="github"):
    """
    Returns the team details if a team with the given name exists, or None
    otherwise.

    name
        The team name for which to obtain information.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_team 'team_name'
    """
    return list_teams(profile).get(name)


def add_team(
    name,
    description=None,
    repo_names=None,
    privacy=None,
    permission=None,
    profile="github",
):
    """
    Create a new Github team within an organization.

    name
        The name of the team to be created.

    description
        The description of the team.

    repo_names
        The names of repositories to add the team to.

    privacy
        The level of privacy for the team, can be 'secret' or 'closed'.

    permission
        The default permission for new repositories added to the team, can be
        'pull', 'push' or 'admin'.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.add_team 'team_name'

    .. versionadded:: 2016.11.0
    """
    try:
        client = _get_client(profile)
        organization = client.get_organization(_get_config_value(profile, "org_name"))
        parameters = {}
        parameters["name"] = name

        if description is not None:
            parameters["description"] = description
        if repo_names is not None:
            parameters["repo_names"] = repo_names
        if permission is not None:
            parameters["permission"] = permission
        if privacy is not None:
            parameters["privacy"] = privacy

        organization._requester.requestJsonAndCheck(
            "POST", organization.url + "/teams", input=parameters
        )
        list_teams(ignore_cache=True)  # Refresh cache
        return True
    except github.GithubException:
        log.exception("Error creating a team")
        return False


def edit_team(name, description=None, privacy=None, permission=None, profile="github"):
    """
    Updates an existing Github team.

    name
        The name of the team to be edited.

    description
        The description of the team.

    privacy
        The level of privacy for the team, can be 'secret' or 'closed'.

    permission
        The default permission for new repositories added to the team, can be
        'pull', 'push' or 'admin'.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.edit_team 'team_name' description='Team description'

    .. versionadded:: 2016.11.0
    """
    team = get_team(name, profile=profile)
    if not team:
        log.error("Team %s does not exist", name)
        return False
    try:
        client = _get_client(profile)
        organization = client.get_organization(_get_config_value(profile, "org_name"))
        team = organization.get_team(team["id"])

        parameters = {}
        if name is not None:
            parameters["name"] = name
        if description is not None:
            parameters["description"] = description
        if privacy is not None:
            parameters["privacy"] = privacy
        if permission is not None:
            parameters["permission"] = permission

        team._requester.requestJsonAndCheck("PATCH", team.url, input=parameters)
        return True
    except UnknownObjectException:
        log.exception("Resource not found")
        return False


def remove_team(name, profile="github"):
    """
    Remove a github team.

    name
        The name of the team to be removed.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_team 'team_name'

    .. versionadded:: 2016.11.0
    """
    team_info = get_team(name, profile=profile)
    if not team_info:
        log.error("Team %s to be removed does not exist.", name)
        return False
    try:
        client = _get_client(profile)
        organization = client.get_organization(_get_config_value(profile, "org_name"))
        team = organization.get_team(team_info["id"])
        team.delete()
        return list_teams(ignore_cache=True, profile=profile).get(name) is None
    except github.GithubException:
        log.exception("Error deleting a team")
        return False


def list_team_repos(team_name, profile="github", ignore_cache=False):
    """
    Gets the repo details for a given team as a dict from repo_name to repo details.
    Note that repo names are always in lower case.

    team_name
        The name of the team from which to list repos.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached team repos.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_team_repos 'team_name'

    .. versionadded:: 2016.11.0
    """
    cached_team = get_team(team_name, profile=profile)
    if not cached_team:
        log.error("Team %s does not exist.", team_name)
        return False

    # Return from cache if available
    if cached_team.get("repos") and not ignore_cache:
        return cached_team.get("repos")

    try:
        client = _get_client(profile)
        organization = client.get_organization(_get_config_value(profile, "org_name"))
        team = organization.get_team(cached_team["id"])
    except UnknownObjectException:
        log.exception("Resource not found: %s", cached_team["id"])
    try:
        repos = {}
        for repo in team.get_repos():
            permission = "pull"
            if repo.permissions.admin:
                permission = "admin"
            elif repo.permissions.push:
                permission = "push"

            repos[repo.name.lower()] = {"permission": permission}
        cached_team["repos"] = repos
        return repos
    except UnknownObjectException:
        log.exception("Resource not found: %s", cached_team["id"])
        return []


def add_team_repo(repo_name, team_name, profile="github", permission=None):
    """
    Adds a repository to a team with team_name.

    repo_name
        The name of the repository to add.

    team_name
        The name of the team of which to add the repository.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    permission
        The permission for team members within the repository, can be 'pull',
        'push' or 'admin'. If not specified, the default permission specified on
        the team will be used.

        .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt myminion github.add_team_repo 'my_repo' 'team_name'

    .. versionadded:: 2016.11.0
    """
    team = get_team(team_name, profile=profile)
    if not team:
        log.error("Team %s does not exist", team_name)
        return False
    try:
        client = _get_client(profile)
        organization = client.get_organization(_get_config_value(profile, "org_name"))
        team = organization.get_team(team["id"])
        repo = organization.get_repo(repo_name)
    except UnknownObjectException:
        log.exception("Resource not found: %s", team["id"])
        return False
    params = None
    if permission is not None:
        params = {"permission": permission}

    headers, data = team._requester.requestJsonAndCheck(
        "PUT", team.url + "/repos/" + repo._identity, input=params
    )
    # Try to refresh cache
    list_team_repos(team_name, profile=profile, ignore_cache=True)
    return True


def remove_team_repo(repo_name, team_name, profile="github"):
    """
    Removes a repository from a team with team_name.

    repo_name
        The name of the repository to remove.

    team_name
        The name of the team of which to remove the repository.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_team_repo 'my_repo' 'team_name'

    .. versionadded:: 2016.11.0
    """
    team = get_team(team_name, profile=profile)
    if not team:
        log.error("Team %s does not exist", team_name)
        return False
    try:
        client = _get_client(profile)
        organization = client.get_organization(_get_config_value(profile, "org_name"))
        team = organization.get_team(team["id"])
        repo = organization.get_repo(repo_name)
    except UnknownObjectException:
        log.exception("Resource not found: %s", team["id"])
        return False
    team.remove_from_repos(repo)
    return repo_name not in list_team_repos(
        team_name, profile=profile, ignore_cache=True
    )


def list_team_members(team_name, profile="github", ignore_cache=False):
    """
    Gets the names of team members in lower case.

    team_name
        The name of the team from which to list members.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached team members.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_team_members 'team_name'

    .. versionadded:: 2016.11.0
    """
    cached_team = get_team(team_name, profile=profile)
    if not cached_team:
        log.error("Team %s does not exist.", team_name)
        return False
    # Return from cache if available
    if cached_team.get("members") and not ignore_cache:
        return cached_team.get("members")

    try:
        client = _get_client(profile)
        organization = client.get_organization(_get_config_value(profile, "org_name"))
        team = organization.get_team(cached_team["id"])
    except UnknownObjectException:
        log.exception("Resource not found: %s", cached_team["id"])
    try:
        cached_team["members"] = [member.login.lower() for member in team.get_members()]
        return cached_team["members"]
    except UnknownObjectException:
        log.exception("Resource not found: %s", cached_team["id"])
        return []


def list_members_without_mfa(profile="github", ignore_cache=False):
    """
    List all members (in lower case) without MFA turned on.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached team repos.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_members_without_mfa

    .. versionadded:: 2016.11.0
    """
    key = "github.{}:non_mfa_users".format(_get_config_value(profile, "org_name"))

    if key not in __context__ or ignore_cache:
        client = _get_client(profile)
        organization = client.get_organization(_get_config_value(profile, "org_name"))

        filter_key = "filter"
        # Silly hack to see if we're past PyGithub 1.26.0, where the name of
        # the filter kwarg changed
        if hasattr(github.Team.Team, "membership"):
            filter_key = "filter_"

        __context__[key] = [
            m.login.lower()
            for m in _get_members(organization, {filter_key: "2fa_disabled"})
        ]
    return __context__[key]


def is_team_member(name, team_name, profile="github"):
    """
    Returns True if the github user is in the team with team_name, or False
    otherwise.

    name
        The name of the user whose membership to check.

    team_name
        The name of the team to check membership in.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.is_team_member 'user_name' 'team_name'

    .. versionadded:: 2016.11.0
    """
    return name.lower() in list_team_members(team_name, profile=profile)


def add_team_member(name, team_name, profile="github"):
    """
    Adds a team member to a team with team_name.

    name
        The name of the team member to add.

    team_name
        The name of the team of which to add the user.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.add_team_member 'user_name' 'team_name'

    .. versionadded:: 2016.11.0
    """
    team = get_team(team_name, profile=profile)
    if not team:
        log.error("Team %s does not exist", team_name)
        return False
    try:
        client = _get_client(profile)
        organization = client.get_organization(_get_config_value(profile, "org_name"))
        team = organization.get_team(team["id"])
        member = client.get_user(name)
    except UnknownObjectException:
        log.exception("Resource not found: %s", team["id"])
        return False

    try:
        # Can't use team.add_membership due to this bug that hasn't made it into
        # a PyGithub release yet https://github.com/PyGithub/PyGithub/issues/363
        headers, data = team._requester.requestJsonAndCheck(
            "PUT",
            team.url + "/memberships/" + member._identity,
            input={"role": "member"},
            parameters={"role": "member"},
        )
    except github.GithubException:
        log.exception("Error in adding a member to a team")
        return False
    return True


def remove_team_member(name, team_name, profile="github"):
    """
    Removes a team member from a team with team_name.

    name
        The name of the team member to remove.

    team_name
        The name of the team from which to remove the user.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_team_member 'user_name' 'team_name'

    .. versionadded:: 2016.11.0
    """
    team = get_team(team_name, profile=profile)
    if not team:
        log.error("Team %s does not exist", team_name)
        return False
    try:
        client = _get_client(profile)
        organization = client.get_organization(_get_config_value(profile, "org_name"))
        team = organization.get_team(team["id"])
        member = client.get_user(name)

    except UnknownObjectException:
        log.exception("Resource not found: %s", team["id"])
        return False

    if not hasattr(team, "remove_from_members"):
        return (
            False,
            "PyGithub 1.26.0 or greater is required for team "
            "management, please upgrade.",
        )

    team.remove_from_members(member)
    return not team.has_in_members(member)


def list_teams(profile="github", ignore_cache=False):
    """
    Lists all teams with the organization.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached teams.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_teams

    .. versionadded:: 2016.11.0
    """
    key = "github.{}:teams".format(_get_config_value(profile, "org_name"))

    if key not in __context__ or ignore_cache:
        client = _get_client(profile)
        organization = client.get_organization(_get_config_value(profile, "org_name"))
        teams_data = organization.get_teams()
        teams = {}
        for team in teams_data:
            # Note that _rawData is used to access some properties here as they
            # are not exposed in older versions of PyGithub. It's VERY important
            # to use team._rawData instead of team.raw_data, as the latter forces
            # an API call to retrieve team details again.
            teams[team.name] = {
                "id": team.id,
                "slug": team.slug,
                "description": team._rawData["description"],
                "permission": team.permission,
                "privacy": team._rawData["privacy"],
            }
        __context__[key] = teams

    return __context__[key]


def get_prs(
    repo_name=None,
    profile="github",
    state="open",
    head=None,
    base=None,
    sort="created",
    direction="desc",
    output="min",
    per_page=None,
):
    """
    Returns information for all pull requests in a given repository, based on
    the search options provided.

    .. versionadded:: 2017.7.0

    repo_name
        The name of the repository for which to list pull requests. This
        argument is required, either passed via the CLI, or defined in the
        configured profile. A ``repo_name`` passed as a CLI argument will
        override the ``repo_name`` defined in the configured profile, if
        provided.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    state
        Indicates the state of the pull requests to return. Can be either
        ``open``, ``closed``, or ``all``. Default is ``open``.

    head
        Filter pull requests by head user and branch name in the format of
        ``user:ref-name``. Example: ``'github:new-script-format'``. Default
        is ``None``.

    base
        Filter pulls by base branch name. Example: ``gh-pages``. Default is
        ``None``.

    sort
        What to sort results by. Can be either ``created``, ``updated``,
        ``popularity`` (comment count), or ``long-running`` (age, filtering
        by pull requests updated within the last month). Default is ``created``.

    direction
        The direction of the sort. Can be either ``asc`` or ``desc``. Default
        is ``desc``.

    output
        The amount of data returned by each pull request. Defaults to ``min``.
        Change to ``full`` to see all pull request output.

    per_page
        GitHub paginates data in their API calls. Use this value to increase or
        decrease the number of pull requests gathered from GitHub, per page. If
        not set, GitHub defaults are used. Maximum is 100.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_prs
        salt myminion github.get_prs base=2016.11
    """
    org_name = _get_config_value(profile, "org_name")
    if repo_name is None:
        repo_name = _get_config_value(profile, "repo_name")

    action = "/".join(["repos", org_name, repo_name])
    args = {}

    # Build API arguments, as necessary.
    if head:
        args["head"] = head
    if base:
        args["base"] = base
    if per_page:
        args["per_page"] = per_page

    # Only pass the following API args if they're not the defaults listed.
    if state and state != "open":
        args["state"] = state
    if sort and sort != "created":
        args["sort"] = sort
    if direction and direction != "desc":
        args["direction"] = direction

    ret = {}
    prs = _query(profile, action=action, command="pulls", args=args)

    for pr_ in prs:
        pr_id = pr_.get("id")
        if output == "full":
            ret[pr_id] = pr_
        else:
            ret[pr_id] = _format_pr(pr_)

    return ret


def _format_pr(pr_):
    """
    Helper function to format API return information into a more manageable
    and useful dictionary for pull request information.

    pr_
        The pull request to format.
    """
    ret = {
        "id": pr_.get("id"),
        "pr_number": pr_.get("number"),
        "state": pr_.get("state"),
        "title": pr_.get("title"),
        "user": pr_.get("user").get("login"),
        "html_url": pr_.get("html_url"),
        "base_branch": pr_.get("base").get("ref"),
    }

    return ret


def _format_issue(issue):
    """
    Helper function to format API return information into a more manageable
    and useful dictionary for issue information.

    issue
        The issue to format.
    """
    ret = {
        "id": issue.get("id"),
        "issue_number": issue.get("number"),
        "state": issue.get("state"),
        "title": issue.get("title"),
        "user": issue.get("user").get("login"),
        "html_url": issue.get("html_url"),
    }

    assignee = issue.get("assignee")
    if assignee:
        assignee = assignee.get("login")

    labels = issue.get("labels")
    label_names = []
    for label in labels:
        label_names.append(label.get("name"))

    milestone = issue.get("milestone")
    if milestone:
        milestone = milestone.get("title")

    ret["assignee"] = assignee
    ret["labels"] = label_names
    ret["milestone"] = milestone

    return ret


def _query(
    profile,
    action=None,
    command=None,
    args=None,
    method="GET",
    header_dict=None,
    data=None,
    url="https://api.github.com/",
    per_page=None,
):
    """
    Make a web call to the GitHub API and deal with paginated results.
    """
    if not isinstance(args, dict):
        args = {}

    if action:
        url += action

    if command:
        url += f"/{command}"

    log.debug("GitHub URL: %s", url)

    if "access_token" not in args.keys():
        args["access_token"] = _get_config_value(profile, "token")
    if per_page and "per_page" not in args.keys():
        args["per_page"] = per_page

    if header_dict is None:
        header_dict = {}

    if method != "POST":
        header_dict["Accept"] = "application/json"

    decode = True
    if method == "DELETE":
        decode = False

    # GitHub paginates all queries when returning many items.
    # Gather all data using multiple queries and handle pagination.
    complete_result = []
    next_page = True
    page_number = ""
    while next_page is True:
        if page_number:
            args["page"] = page_number
        result = salt.utils.http.query(
            url,
            method,
            params=args,
            data=data,
            header_dict=header_dict,
            decode=decode,
            decode_type="json",
            headers=True,
            status=True,
            text=True,
            hide_fields=["access_token"],
            opts=__opts__,
        )
        log.debug("GitHub Response Status Code: %s", result["status"])

        if result["status"] == 200:
            if isinstance(result["dict"], dict):
                # If only querying for one item, such as a single issue
                # The GitHub API returns a single dictionary, instead of
                # A list of dictionaries. In that case, we can return.
                return result["dict"]

            complete_result = complete_result + result["dict"]
        else:
            raise CommandExecutionError(
                "GitHub Response Error: {}".format(result.get("error"))
            )

        try:
            link_info = result.get("headers").get("Link").split(",")[0]
        except AttributeError:
            # Only one page of data was returned; exit the loop.
            next_page = False
            continue

        if "next" in link_info:
            # Get the 'next' page number from the Link header.
            page_number = link_info.split(">")[0].split("&page=")[1]
        else:
            # Last page already processed; break the loop.
            next_page = False

    return complete_result
