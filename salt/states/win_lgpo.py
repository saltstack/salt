# -*- coding: utf-8 -*-
'''
Manage Windows Local Group Policy
=================================

.. versionadded:: 2016.11.0

This state allows configuring local Windows Group Policy

The state can be used to ensure the setting of a single policy or multiple policies in one pass.

Single policies must specify the policy name, the setting, and the policy class (Machine/User/Both)

Example single policy configuration

.. code-block:: yaml

    Ensure Account Lockout Duration:
      lgpo.set:
        - name: Account lockout duration
        - setting: 90
        - policy_class: Machine

.. code-block:: yaml

    Acount lockout duration:
      gpo.set:
        - setting: 120
        - policy_class: Machine

Multiple policy configuration

.. code-block:: yaml

    Company Local Group Policy:
        lgpo.set:
            - computer_policy:
                Deny logon locally: Guest
                Account lockout duration: 120
                Account lockout threshold: 10
                Reset account lockout counter after: 1440
                Enforce password history: 24
                Maximum password age: 60
                Minimum password age: 1
                Minimum password length: 14
                Password must meet complexity requirements: Enabled
                Store passwords using reversible encrytion: Disabled
                Configure Automatic Updates:
                    Configure automatic updating: 4 - Auto download and schedule the intsall
                    Scheduled install day: 7 - Every Saturday
                    Scheduled install time: 17:00
                Specify intranet Microsoft update service location:
                    Set the intranet update service for detecting updates: http://mywsus
                    Set the intranet statistics server: http://mywsus
            - user_policy:
                Do not process the legacy run list: Enabled

.. code-block:: yaml

    server_policy:
      lgpo.set:
        - computer_policy:
            Maximum password age: 60
            Minimum password age: 1
            Minimum password length: 14
            Account lockout duration: 1440
            Account lockout threshold: 10
            Reset account lockout counter after: 1440
            Manage auditing and security log:
              - "BUILTIN\\Administrators"
            Replace a process level token:
              - "NT AUTHORITY\\NETWORK SERVICE"
              - "NT AUTHORITY\\LOCAL SERVICE"
            "Accounts: Guest account status": Disabled
            "Accounts: Rename guest account": Not_4_U
            "Audit: Audit the use of Backup and Restore privilege": Enabled
            "Interactive logon: Do not display last user name": Enabled
            "Network\\DNS Client\\Dynamic update": Disabled
            "System\\Logon\\Do not display the Getting Started welcome screen at logon": Enabled
            "Windows Components\\Remote Desktop Services\\Remote Desktop Session Host\\Connections\\Select RDP transport protocols":
                "Select Transport Type": "Use both UDP and TCP"
            "Windows Components\\Windows Update\\Allow Automatic Updates immediate installation": Enabled
            "Windows Components\\Windows Update\\Allow non-administrators to receive update notifications": Disabled
            "Windows Components\\Windows Update\\Always automatically restart at the scheduled time":
                "The restart timer will give users this much time to save their work (minutes)": 15
            "Windows Components\\Windows Update\\Automatic Updates detection frequency":
                "Check for updates at the following interval (hours)": 1
            "Windows Components\\Windows Update\\Configure Automatic Updates":
                "Configure automatic updating": 4 - Auto download and schedule the install
                "Install during automatic maintenance": False
                "Scheduled install day": 7 - Every Saturday
                "Scheduled install time": "17:00"
            "Windows Components\\Windows Update\\Delay Restart for scheduled installations":
                "Wait the following period before proceeding with a scheduled restart (minutes)": 1
            "Windows Components\\Windows Update\\No auto-restart with logged on users for scheduled automatic updates installations": Disabled
            "Windows Components\\Windows Update\\Re-prompt for restart with scheduled installations":
                "Wait the following period before prompting again with a scheduled restart (minutes)": 30
            "Windows Components\\Windows Update\\Reschedule Automatic Updates scheduled installations": Disabled
            "Windows Components\\Windows Update\\Specify intranet Microsoft update service location":
                "Set the intranet update service for detecting updates": http://mywsus
                "Set the intranet statistics server": http://mywsus
        - cumulative_rights_assignments: True

'''

from __future__ import absolute_import
import logging
import json

log = logging.getLogger(__name__)
__virtualname__ = 'lgpo'
__func_alias__ = {'set_': 'set'}


def __virtual__():
    '''
    load this state if the win_lgpo module exists
    '''
    return __virtualname__ if 'lgpo.set' in __salt__ else False


