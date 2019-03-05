# -*- coding: utf-8 -*-
'''
Github User State Module

.. versionadded:: 2016.3.0.

This state is used to ensure presence of users in the Organization.

.. code-block:: yaml

    ensure user test is present in github:
        github.present:
            - name: 'Example TestUser1'
            - email: example@domain.com
            - username: 'gitexample'
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import time
import datetime
import logging

# Import Salt Libs
from salt.ext import six
from salt.exceptions import CommandExecutionError
from salt.ext.six.moves import range


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if the github module is available in __salt__
    '''
    return 'github' if 'github.list_users' in __salt__ else False


def present(name, profile="github", **kwargs):
    '''
    Ensure a user is present

    .. code-block:: yaml

        ensure user test is present in github:
            github.present:
                - name: 'gitexample'

    The following parameters are required:

    name
        This is the github handle of the user in the organization
    '''

    ret = {
        'name': name,
        'changes': {},
        'result': None,
        'comment': ''
    }

    target = __salt__['github.get_user'](name, profile=profile, **kwargs)

    # If the user has a valid github handle and is not in the org already
    if not target:
        ret['result'] = False
        ret['comment'] = 'Couldnt find user {0}'.format(name)
    elif isinstance(target, bool) and target:
        ret['comment'] = 'User {0} is already in the org '.format(name)
        ret['result'] = True
    elif not target.get('in_org', False) and target.get('membership_state') != 'pending':
        if __opts__['test']:
            ret['comment'] = 'User {0} will be added to the org'.format(name)
            return ret

        # add the user
        result = __salt__['github.add_user'](
            name, profile=profile, **kwargs
        )

        if result:
            ret['changes'].setdefault('old', None)
            ret['changes'].setdefault('new', 'User {0} exists in the org now'.format(name))
            ret['result'] = True
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to add user {0} to the org'.format(name)
    else:
        ret['comment'] = 'User {0} has already been invited.'.format(name)
        ret['result'] = True

    return ret


def absent(name, profile="github", **kwargs):
    '''
    Ensure a github user is absent

    .. code-block:: yaml

        ensure user test is absent in github:
            github.absent:
                - name: 'Example TestUser1'
                - email: example@domain.com
                - username: 'gitexample'

    The following parameters are required:

    name
        Github handle of the user in organization

    '''
    email = kwargs.get('email')
    full_name = kwargs.get('fullname')

    ret = {
        'name': name,
        'changes': {},
        'result': None,
        'comment': 'User {0} is absent.'.format(name)
    }

    target = __salt__['github.get_user'](name, profile=profile, **kwargs)

    if target:
        if isinstance(target, bool) or target.get('in_org', False):
            if __opts__['test']:
                ret['comment'] = "User {0} will be deleted".format(name)
                ret['result'] = None
                return ret

            result = __salt__['github.remove_user'](name, profile=profile, **kwargs)

            if result:
                ret['comment'] = 'Deleted user {0}'.format(name)
                ret['changes'].setdefault('old', 'User {0} exists'.format(name))
                ret['changes'].setdefault('new', 'User {0} deleted'.format(name))
                ret['result'] = True
            else:
                ret['comment'] = 'Failed to delete {0}'.format(name)
                ret['result'] = False
        else:
            ret['comment'] = "User {0} has already been deleted!".format(name)
            ret['result'] = True
    else:
        ret['comment'] = 'User {0} does not exist'.format(name)
        ret['result'] = True
        return ret

    return ret


