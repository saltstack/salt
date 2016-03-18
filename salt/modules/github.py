# -*- coding: utf-8 -*-
'''
Module for interacting with the GitHub v3 API.

.. versionadded:: 2016.3.0.

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
      # optional: only some functions, such as 'add_user',
      # require a dev_team_id
      dev_team_id: 1234
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt Libs
from salt.exceptions import CommandExecutionError

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


def _get_profile(profile):
    config = __salt__['config.option'](profile)
    if not config:
        raise CommandExecutionError(
            'Authentication information could not be found for the '
            '\'{0}\' profile.'.format(profile)
        )
    return config


def _get_secret_key(profile):
    token = _get_profile(profile).get('token')
    if not token:
        raise CommandExecutionError(
            'The required \'token\' parameter was not found in the '
            '\'{0}\' profile.'.format(profile)
        )
    return token


def _get_org_name(profile):
    org_name = _get_profile(profile).get('org_name')
    if not org_name:
        raise CommandExecutionError(
            'The required \'org_name\' parameter was not found in the '
            '\'{0}\' profile.'.format(profile)
        )
    return org_name


def _get_dev_team_id(profile):
    dev_team_id = _get_profile(profile).get('dev_team_id')
    if not dev_team_id:
        raise CommandExecutionError(
            'The \'dev_team_id\' option was not found in the \'{0}\' '
            'profile.'.format(profile)
        )
    return dev_team_id


def _get_client(profile):
    '''
    Return the GitHub client, cached into __context__ for performance
    '''
    key = 'github.{0}:{1}'.format(
        _get_secret_key(profile),
        _get_org_name(profile)
    )

    if key not in __context__:
        __context__[key] = github.Github(
            _get_secret_key(profile),
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
    List all users within the organization.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_users
        salt myminion github.list_users profile='my-github-profile'
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
    organization = client.get_organization(_get_org_name(profile))

    try:
        git_user = client.get_user(name)
    except UnknownObjectException as e:
        logging.exception("Resource not found: {0}".format(str(e)))
        return False

    if organization.has_in_members(git_user):
        organization.remove_from_members(git_user)

    return not organization.has_in_members(git_user)
