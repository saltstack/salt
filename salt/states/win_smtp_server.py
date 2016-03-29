# -*- coding: utf-8 -*-
'''
Module for managing IIS SMTP server configuration on Windows servers.

'''

from __future__ import absolute_import

# Import 3rd-party libs
import salt.ext.six as six

# Import salt libs
import salt.utils

_DEFAULT_SERVER = 'SmtpSvc/1'


def __virtual__():
    '''
    Load only on minions that have the win_smtp_server module.
    '''
    if 'win_smtp_server.get_server_setting' in __salt__:
        return True
    return False


def _merge_dicts(*args):
    '''
    Shallow copy and merge dicts together, giving precedence to last in.
    '''
    ret = dict()
    for arg in args:
        ret.update(arg)
    return ret


def _normalize_server_settings(**settings):
    '''
    Convert setting values that has been improperly converted to a dict back to a string.
    '''
    ret = dict()
    settings = salt.utils.clean_kwargs(**settings)

    for setting in settings:
        if isinstance(settings[setting], dict):
            value_from_key = next(six.iterkeys(settings[setting]))

            ret[setting] = "{{{0}}}".format(value_from_key)
        else:
            ret[setting] = settings[setting]
    return ret


def server_setting(name, settings=None, server=_DEFAULT_SERVER):
    '''
    Ensure the value is set for the specified setting.
    '''
    ret = {'name': name,
           'changes': {},
           'comment': str(),
           'result': None}

    if not settings:
        ret['comment'] = 'No settings to change provided.'
        ret['result'] = True
        return ret

    ret_settings = dict()
    ret_settings['changes'] = {}
    ret_settings['failures'] = {}

    current_settings = __salt__['win_smtp_server.get_server_setting'](settings=settings.keys(),
                                                                      server=server)
    for key in settings:
        # Some fields are formatted like '{data}'. Salt/Python converts these to dicts
        # automatically on input, so convert them back to the proper format.
        settings = _normalize_server_settings(**settings)

        if str(settings[key]) != str(current_settings[key]):
            ret_settings['changes'][key] = {'old': current_settings[key],
                                            'new': settings[key]}
    if not ret_settings['changes']:
        ret['comment'] = 'Settings already contain the provided values.'
        ret['result'] = True
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Settings will be changed.'
        ret['changes'] = ret_settings
        return ret

    __salt__['win_smtp_server.set_server_setting'](settings=settings, server=server)
    new_settings = __salt__['win_smtp_server.get_server_setting'](settings=settings.keys(),
                                                                  server=server)
    for key in settings:
        if str(new_settings[key]) != str(settings[key]):
            ret_settings['failures'][key] = {'old': current_settings[key],
                                             'new': new_settings[key]}
            ret_settings['changes'].pop(key, None)

    if ret_settings['failures']:
        ret['comment'] = 'Some settings failed to change.'
        ret['changes'] = ret_settings
        ret['result'] = False
    else:
        ret['comment'] = 'Set settings to contain the provided values.'
        ret['changes'] = ret_settings['changes']
        ret['result'] = True
    return ret


def active_log_format(name, log_format, server=_DEFAULT_SERVER):
    '''
    Manage the active log format for the SMTP server.
    '''
    ret = {'name': name,
           'changes': {},
           'comment': str(),
           'result': None}
    current_log_format = __salt__['win_smtp_server.get_log_format'](server)

    if log_format == current_log_format:
        ret['comment'] = 'LogPluginClsid already contains the id of the provided log format.'
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'LogPluginClsid will be changed.'
        ret['changes'] = {'old': current_log_format,
                          'new': log_format}
    else:
        ret['comment'] = 'Set LogPluginClsid to contain the id of the provided log format.'
        ret['changes'] = {'old': current_log_format,
                          'new': log_format}
        ret['result'] = __salt__['win_smtp_server.set_log_format'](log_format, server)
    return ret


def connection_ip_list(name, addresses=None, grant_by_default=False, server=_DEFAULT_SERVER):
    '''
    Manage IP list for SMTP connections.
    '''
    ret = {'name': name,
           'changes': {},
           'comment': str(),
           'result': None}
    if not addresses:
        addresses = dict()

    current_addresses = __salt__['win_smtp_server.get_connection_ip_list'](server=server)

    if addresses == current_addresses:
        ret['comment'] = 'IPGrant already contains the provided addresses.'
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'IPGrant will be changed.'
        ret['changes'] = {'old': current_addresses,
                          'new': addresses}
    else:
        ret['comment'] = 'Set IPGrant to contain the provided addresses.'
        ret['changes'] = {'old': current_addresses,
                          'new': addresses}
        ret['result'] = __salt__['win_smtp_server.set_connection_ip_list'](addresses=addresses,
                                                                           grant_by_default=grant_by_default,
                                                                           server=server)
    return ret


def relay_ip_list(name, addresses=None, server=_DEFAULT_SERVER):
    '''
    Manage IP list for SMTP relay connections.
    '''
    ret = {'name': name,
           'changes': {},
           'comment': str(),
           'result': None}
    current_addresses = __salt__['win_smtp_server.get_relay_ip_list'](server=server)

    # Fix if we were passed None as a string.
    if addresses:
        if addresses[0] == 'None':
            addresses[0] = None
    elif addresses is None:
        addresses = [None]

    if addresses == current_addresses:
        ret['comment'] = 'RelayIpList already contains the provided addresses.'
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'RelayIpList will be changed.'
        ret['changes'] = {'old': current_addresses,
                          'new': addresses}
    else:
        ret['comment'] = 'Set RelayIpList to contain the provided addresses.'
        ret['changes'] = {'old': current_addresses,
                          'new': addresses}
        ret['result'] = __salt__['win_smtp_server.set_relay_ip_list'](addresses=addresses, server=server)
    return ret
