# -*- coding: utf-8 -*-
'''
Manage RDP Service on Windows servers
'''
from __future__ import absolute_import

# Import python libs
import logging
import re

# Import salt libs
from salt.utils.decorators import depends
import salt.utils

try:
    from pywintypes import error as PyWinError
    import win32ts
    _HAS_WIN32TS_DEPENDENCIES = True
except ImportError:
    _HAS_WIN32TS_DEPENDENCIES = False

_LOG = logging.getLogger(__name__)


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        return 'rdp'
    return (False, 'Module only works on Windows.')


def _parse_return_code_powershell(string):
    '''
    return from the input string the return code of the powershell command
    '''

    regex = re.search(r'ReturnValue\s*: (\d*)', string)
    if not regex:
        return (False, 'Could not parse PowerShell return code.')
    else:
        return int(regex.group(1))


def _psrdp(cmd):
    '''
    Create a Win32_TerminalServiceSetting WMI Object as $RDP and execute the
    command cmd returns the STDOUT of the command
    '''
    rdp = ('$RDP = Get-WmiObject -Class Win32_TerminalServiceSetting '
           '-Namespace root\\CIMV2\\TerminalServices -Computer . '
           '-Authentication 6 -ErrorAction Stop')
    return __salt__['cmd.run']('{0} ; {1}'.format(rdp, cmd),
                               shell='powershell', python_shell=True)


def enable():
    '''
    Enable RDP the service on the server

    CLI Example:

    .. code-block:: bash

        salt '*' rdp.enable
    '''

    return _parse_return_code_powershell(
        _psrdp('$RDP.SetAllowTsConnections(1,1)')) == 0


def disable():
    '''
    Disable RDP the service on the server

    CLI Example:

    .. code-block:: bash

        salt '*' rdp.disable
    '''

    return _parse_return_code_powershell(
        _psrdp('$RDP.SetAllowTsConnections(0,1)')) == 0


def status():
    '''
    Show if rdp is enabled on the server

    CLI Example:

    .. code-block:: bash

        salt '*' rdp.status
    '''

    out = int(_psrdp('echo $RDP.AllowTSConnections').strip())
    return out != 0


@depends(_HAS_WIN32TS_DEPENDENCIES)
def list_sessions(logged_in_users_only=False):
    '''
    List information about the sessions.

    .. versionadded:: Carbon

    :param logged_in_users_only: If True, only return sessions with users logged in.
    :return: A list containing dictionaries of session information.

    CLI Example:

    .. code-block:: bash

        salt '*' rdp.list_sessions
    '''
    ret = list()
    server = win32ts.WTS_CURRENT_SERVER_HANDLE
    protocols = {win32ts.WTS_PROTOCOL_TYPE_CONSOLE: 'console',
                 win32ts.WTS_PROTOCOL_TYPE_ICA: 'citrix',
                 win32ts.WTS_PROTOCOL_TYPE_RDP: 'rdp'}
    statuses = {win32ts.WTSActive: 'active', win32ts.WTSConnected: 'connected',
                win32ts.WTSConnectQuery: 'connect_query', win32ts.WTSShadow: 'shadow',
                win32ts.WTSDisconnected: 'disconnected', win32ts.WTSIdle: 'idle',
                win32ts.WTSListen: 'listen', win32ts.WTSReset: 'reset',
                win32ts.WTSDown: 'down', win32ts.WTSInit: 'init'}

    for session in win32ts.WTSEnumerateSessions(server):
        user = win32ts.WTSQuerySessionInformation(server, session['SessionId'],
                                                  win32ts.WTSUserName) or None
        protocol_id = win32ts.WTSQuerySessionInformation(server, session['SessionId'],
                                                         win32ts.WTSClientProtocolType)
        status_id = win32ts.WTSQuerySessionInformation(server, session['SessionId'],
                                                       win32ts.WTSConnectState)
        protocol = protocols.get(protocol_id, 'unknown')
        connection_status = statuses.get(status_id, 'unknown')
        station = session['WinStationName'] or 'Disconnected'
        connection_info = {'connection_status': connection_status, 'protocol': protocol,
                           'session_id': session['SessionId'], 'station': station,
                           'user': user}
        if logged_in_users_only:
            if user:
                ret.append(connection_info)
        else:
            ret.append(connection_info)

    if not ret:
        _LOG.warning('No sessions found.')
    return sorted(ret, key=lambda k: k['session_id'])


@depends(_HAS_WIN32TS_DEPENDENCIES)
def get_session(session_id):
    '''
    Get information about a session.

    .. versionadded:: Carbon

    :param session_id: The numeric Id of the session.
    :return: A dictionary of session information.

    CLI Example:

    .. code-block:: bash

        salt '*' rdp.get_session session_id

        salt '*' rdp.get_session 99
    '''
    ret = dict()
    sessions = list_sessions()
    session = [item for item in sessions if item['session_id'] == session_id]

    if session:
        ret = session[0]

    if not ret:
        _LOG.warning('No session found for id: %s', session_id)
    return ret


@depends(_HAS_WIN32TS_DEPENDENCIES)
def disconnect_session(session_id):
    '''
    Disconnect a session.

    .. versionadded:: Carbon

    :param session_id: The numeric Id of the session.
    :return: A boolean representing whether the disconnect succeeded.

    CLI Example:

    .. code-block:: bash

        salt '*' rdp.disconnect_session session_id

        salt '*' rdp.disconnect_session 99
    '''
    try:
        win32ts.WTSDisconnectSession(win32ts.WTS_CURRENT_SERVER_HANDLE, session_id, True)
    except PyWinError as error:
        _LOG.error('Error calling WTSDisconnectSession: %s', error)
        return False
    return True


@depends(_HAS_WIN32TS_DEPENDENCIES)
def logoff_session(session_id):
    '''
    Initiate the logoff of a session.

    .. versionadded:: Carbon

    :param session_id: The numeric Id of the session.
    :return: A boolean representing whether the logoff succeeded.

    CLI Example:

    .. code-block:: bash

        salt '*' rdp.logoff_session session_id

        salt '*' rdp.logoff_session 99
    '''
    try:
        win32ts.WTSLogoffSession(win32ts.WTS_CURRENT_SERVER_HANDLE, session_id, True)
    except PyWinError as error:
        _LOG.error('Error calling WTSLogoffSession: %s', error)
        return False
    return True
