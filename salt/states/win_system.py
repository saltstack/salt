# -*- coding: utf-8 -*-
'''
Management of Windows system information
========================================

.. versionadded:: 2014.1.0

This state is used to manage system information such as the computer name and
description.

.. code-block:: yaml

    ERIK-WORKSTATION:
      system.computer_name: []

    This is Erik's computer, don't touch!:
      system.computer_desc: []
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import Python libs
import logging

# Import Salt libs
import salt.utils.functools
import salt.utils.platform

# Import 3rd party libs
from salt.ext import six


log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'system'


def __virtual__():
    '''
    This only supports Windows
    '''
    if salt.utils.platform.is_windows() and 'system.get_computer_desc' in __salt__:
        return __virtualname__
    return False


def computer_desc(name):
    '''
    Manage the computer's description field

    name
        The desired computer description
    '''
    # Just in case someone decides to enter a numeric description
    name = six.text_type(name)

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Computer description already set to \'{0}\''.format(name)}

    before_desc = __salt__['system.get_computer_desc']()

    if before_desc == name:
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('Computer description will be changed to \'{0}\''
                          .format(name))
        return ret

    result = __salt__['system.set_computer_desc'](name)
    if result['Computer Description'] == name:
        ret['comment'] = ('Computer description successfully changed to \'{0}\''
                          .format(name))
        ret['changes'] = {'old': before_desc, 'new': name}
    else:
        ret['result'] = False
        ret['comment'] = ('Unable to set computer description to '
                          '\'{0}\''.format(name))
    return ret


computer_description = salt.utils.functools.alias_function(computer_desc, 'computer_description')


def computer_name(name):
    '''
    Manage the computer's name

    name
        The desired computer name
    '''
    # Just in case someone decides to enter a numeric description
    name = six.text_type(name)

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Computer name already set to \'{0}\''.format(name)}

    before_name = __salt__['system.get_computer_name']()
    pending_name = __salt__['system.get_pending_computer_name']()

    if before_name == name and pending_name is None:
        return ret
    elif pending_name == name.upper():
        ret['comment'] = ('The current computer name is \'{0}\', but will be '
                          'changed to \'{1}\' on the next reboot'
                          .format(before_name, name))
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Computer name will be changed to \'{0}\''.format(name)
        return ret

    result = __salt__['system.set_computer_name'](name)
    if result is not False:
        after_name = result['Computer Name']['Current']
        after_pending = result['Computer Name'].get('Pending')
        if ((after_pending is not None and after_pending == name) or
                (after_pending is None and after_name == name)):
            ret['comment'] = 'Computer name successfully set to \'{0}\''.format(name)
            if after_pending is not None:
                ret['comment'] += ' (reboot required for change to take effect)'
        ret['changes'] = {'old': before_name, 'new': name}
    else:
        ret['result'] = False
        ret['comment'] = 'Unable to set computer name to \'{0}\''.format(name)
    return ret


def hostname(name):
    '''
    .. versionadded:: 2016.3.0

    Manage the hostname of the computer

    name
        The hostname to set
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': ''
    }

    current_hostname = __salt__['system.get_hostname']()

    if current_hostname.upper() == name.upper():
        ret['comment'] = "Hostname is already set to '{0}'".format(name)
        return ret

    out = __salt__['system.set_hostname'](name)

    if out:
        ret['comment'] = "The current hostname is '{0}', " \
                         "but will be changed to '{1}' on the next reboot".format(current_hostname, name)
        ret['changes'] = {'hostname': name}
    else:
        ret['result'] = False
        ret['comment'] = 'Unable to set hostname'

    return ret


def workgroup(name):
    '''
    .. versionadded:: 2019.2.0

    Manage the workgroup of the computer

    name
        The workgroup to set

    Example:

    .. code-block:: yaml

        set workgroup:
          system.workgroup:
            - name: local
    '''
    ret = {'name': name.upper(), 'result': False, 'changes': {}, 'comment': ''}

    # Grab the current domain/workgroup
    out = __salt__['system.get_domain_workgroup']()
    current_workgroup = out['Domain'] if 'Domain' in out else out['Workgroup'] if 'Workgroup' in out else ''

    # Notify the user if the requested workgroup is the same
    if current_workgroup.upper() == name.upper():
        ret['result'] = True
        ret['comment'] = "Workgroup is already set to '{0}'".format(name.upper())
        return ret

    # If being run in test-mode, inform the user what is supposed to happen
    if __opts__['test']:
        ret['result'] = None
        ret['changes'] = {}
        ret['comment'] = 'Computer will be joined to workgroup \'{0}\''.format(name)
        return ret

    # Set our new workgroup, and then immediately ask the machine what it
    # is again to validate the change
    res = __salt__['system.set_domain_workgroup'](name.upper())
    out = __salt__['system.get_domain_workgroup']()
    changed_workgroup = out['Domain'] if 'Domain' in out else out['Workgroup'] if 'Workgroup' in out else ''

    # Return our results based on the changes
    ret = {}
    if res and current_workgroup.upper() == changed_workgroup.upper():
        ret['result'] = True
        ret['comment'] = "The new workgroup '{0}' is the same as '{1}'".format(current_workgroup.upper(), changed_workgroup.upper())
    elif res:
        ret['result'] = True
        ret['comment'] = "The workgroup has been changed from '{0}' to '{1}'".format(current_workgroup.upper(), changed_workgroup.upper())
        ret['changes'] = {'old': current_workgroup.upper(), 'new': changed_workgroup.upper()}
    else:
        ret['result'] = False
        ret['comment'] = "Unable to join the requested workgroup '{0}'".format(changed_workgroup.upper())

    return ret


