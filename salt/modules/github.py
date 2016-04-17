# -*- coding: utf-8 -*-
'''
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

      # optional: only some functions, such as 'add_user',
      # require a dev_team_id.
      dev_team_id: 1234
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt Libs
from salt.exceptions import CommandExecutionError
import salt.utils.http

# Import third party libs
HAS_LIBS = False
try:
    import github
    import github.PaginatedList
    import github.NamedUser
    from github.GithubException import UnknownObjectException

    HAS_LIBS = True
except ImportError:
    pass

log = logging.getLogger(__name__)

__virtualname__ = 'github'


def __virtual__():
    '''
    Only load this module if PyGithub is installed on this minion.
    '''
    if HAS_LIBS:
        return __virtualname__
    return (False, 'The github execution module cannot be loaded: '
            'PyGithub library is not installed.')


def _get_config_value(profile, config_name):
    '''
    Helper function that returns a profile's configuration value based on
    the supplied configuration name.

    profile
        The profile name that contains configuration information.

    config_name
        The configuration item's name to use to return configuration values.
    '''
    config = __salt__['config.option'](profile)
    if not config:
        raise CommandExecutionError(
            'Authentication information could not be found for the '
            '\'{0}\' profile.'.format(profile)
        )

    config_value = config.get(config_name)
    if not config_value:
        raise CommandExecutionError(
            'The \'{0}\' parameter was not found in the \'{1}\' '
            'profile.'.format(
                config_name,
                profile
            )
        )

    return config_value


def _get_client(profile):
    '''
    Return the GitHub client, cached into __context__ for performance
    '''
    token = _get_config_value(profile, 'token')
    key = 'github.{0}:{1}'.format(
        token,
        _get_config_value(profile, 'org_name')
    )

    if key not in __context__:
        __context__[key] = github.Github(
            token,
        )
    return __context__[key]


def _get_members(organization, params=None):
    return github.PaginatedList.PaginatedList(
        github.NamedUser.NamedUser,
        organization._requester,
        organization.url + "/members",
        params
    )


def _get_repos(profile, params=None):
    org_name = _get_config_value(profile, 'org_name')
    client = _get_client(profile)
    organization = client.get_organization(org_name)

    return github.PaginatedList.PaginatedList(
        github.Repository.Repository,
        organization._requester,
        organization.url + '/repos',
        params
    )


def list_users(profile="github"):
    '''
    List all users within the organization.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_users
        salt myminion github.list_users profile='my-github-profile'
    '''
    org_name = _get_config_value(profile, 'org_name')
    key = "github.{0}:users".format(
        org_name
    )

    if key not in __context__:
        client = _get_client(profile)
        organization = client.get_organization(org_name)

        users = [member.login for member in _get_members(organization, None)]
        __context__[key] = users

    return __context__[key]


def get_user(name, profile='github', user_details=False):
    '''
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

    '''

    if not user_details and name in list_users(profile):
        # User is in the org, no need for additional Data
        return True

    response = {}
    client = _get_client(profile)
    organization = client.get_organization(
        _get_config_value(profile, 'org_name')
    )

    try:
        user = client.get_user(name)
    except UnknownObjectException as e:
        logging.exception("Resource not found {0}: ".format(str(e)))
        return False

    response['company'] = user.company
    response['created_at'] = user.created_at
    response['email'] = user.email
    response['html_url'] = user.html_url
    response['id'] = user.id
    response['login'] = user.login
    response['name'] = user.name
    response['type'] = user.type
    response['url'] = user.url

    try:
        headers, data = organization._requester.requestJsonAndCheck(
            "GET",
            organization.url + "/memberships/" + user._identity
        )
    except UnknownObjectException as e:
        response['membership_state'] = 'nonexistent'
        response['in_org'] = False
        return response

    response['in_org'] = organization.has_in_members(user)
    response['membership_state'] = data.get('state')

    return response


def add_user(name, profile='github'):
    '''
    Add a GitHub user.

    name
        The user for which to obtain information.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.add_user github-handle
    '''

    client = _get_client(profile)
    organization = client.get_organization(
        _get_config_value(profile, 'org_name')
    )

    try:
        github_named_user = client.get_user(name)
    except UnknownObjectException as e:
        logging.exception("Resource not found {0}: ".format(str(e)))
        return False

    org_team = organization.get_team(
        _get_config_value(profile, 'dev_team_id')
    )

    try:
        headers, data = org_team._requester.requestJsonAndCheck(
            "PUT",
            org_team.url + "/memberships/" + github_named_user._identity,
            input={'role': 'member'},
            parameters={'role': 'member'}
        )
    except github.GithubException as e:
        logging.error(str(e))
        return True

    headers, data = organization._requester.requestJsonAndCheck(
        "GET",
        organization.url + "/memberships/" + github_named_user._identity
    )

    return data.get('state') == 'pending'


def remove_user(name, profile='github'):
    '''
    Remove a Github user by name.

    name
        The user for which to obtain information.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_user github-handle
    '''

    client = _get_client(profile)
    organization = client.get_organization(
        _get_config_value(profile, 'org_name')
    )

    try:
        git_user = client.get_user(name)
    except UnknownObjectException as e:
        logging.exception("Resource not found: {0}".format(str(e)))
        return False

    if organization.has_in_members(git_user):
        organization.remove_from_members(git_user)

    return not organization.has_in_members(git_user)


def get_issue(issue_number, repo_name=None, profile='github', output='min'):
    '''
    Return information about a single issue in a named repository.

    .. versionadded:: Carbon

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
    '''
    org_name = _get_config_value(profile, 'org_name')
    if repo_name is None:
        repo_name = _get_config_value(profile, 'repo_name')

    action = '/'.join(['repos', org_name, repo_name])
    command = 'issues/' + str(issue_number)

    ret = {}
    issue_data = _query(profile, action=action, command=command)

    issue_id = issue_data.get('id')
    if output == 'full':
        ret[issue_id] = issue_data
    else:
        ret[issue_id] = _format_issue(issue_data)

    return ret


def get_issue_comments(issue_number,
                       repo_name=None,
                       profile='github',
                       since=None,
                       output='min'):
    '''
    Return information about the comments for a given issue in a named repository.

    .. versionadded:: Carbon

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
    '''
    org_name = _get_config_value(profile, 'org_name')
    if repo_name is None:
        repo_name = _get_config_value(profile, 'repo_name')

    action = '/'.join(['repos', org_name, repo_name])
    command = '/'.join(['issues', str(issue_number), 'comments'])

    args = {}
    if since:
        args['since'] = since

    comments = _query(profile, action=action, command=command, args=args)

    ret = {}
    for comment in comments:
        comment_id = comment.get('id')
        if output == 'full':
            ret[comment_id] = comment
        else:
            ret[comment_id] = {'id': comment.get('id'),
                               'created_at': comment.get('created_at'),
                               'updated_at': comment.get('updated_at'),
                               'user_login': comment.get('user').get('login')}
    return ret


def get_issues(repo_name=None,
               profile='github',
               milestone=None,
               state='open',
               assignee=None,
               creator=None,
               mentioned=None,
               labels=None,
               sort='created',
               direction='desc',
               since=None,
               output='min',
               per_page=None):
    '''
    Returns information for all issues in a given repository, based on the search options.

    .. versionadded:: Carbon

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
    '''
    org_name = _get_config_value(profile, 'org_name')
    if repo_name is None:
        repo_name = _get_config_value(profile, 'repo_name')

    action = '/'.join(['repos', org_name, repo_name])
    args = {}

    # Build API arguments, as necessary.
    if milestone:
        args['milestone'] = milestone
    if assignee:
        args['assignee'] = assignee
    if creator:
        args['creator'] = creator
    if mentioned:
        args['mentioned'] = mentioned
    if labels:
        args['labels'] = labels
    if since:
        args['since'] = since
    if per_page:
        args['per_page'] = per_page

    # Only pass the following API args if they're not the defaults listed.
    if state and state != 'open':
        args['state'] = state
    if sort and sort != 'created':
        args['sort'] = sort
    if direction and direction != 'desc':
        args['direction'] = direction

    ret = {}
    issues = _query(profile, action=action, command='issues', args=args)

    for issue in issues:
        # Pull requests are included in the issue list from GitHub
        # Let's not include those in the return.
        if issue.get('pull_request'):
            continue
        issue_id = issue.get('id')
        if output == 'full':
            ret[issue_id] = issue
        else:
            ret[issue_id] = _format_issue(issue)

    return ret


def get_milestones(repo_name=None,
                   profile='github',
                   state='open',
                   sort='due_on',
                   direction='asc',
                   output='min',
                   per_page=None):
    '''
    Return information about milestones for a given repository.

    .. versionadded:: Carbon

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

    '''
    org_name = _get_config_value(profile, 'org_name')
    if repo_name is None:
        repo_name = _get_config_value(profile, 'repo_name')

    action = '/'.join(['repos', org_name, repo_name])
    args = {}

    if per_page:
        args['per_page'] = per_page

    # Only pass the following API args if they're not the defaults listed.
    if state and state != 'open':
        args['state'] = state
    if sort and sort != 'due_on':
        args['sort'] = sort
    if direction and direction != 'asc':
        args['direction'] = direction

    ret = {}
    milestones = _query(profile, action=action, command='milestones', args=args)

    for milestone in milestones:
        milestone_id = milestone.get('id')
        if output == 'full':
            ret[milestone_id] = milestone
        else:
            milestone.pop('creator')
            milestone.pop('html_url')
            milestone.pop('labels_url')
            ret[milestone_id] = milestone

    return ret


def get_milestone(number=None,
                  name=None,
                  repo_name=None,
                  profile='github',
                  output='min'):
    '''
    Return information about a single milestone in a named repository.

    .. versionadded:: Carbon

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

    '''
    ret = {}

    if not any([number, name]):
        raise CommandExecutionError(
            'Either a milestone \'name\' or \'number\' must be provided.'
        )

    org_name = _get_config_value(profile, 'org_name')
    if repo_name is None:
        repo_name = _get_config_value(profile, 'repo_name')

    action = '/'.join(['repos', org_name, repo_name])
    if number:
        command = 'milestones/' + str(number)
        milestone_data = _query(profile, action=action, command=command)
        milestone_id = milestone_data.get('id')
        if output == 'full':
            ret[milestone_id] = milestone_data
        else:
            milestone_data.pop('creator')
            milestone_data.pop('html_url')
            milestone_data.pop('labels_url')
            ret[milestone_id] = milestone_data
        return ret

    else:
        milestones = get_milestones(repo_name=repo_name, profile=profile, output=output)
        for key, val in milestones.iteritems():
            if val.get('title') == name:
                ret[key] = val
                return ret

    return ret


def get_repo_info(repo_name, profile='github'):
    '''
    Return information for a given repo.

    .. versionadded:: Carbon

    repo_name
        The name of repository.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_repo_info salt
        salt myminion github.get_repo_info salt profile='my-github-profile'
    '''
    ret = {}
    org_name = _get_config_value(profile, 'org_name')
    client = _get_client(profile)

    repo = client.get_repo('/'.join([org_name, repo_name]))
    if repo:
        # client.get_repo will return a github.Repository.Repository object,
        # even if the repo is invalid. We need to catch the exception when
        # we try to perform actions on the repo object, rather than above
        # the if statement.
        try:
            ret['id'] = repo.id
        except github.UnknownObjectException:
            raise CommandExecutionError(
                'The \'{0}\' repository under the \'{1}\' organization could not '
                'be found.'.format(
                    repo_name,
                    org_name
                )
            )
        ret['name'] = repo.name
        ret['full_name'] = repo.full_name
        ret['owner'] = repo.owner.login
        ret['private'] = repo.private
        ret['html_url'] = repo.html_url
        ret['description'] = repo.description
        ret['fork'] = repo.fork
        ret['homepage'] = repo.homepage
        ret['size'] = repo.size
        ret['stargazers_count'] = repo.stargazers_count
        ret['watchers_count'] = repo.watchers_count
        ret['language'] = repo.language
        ret['open_issues_count'] = repo.open_issues_count
        ret['forks'] = repo.forks
        ret['open_issues'] = repo.open_issues
        ret['watchers'] = repo.watchers
        ret['default_branch'] = repo.default_branch

    return ret


def list_repos(profile='github'):
    '''
    List all repositories within the organization. Includes public and private
    repositories within the organization Dependent upon the access rights of
    the profile token.

    .. versionadded:: Carbon

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    .. code-block:: bash

        salt myminion github.list_repos
        salt myminion github.list_repos profile='my-github-profile'
    '''
    return [repo.name for repo in _get_repos(profile)]


def list_private_repos(profile='github'):
    '''
    List private repositories within the organization. Dependent upon the access
    rights of the profile token.

    .. versionadded:: Carbon

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    .. code-block:: bash

        salt myminion github.list_private_repos
        salt myminion github.list_private_repos profile='my-github-profile'
    '''
    repos = []
    for repo in _get_repos(profile):
        if repo.private is True:
            repos.append(repo.name)
    return repos


def list_public_repos(profile='github'):
    '''
    List public repositories within the organization.

    .. versionadded:: Carbon

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    .. code-block:: bash

        salt myminion github.list_public_repos
        salt myminion github.list_public_repos profile='my-github-profile'
    '''
    repos = []
    for repo in _get_repos(profile):
        if repo.private is False:
            repos.append(repo.name)
    return repos


def _format_issue(issue):
    '''
    Helper function to format API return information into a more manageable
    and useful dictionary for issue information.

    issue
        The issue to format.
    '''
    ret = {'id': issue.get('id'),
           'issue_number': issue.get('number'),
           'state': issue.get('state'),
           'title': issue.get('title'),
           'user': issue.get('user').get('login'),
           'html_url': issue.get('html_url')}

    assignee = issue.get('assignee')
    if assignee:
        assignee = assignee.get('login')

    labels = issue.get('labels')
    label_names = []
    for label in labels:
        label_names.append(label.get('name'))

    milestone = issue.get('milestone')
    if milestone:
        milestone = milestone.get('title')

    ret['assignee'] = assignee
    ret['labels'] = label_names
    ret['milestone'] = milestone

    return ret


def _query(profile,
           action=None,
           command=None,
           args=None,
           method='GET',
           header_dict=None,
           data=None,
           url='https://api.github.com/',
           per_page=None):
    '''
    Make a web call to the GitHub API and deal with paginated results.
    '''
    if not isinstance(args, dict):
        args = {}

    if action:
        url += action

    if command:
        url += '/{0}'.format(command)

    log.debug('GitHub URL: {0}'.format(url))

    if 'access_token' not in args.keys():
        args['access_token'] = _get_config_value(profile, 'token')
    if per_page and 'per_page' not in args.keys():
        args['per_page'] = per_page

    if header_dict is None:
        header_dict = {}

    if method != 'POST':
        header_dict['Accept'] = 'application/json'

    decode = True
    if method == 'DELETE':
        decode = False

    # GitHub paginates all queries when returning many items.
    # Gather all data using multiple queries and handle pagination.
    complete_result = []
    next_page = True
    page_number = ''
    while next_page is True:
        if page_number:
            args['page'] = page_number
        result = salt.utils.http.query(url,
                                       method,
                                       params=args,
                                       data=data,
                                       header_dict=header_dict,
                                       decode=decode,
                                       decode_type='json',
                                       headers=True,
                                       status=True,
                                       text=True,
                                       hide_fields=['access_token'],
                                       opts=__opts__,
                                       )
        log.debug(
            'GitHub Response Status Code: {0}'.format(
                result['status']
            )
        )

        if result['status'] == 200:
            if isinstance(result['dict'], dict):
                # If only querying for one item, such as a single issue
                # The GitHub API returns a single dictionary, instead of
                # A list of dictionaries. In that case, we can return.
                return result['dict']

            complete_result = complete_result + result['dict']
        else:
            raise CommandExecutionError(
                'GitHub Response Error: {0}'.format(result.get('error'))
            )

        try:
            link_info = result.get('headers').get('Link').split(',')[0]
        except AttributeError:
            # Only one page of data was returned; exit the loop.
            next_page = False
            continue

        if 'next' in link_info:
            # Get the 'next' page number from the Link header.
            page_number = link_info.split('>')[0].split('&page=')[1]
        else:
            # Last page already processed; break the loop.
            next_page = False

    return complete_result