def team_present(
        name,
        description=None,
        repo_names=None,
        privacy='secret',
        permission='pull',
        members=None,
        enforce_mfa=False,
        no_mfa_grace_seconds=0,
        profile="github",
        **kwargs):
    '''
    Ensure a team is present

    name
        This is the name of the team in the organization.

    description
        The description of the team.

    repo_names
        The names of repositories to add the team to.

    privacy
        The level of privacy for the team, can be 'secret' or 'closed'. Defaults
        to secret.

    permission
        The default permission for new repositories added to the team, can be
        'pull', 'push' or 'admin'. Defaults to pull.

    members
        The members belonging to the team, specified as a dict of member name to
        optional configuration. Options include 'enforce_mfa_from' and 'mfa_exempt'.

    enforce_mfa
        Whether to enforce MFA requirements on members of the team. If True then
        all members without `mfa_exempt: True` configured will be removed from
        the team. Note that `no_mfa_grace_seconds` may be set to allow members
        a grace period.

    no_mfa_grace_seconds
        The number of seconds of grace time that a member will have to enable MFA
        before being removed from the team. The grace period will begin from
        `enforce_mfa_from` on the member configuration, which defaults to
        1970/01/01.

    Example:

    .. code-block:: yaml

        Ensure team test is present in github:
            github.team_present:
                - name: 'test'
                - members:
                    user1: {}
                    user2: {}

        Ensure team test_mfa is present in github:
            github.team_present:
                - name: 'test_mfa'
                - members:
                    user1:
                        enforce_mfa_from: 2016/06/15
                - enforce_mfa: True

    .. versionadded:: 2016.11.0
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': ''
    }

    target = __salt__['github.get_team'](name, profile=profile, **kwargs)
    test_comments = []

    if target:  # Team already exists
        parameters = {}
        if description is not None and target['description'] != description:
            parameters['description'] = description
        if permission is not None and target['permission'] != permission:
            parameters['permission'] = permission
        if privacy is not None and target['privacy'] != privacy:
            parameters['privacy'] = privacy

        if parameters:
            if __opts__['test']:
                test_comments.append('Team properties are set to be edited: {0}'
                                     .format(parameters))
                ret['result'] = None
            else:
                result = __salt__['github.edit_team'](name, profile=profile,
                                                      **parameters)
                if result:
                    ret['changes']['team'] = {
                        'old': 'Team properties were {0}'.format(target),
                        'new': 'Team properties (that changed) are {0}'.format(parameters)
                    }
                else:
                    ret['result'] = False
                    ret['comment'] = 'Failed to update team properties.'
                    return ret

        manage_repos = repo_names is not None
        current_repos = set(__salt__['github.list_team_repos'](name, profile=profile)
                            .keys())
        repo_names = set(repo_names or [])

        repos_to_add = repo_names - current_repos
        repos_to_remove = current_repos - repo_names if repo_names else []

        if repos_to_add:
            if __opts__['test']:
                test_comments.append('Team {0} will have the following repos '
                                     'added: {1}.'.format(name, list(repos_to_add)))
                ret['result'] = None
            else:
                for repo_name in repos_to_add:
                    result = (__salt__['github.add_team_repo']
                              (repo_name, name, profile=profile, **kwargs))
                    if result:
                        ret['changes'][repo_name] = {
                            'old': 'Repo {0} is not in team {1}'.format(repo_name, name),
                            'new': 'Repo {0} is in team {1}'.format(repo_name, name)
                        }
                    else:
                        ret['result'] = False
                        ret['comment'] = ('Failed to add repo {0} to team {1}.'
                                          .format(repo_name, name))
                        return ret

        if repos_to_remove:
            if __opts__['test']:
                test_comments.append('Team {0} will have the following repos '
                                     'removed: {1}.'.format(name, list(repos_to_remove)))
                ret['result'] = None
            else:
                for repo_name in repos_to_remove:
                    result = (__salt__['github.remove_team_repo']
                              (repo_name, name, profile=profile, **kwargs))
                    if result:
                        ret['changes'][repo_name] = {
                            'old': 'Repo {0} is in team {1}'.format(repo_name, name),
                            'new': 'Repo {0} is not in team {1}'.format(repo_name, name)
                        }
                    else:
                        ret['result'] = False
                        ret['comment'] = ('Failed to remove repo {0} from team {1}.'
                                          .format(repo_name, name))
                        return ret

    else:  # Team does not exist - it will be created.
        if __opts__['test']:
            ret['comment'] = 'Team {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret

        result = __salt__['github.add_team'](
            name,
            description=description,
            repo_names=repo_names,
            permission=permission,
            privacy=privacy,
            profile=profile,
            **kwargs
        )
        if result:
            ret['changes']['team'] = {}
            ret['changes']['team']['old'] = None
            ret['changes']['team']['new'] = 'Team {0} has been created'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create team {0}.'.format(name)
            return ret

    manage_members = members is not None

    mfa_deadline = datetime.datetime.utcnow() - datetime.timedelta(seconds=no_mfa_grace_seconds)
    members_no_mfa = __salt__['github.list_members_without_mfa'](profile=profile)

    members_lower = {}
    for member_name, info in six.iteritems(members or {}):
        members_lower[member_name.lower()] = info

    member_change = False
    current_members = __salt__['github.list_team_members'](name, profile=profile)

    for member, member_info in six.iteritems(members or {}):
        log.info('Checking member %s in team %s', member, name)

        if member.lower() not in current_members:
            if (enforce_mfa and _member_violates_mfa(member, member_info,
                                                     mfa_deadline, members_no_mfa)):
                if __opts__['test']:
                    test_comments.append('User {0} will not be added to the '
                                         'team because they do not have MFA.'
                                         ''.format(member))
            else:  # Add to team
                member_change = True
                if __opts__['test']:
                    test_comments.append('User {0} set to be added to the '
                                         'team.'.format(member))
                    ret['result'] = None
                else:
                    result = (__salt__['github.add_team_member']
                              (member, name, profile=profile, **kwargs))
                    if result:
                        ret['changes'][member] = {}
                        ret['changes'][member]['old'] = (
                            'User {0} is not in team {1}'.format(member, name))
                        ret['changes'][member]['new'] = (
                            'User {0} is in team {1}'.format(member, name))
                    else:
                        ret['result'] = False
                        ret['comment'] = ('Failed to add user {0} to team '
                                          '{1}.'.format(member, name))
                        return ret

    for member in current_members:
        mfa_violation = False
        if member in members_lower:
            mfa_violation = _member_violates_mfa(member, members_lower[member],
                                                 mfa_deadline, members_no_mfa)
        if (manage_members and member not in members_lower or
            (enforce_mfa and mfa_violation)):
            # Remove from team
            member_change = True
            if __opts__['test']:
                if mfa_violation:
                    test_comments.append('User {0} set to be removed from the '
                                         'team because they do not have MFA.'
                                         .format(member))
                else:
                    test_comments.append('User {0} set to be removed from '
                                         'the team.'.format(member))
                ret['result'] = None
            else:
                result = (__salt__['github.remove_team_member']
                          (member, name, profile=profile, **kwargs))
                if result:
                    extra_changes = ' due to MFA violation' if mfa_violation else ''
                    ret['changes'][member] = {
                        'old': 'User {0} is in team {1}'.format(member, name),
                        'new': 'User {0} is not in team {1}{2}'.format(member, name, extra_changes)
                    }
                else:
                    ret['result'] = False
                    ret['comment'] = ('Failed to remove user {0} from team {1}.'
                                      .format(member, name))
                    return ret

    if member_change:  # Refresh team cache
        __salt__['github.list_team_members'](name, profile=profile,
                                             ignore_cache=False, **kwargs)

    if test_comments:
        ret['comment'] = '\n'.join(test_comments)
    return ret


def _member_violates_mfa(member, member_info, mfa_deadline, members_without_mfa):
    if member_info.get('mfa_exempt', False):
        return False
    enforce_mfa_from = datetime.datetime.strptime(
        member_info.get('enforce_mfa_from', '1970/01/01'), '%Y/%m/%d')
    return member.lower() in members_without_mfa and (mfa_deadline > enforce_mfa_from)


def team_absent(name, profile="github", **kwargs):
    '''
    Ensure a team is absent.

    Example:

    .. code-block:: yaml

        ensure team test is present in github:
            github.team_absent:
                - name: 'test'


    The following parameters are required:

    name
        This is the name of the team in the organization.

    .. versionadded:: 2016.11.0
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': None,
        'comment': ''
    }

    target = __salt__['github.get_team'](name, profile=profile, **kwargs)

    if not target:
        ret['comment'] = 'Team {0} does not exist'.format(name)
        ret['result'] = True
        return ret
    else:
        if __opts__['test']:
            ret['comment'] = "Team {0} will be deleted".format(name)
            ret['result'] = None
            return ret

        result = __salt__['github.remove_team'](name, profile=profile, **kwargs)

        if result:
            ret['comment'] = 'Deleted team {0}'.format(name)
            ret['changes'].setdefault('old', 'Team {0} exists'.format(name))
            ret['changes'].setdefault('new', 'Team {0} deleted'.format(name))
            ret['result'] = True
        else:
            ret['comment'] = 'Failed to delete {0}'.format(name)
            ret['result'] = False
    return ret


