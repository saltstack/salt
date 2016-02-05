# -*- coding: utf-8 -*-
'''
Module for interop with the Github v3 API

.. versionadded:: 2016.3.0.

:depends:   - PyGithub python module
:configuration: Configure this module by specifying the name of a configuration
    profile in the minion config, minion pillar, or master config. The module
    will use the 'github' key by default, if defined.

    For example:

    .. code-block:: yaml

        github:
            token: abc1234
'''
from __future__ import absolute_import

# Import python libs
import logging

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
    Only load this module if github is installed on this minion.
    '''
    if HAS_LIBS:
        return __virtualname__
    return (False, 'The github execution module cannot be loaded: '
            'python github library is not installed.')


def _get_secret_key(profile):
    config = __salt__['config.option'](profile)
    return config.get('token')


def _get_org_name(profile):
    config = __salt__['config.option'](profile)
    return config.get('org_name')


def _get_dev_team_id(profile):
    config = __salt__['config.option'](profile)
    return config.get('dev_team_id')


def _get_client(profile):
    '''
    Return the github client, cached into __context__ for performance
    '''
    config = __salt__['config.option'](profile)

    key = "github.{0}:{1}".format(
        config.get('token'),
        config.get('org_name')
    )

    if key not in __context__:
        __context__[key] = github.Github(
            config.get('token')
        )
    return __context__[key]


def _get_members(organization, params=None):
    return github.PaginatedList.PaginatedList(
        github.NamedUser.NamedUser,
        organization._requester,
        organization.url + "/members",
        params
    )


def list_users(profile="github"):
    '''
    List all users

    CLI Example:

        salt myminion github.list_users
    '''
    key = "github.{0}:users".format(
        _get_org_name(profile)
    )

    if key not in __context__:
        client = _get_client(profile)
        organization = client.get_organization(_get_org_name(profile))

        users = [member.login for member in _get_members(organization, None)]
        __context__[key] = users

    return __context__[key]


def get_user(name, profile="github", **kwargs):
    '''
    Get a github user by name

    CLI Example:

        salt myminion github.get_user 'github-handle' user_details=false
        salt myminion github.get_user 'github-handle' user_details=true

    '''

    if not kwargs.get('user_details', False) and name in list_users(profile):
        # User is in the org, no need for additional Data
        return True

    response = {}
    client = _get_client(profile)
    organization = client.get_organization(_get_org_name(profile))

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


def add_user(name, profile="github", **kwargs):
    '''
    Add a github user

    CLI Example:

        salt myminion github.add_user 'github-handle'
    '''

    client = _get_client(profile)
    organization = client.get_organization(_get_org_name(profile))

    try:
        github_named_user = client.get_user(name)
    except UnknownObjectException as e:
        logging.exception("Resource not found {0}: ".format(str(e)))
        return False

    org_team = organization.get_team(_get_dev_team_id(profile))

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


def remove_user(name, profile="github", **kwargs):
    '''
    remove a Github user by name

    CLI Example:

        salt myminion github.remove_user github-handle
    '''

    client = _get_client(profile)
    organization = client.get_organization(_get_org_name(profile))

    try:
        git_user = client.get_user(name)
    except UnknownObjectException as e:
        logging.exception("Resource not found: {0}".format(str(e)))
        return False

    if organization.has_in_members(git_user):
        organization.remove_from_members(git_user)

    return not organization.has_in_members(git_user)