def join_domain(name,
                username=None,
                password=None,
                account_ou=None,
                account_exists=False,
                restart=False):
    '''
    Checks if a computer is joined to the Domain. If the computer is not in the
    Domain, it will be joined.

    Args:

        name (str):
            The name of the Domain.

        username (str):
            Username of an account which is authorized to join computers to the
            specified domain. Need to be either fully qualified like
            user@domain.tld or simply user.

        password (str):
            Password of the account to add the computer to the Domain.

        account_ou (str):
            The DN of the OU below which the account for this computer should be
            created when joining the domain,
            e.g. ou=computers,ou=departm_432,dc=my-company,dc=com.

        account_exists (bool):
            Needs to be set to ``True`` to allow re-using an existing computer
            account.

        restart (bool):
            Needs to be set to ``True`` to restart the computer after a
            successful join.

    Example:

    .. code-block:: yaml

        join_to_domain:
          system.join_domain:
            - name: mydomain.local.com
            - username: myaccount@mydomain.local.com
            - password: mysecretpassword
            - restart: True
    '''

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Computer already added to \'{0}\''.format(name)}

    current_domain_dic = __salt__['system.get_domain_workgroup']()
    if 'Domain' in current_domain_dic:
        current_domain = current_domain_dic['Domain']
    elif 'Workgroup' in current_domain_dic:
        current_domain = 'Workgroup'
    else:
        current_domain = None

    if name.lower() == current_domain.lower():
        ret['comment'] = 'Computer already added to \'{0}\''.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Computer will be added to \'{0}\''.format(name)
        return ret

    result = __salt__['system.join_domain'](domain=name,
                                            username=username,
                                            password=password,
                                            account_ou=account_ou,
                                            account_exists=account_exists,
                                            restart=restart)
    if result is not False:
        ret['comment'] = 'Computer added to \'{0}\''.format(name)
        if restart:
            ret['comment'] += '\nSystem will restart'
        else:
            ret['comment'] += '\nSystem needs to be restarted'
        ret['changes'] = {'old': current_domain,
                          'new': name}
    else:
        ret['comment'] = 'Computer failed to join \'{0}\''.format(name)
        ret['result'] = False
    return ret


def reboot(name, message=None, timeout=5, force_close=True, in_seconds=False,
           only_on_pending_reboot=True):
    '''
    Reboot the computer

    :param str message:
        An optional message to display to users. It will also be used as a
        comment in the event log entry.

        The default value is None.

    :param int timeout:
        The number of minutes or seconds before a reboot will occur. Whether
        this number represents minutes or seconds depends on the value of
        ``in_seconds``.

        The default value is 5.

    :param bool in_seconds:
        If this is True, the value of ``timeout`` will be treated as a number
        of seconds. If this is False, the value of ``timeout`` will be treated
        as a number of minutes.

        The default value is False.

    :param bool force_close:
        If this is True, running applications will be forced to close without
        warning. If this is False, running applications will not get the
        opportunity to prompt users about unsaved data.

        The default value is True.

    :param bool only_on_pending_reboot:

        If this is True, the reboot will only occur if the system reports a
        pending reboot. If this is False, the reboot will always occur.

        The default value is True.
    '''

    return shutdown(name, message=message, timeout=timeout,
                    force_close=force_close, reboot=True,
                    in_seconds=in_seconds,
                    only_on_pending_reboot=only_on_pending_reboot)


def shutdown(name, message=None, timeout=5, force_close=True, reboot=False,
             in_seconds=False, only_on_pending_reboot=False):
    '''
    Shutdown the computer

    :param str message:
        An optional message to display to users. It will also be used as a
        comment in the event log entry.

        The default value is None.

    :param int timeout:
        The number of minutes or seconds before a shutdown will occur. Whether
        this number represents minutes or seconds depends on the value of
        ``in_seconds``.

        The default value is 5.

    :param bool in_seconds:
        If this is True, the value of ``timeout`` will be treated as a number
        of seconds. If this is False, the value of ``timeout`` will be treated
        as a number of minutes.

        The default value is False.

    :param bool force_close:
        If this is True, running applications will be forced to close without
        warning. If this is False, running applications will not get the
        opportunity to prompt users about unsaved data.

        The default value is True.

    :param bool reboot:

        If this is True, the computer will restart immediately after shutting
        down. If False the system flushes all caches to disk and safely powers
        down the system.

        The default value is False.

    :param bool only_on_pending_reboot:

        If this is True, the shutdown will only occur if the system reports a
        pending reboot. If this is False, the shutdown will always occur.

        The default value is False.
    '''

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if reboot:
        action = 'reboot'
    else:
        action = 'shutdown'

    if only_on_pending_reboot and not __salt__['system.get_pending_reboot']():
        if __opts__['test']:
            ret['comment'] = ('System {0} will be skipped because '
                              'no reboot is pending').format(action)
        else:
            ret['comment'] = ('System {0} has been skipped because '
                              'no reboot was pending').format(action)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Will attempt to schedule a {0}'.format(action)
        return ret

    ret['result'] = __salt__['system.shutdown'](message=message,
                                                timeout=timeout,
                                                force_close=force_close,
                                                reboot=reboot,
                                                in_seconds=in_seconds,
                                                only_on_pending_reboot=False)

    if ret['result']:
        ret['changes'] = {'old': 'No reboot or shutdown was scheduled',
                          'new': 'A {0} has been scheduled'.format(action)}
        ret['comment'] = 'Request to {0} was successful'.format(action)
    else:
        ret['comment'] = 'Request to {0} failed'.format(action)
    return ret