def repo_present(
        name,
        description=None,
        homepage=None,
        private=None,
        has_issues=None,
        has_wiki=None,
        has_downloads=None,
        auto_init=False,
        gitignore_template=None,
        license_template=None,
        teams=None,
        profile="github",
        **kwargs):
    '''
    Ensure a repository is present

    name
        This is the name of the repository.

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

    teams
        The teams for which this repo should belong to, specified as a dict of
        team name to permission ('pull', 'push' or 'admin').

        .. versionadded:: 2017.7.0

    Example:

    .. code-block:: yaml

        Ensure repo my-repo is present in github:
            github.repo_present:
                - name: 'my-repo'
                - description: 'My very important repository'

    .. versionadded:: 2016.11.0
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': ''
    }

    # This is an optimization to cache all repos in the organization up front.
    # The first use of this state will collect all of the repos and save a bunch
    # of API calls for future use.
    __salt__['github.list_repos'](profile=profile)

    try:
        target = __salt__['github.get_repo_info'](name, profile=profile, **kwargs)
    except CommandExecutionError:
        target = None

    given_params = {
        'description': description,
        'homepage': homepage,
        'private': private,
        'has_issues': has_issues,
        'has_wiki': has_wiki,
        'has_downloads': has_downloads,
        'auto_init': auto_init,
        'gitignore_template': gitignore_template,
        'license_template': license_template
    }

    # Keep track of current_teams if we've fetched them after creating a new repo
    current_teams = None

    if target:  # Repo already exists
        # Some params are only valid on repo creation
        ignore_params = ['auto_init', 'gitignore_template', 'license_template']
        parameters = {}
        old_parameters = {}
        for param_name, param_value in six.iteritems(given_params):
            if (param_value is not None and param_name not in ignore_params and
                    target[param_name] is not param_value and
                    target[param_name] != param_value):
                parameters[param_name] = param_value
                old_parameters[param_name] = target[param_name]

        if parameters:
            repo_change = {
                'old': 'Repo properties were {0}'.format(old_parameters),
                'new': 'Repo properties (that changed) are {0}'.format(parameters)
            }
            if __opts__['test']:
                ret['changes']['repo'] = repo_change
                ret['result'] = None
            else:
                result = __salt__['github.edit_repo'](name, profile=profile,
                                                      **parameters)
                if result:
                    ret['changes']['repo'] = repo_change
                else:
                    ret['result'] = False
                    ret['comment'] = 'Failed to update repo properties.'
                    return ret

    else:  # Repo does not exist - it will be created.
        repo_change = {
            'old': None,
            'new': 'Repo {0} has been created'.format(name)
        }
        if __opts__['test']:
            ret['changes']['repo'] = repo_change
            ret['result'] = None
        else:
            add_params = dict(given_params)
            add_params.update(kwargs)
            result = __salt__['github.add_repo'](
                name,
                **add_params
            )

            if not result:
                ret['result'] = False
                ret['comment'] = 'Failed to create repo {0}.'.format(name)
                return ret

            # Turns out that trying to fetch teams for a new repo can 404 immediately
            # after repo creation, so this waits until we can fetch teams successfully
            # before continuing.
            for attempt in range(3):
                time.sleep(1)
                try:
                    current_teams = __salt__['github.get_repo_teams'](
                        name, profile=profile, **kwargs)
                    break
                except CommandExecutionError as e:
                    log.info("Attempt %s to fetch new repo %s failed",
                             attempt,
                             name)

            if current_teams is None:
                ret['result'] = False
                ret['comment'] = 'Failed to verify repo {0} after creation.'.format(name)
                return ret

            ret['changes']['repo'] = repo_change

    if teams is not None:
        if __opts__['test'] and not target:
            # Assume no teams if we're in test mode and the repo doesn't exist
            current_teams = []
        elif current_teams is None:
            current_teams = __salt__['github.get_repo_teams'](name, profile=profile)
        current_team_names = set([t['name'] for t in current_teams])

        # First remove any teams that aren't present
        for team_name in current_team_names:
            if team_name not in teams:
                team_change = {
                    'old': 'Repo {0} is in team {1}'.format(name, team_name),
                    'new': 'Repo {0} is not in team {1}'.format(name, team_name)
                }

                if __opts__['test']:
                    ret['changes'][team_name] = team_change
                    ret['result'] = None
                else:
                    result = __salt__['github.remove_team_repo'](name, team_name,
                                                                 profile=profile)
                    if result:
                        ret['changes'][team_name] = team_change
                    else:
                        ret['result'] = False
                        ret['comment'] = ('Failed to remove repo {0} from team {1}.'
                                          .format(name, team_name))
                        return ret

        # Next add or modify any necessary teams
        for team_name, permission in six.iteritems(teams):
            if team_name not in current_team_names:  # Need to add repo to team
                team_change = {
                    'old': 'Repo {0} is not in team {1}'.format(name, team_name),
                    'new': 'Repo {0} is in team {1}'.format(name, team_name)
                }
                if __opts__['test']:
                    ret['changes'][team_name] = team_change
                    ret['result'] = None
                else:
                    result = __salt__['github.add_team_repo'](name, team_name,
                                                              profile=profile,
                                                              permission=permission)
                    if result:
                        ret['changes'][team_name] = team_change
                    else:
                        ret['result'] = False
                        ret['comment'] = ('Failed to remove repo {0} from team {1}.'
                                          .format(name, team_name))
                        return ret
            else:
                current_permission = (__salt__['github.list_team_repos']
                                      (team_name, profile=profile)
                                      .get(name.lower(), {})
                                      .get('permission'))
                if not current_permission:
                    ret['result'] = False
                    ret['comment'] = ('Failed to determine current permission for team '
                                      '{0} in repo {1}'.format(team_name, name))
                    return ret
                elif current_permission != permission:
                    team_change = {
                        'old': ('Repo {0} in team {1} has permission {2}'
                                .format(name, team_name, current_permission)),
                        'new': ('Repo {0} in team {1} has permission {2}'
                                .format(name, team_name, permission))
                    }
                    if __opts__['test']:
                        ret['changes'][team_name] = team_change
                        ret['result'] = None
                    else:
                        result = __salt__['github.add_team_repo'](name, team_name,
                                                                  profile=profile,
                                                                  permission=permission)
                        if result:
                            ret['changes'][team_name] = team_change
                        else:
                            ret['result'] = False
                            ret['comment'] = ('Failed to set permission on repo {0} from '
                                              'team {1} to {2}.'
                                              .format(name, team_name, permission))
                            return ret
    return ret


def repo_absent(name, profile="github", **kwargs):
    '''
    Ensure a repo is absent.

    Example:

    .. code-block:: yaml

        ensure repo test is absent in github:
            github.repo_absent:
                - name: 'test'

    The following parameters are required:

    name
        This is the name of the repository in the organization.

    .. versionadded:: 2016.11.0
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': None,
        'comment': ''
    }

    try:
        target = __salt__['github.get_repo_info'](name, profile=profile, **kwargs)
    except CommandExecutionError:
        target = None

    if not target:
        ret['comment'] = 'Repo {0} does not exist'.format(name)
        ret['result'] = True
        return ret
    else:
        if __opts__['test']:
            ret['comment'] = "Repo {0} will be deleted".format(name)
            ret['result'] = None
            return ret

        result = __salt__['github.remove_repo'](name, profile=profile, **kwargs)

        if result:
            ret['comment'] = 'Deleted repo {0}'.format(name)
            ret['changes'].setdefault('old', 'Repo {0} exists'.format(name))
            ret['changes'].setdefault('new', 'Repo {0} deleted'.format(name))
            ret['result'] = True
        else:
            ret['comment'] = ('Failed to delete repo {0}. Ensure the delete_repo '
                              'scope is enabled if using OAuth.'.format(name))
            ret['result'] = False
    return ret