def set_(name,
         setting=None,
         policy_class=None,
         computer_policy=None,
         user_policy=None,
         cumulative_rights_assignments=True,
         adml_language='en-US'):
    '''
    Ensure the specified policy is set

    name
        the name of a single policy to configure

    setting
        the configuration setting for the single named policy
        if this argument is used the computer_policy/user_policy arguments will be ignored

    policy_class
        the policy class of the single named policy to configure
        this can "machine", "user", or "both"

    computer_policy
        a dict of policyname: value pairs of a set of computer policies to configure
        if this argument is used, the name/setting/policy_class arguments will be ignored

    user_policy
        a dict of policyname: value pairs of a set of user policies to configure
        if this argument is used, the name/setting/policy_class arguments will be ignored

    cumulative_rights_assignments
        determine if any user right assignment policies specified will be cumulative
        or explicit

    adml_language
        the adml language to use for AMDX policy data/display conversions
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    policy_classes = ['machine', 'computer', 'user', 'both']
    if not setting and not computer_policy and not user_policy:
        msg = 'At least one of the parameters setting, computer_policy, or user_policy'
        msg = msg + ' must be specified.'
        ret['result'] = False
        ret['comment'] = msg
        return ret
    if setting and not policy_class:
        msg = 'A single policy setting was specified but the policy_class was not specified.'
        ret['result'] = False
        ret['comment'] = msg
        return ret
    if setting and (computer_policy or user_policy):
        msg = 'The setting and computer_policy/user_policy parameters are mutually exclusive.  Please'
        msg = msg + ' specify either a policy name and setting or a computer_policy and/or user_policy'
        msg = msg + ' dict'
        ret['result'] = False
        ret['comment'] = msg
        return ret
    if policy_class and policy_class.lower() not in policy_classes:
        msg = 'The policy_class parameter must be one of the following: {0}'
        ret['result'] = False
        ret['comment'] = msg
        return ret
    if not setting:
        if computer_policy and user_policy:
            policy_class = 'both'
        elif computer_policy:
            policy_class = 'machine'
        elif user_policy:
            policy_class = 'user'
        if computer_policy and not isinstance(computer_policy, dict):
            msg = 'The computer_policy must be specified as a dict.'
            ret['result'] = False
            ret['comment'] = msg
            return ret
        if user_policy and not isinstance(user_policy, dict):
            msg = 'The user_policy must be specified as a dict.'
            ret['result'] = False
            ret['comment'] = msg
            return ret
    else:
        user_policy = {}
        computer_policy = {}
        if policy_class.lower() == 'both':
            user_policy[name] = setting
            computer_policy[name] = setting
        elif policy_class.lower() == 'user':
            user_policy[name] = setting
        elif policy_class.lower() == 'machine' or policy_class.lower() == 'computer':
            computer_policy[name] = setting
    pol_data = {}
    pol_data['user'] = {'output_section': 'User Configuration',
                        'requested_policy': user_policy,
                        'policy_lookup': {}}
    pol_data['machine'] = {'output_section': 'Computer Configuration',
                           'requested_policy': computer_policy,
                           'policy_lookup': {}}

    for p_class, p_data in pol_data.iteritems():
        if p_data['requested_policy']:
            for policy_name, policy_setting in p_data['requested_policy'].iteritems():
                lookup = __salt__['lgpo.get_policy_info'](policy_name,
                                                          p_class,
                                                          adml_language=adml_language)
                if lookup['policy_found']:
                    pol_data[p_class]['policy_lookup'][policy_name] = lookup
                else:
                    ret['comment'] = ' '.join([ret['comment'], lookup['message']])
                    ret['result'] = False
    if not ret['result']:
        return ret

    current_policy = __salt__['lgpo.get'](policy_class=policy_class,
                                          adml_language=adml_language,
                                          hierarchical_return=False)
    log.debug('current policy == {0}'.format(current_policy))

    # compare policies
    policy_changes = []
    for policy_section, policy_data in pol_data.iteritems():
        pol_id = None
        if policy_data and policy_data['output_section'] in current_policy:
            for policy_name, policy_setting in policy_data['requested_policy'].iteritems():
                currently_set = False
                if policy_name in current_policy[policy_data['output_section']]:
                    currently_set = True
                    pol_id = policy_name
                else:
                    for alias in policy_data['policy_lookup'][policy_name]['policy_aliases']:
                        log.debug('checking alias {0}'.format(alias))
                        if alias in current_policy[policy_data['output_section']]:
                            currently_set = True
                            pol_id = alias
                            break
                if currently_set:
                    # compare
                    log.debug('need to compare {0} from current/requested policy'.format(policy_name))
                    changes = False
                    if json.dumps(policy_data['requested_policy'][policy_name], sort_keys=True).lower() != \
                            json.dumps(current_policy[policy_data['output_section']][pol_id], sort_keys=True).lower():
                        if policy_data['policy_lookup'][policy_name]['rights_assignment'] and cumulative_rights_assignments:
                            for user in policy_data['requested_policy'][policy_name]:
                                if user not in current_policy[policy_data['output_section']][pol_id]:
                                    changes = True
                        else:
                            changes = True
                        if changes:
                            log.debug('{0} current policy != requested policy'.format(policy_name))
                            log.debug('we compared {0} to {1}'.format(
                                    json.dumps(policy_data['requested_policy'][policy_name], sort_keys=True).lower(),
                                    json.dumps(current_policy[policy_data['output_section']][pol_id], sort_keys=True).lower()))
                            policy_changes.append(policy_name)
                    else:
                        log.debug('{0} current setting matches the requested setting'.format(policy_name))
                        ret['comment'] = '  '.join(['"{0}" is already set.'.format(policy_name),
                                                    ret['comment']])
                else:
                    policy_changes.append(policy_name)
                    log.debug('policy {0} is not set, we will configure it'.format(policy_name))
    if __opts__['test']:
        if policy_changes:
            ret['result'] = None
            ret['comment'] = 'The following policies are set to change: {0}.'.format(
                    ', '.join(policy_changes))
        else:
            ret['comment'] = 'All specified policies are properly configured'
    else:
        if policy_changes:
            _ret = __salt__['lgpo.set'](computer_policy=computer_policy,
                                        user_policy=user_policy,
                                        cumulative_rights_assignments=cumulative_rights_assignments,
                                        adml_language=adml_language)
            if _ret:
                ret['result'] = _ret
                ret['changes']['old'] = current_policy
                ret['changes']['new'] = __salt__['lgpo.get'](policy_class=policy_class,
                                                             adml_language=adml_language,
                                                             hierarchical_return=False)
            else:
                ret['result'] = False
                ret['comment'] = 'Errors occurred while attempting to configure policies: {0}'.format(_ret)

    return ret
