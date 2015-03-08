# -*- coding: utf-8 -*-
'''
Module for returning various status data about a minion.
These data can be useful for compiling into stats later.

:depends:   - pythoncom
            - wmi
'''

import subprocess
import logging
import salt.utils
import salt.utils.event
from salt.utils.network import host_to_ip as _host_to_ip


log = logging.getLogger(__name__)

try:
    import wmi
    import salt.utils.winapi
    has_required_packages = True
except ImportError:
    if salt.utils.is_windows():
        log.exception('pywin32 and wmi python packages are required '
                      'in order to use the status module.')
    has_required_packages = False


__opts__ = {}

# Define the module's virtual name
__virtualname__ = 'status'


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows() and has_required_packages:
        return __virtualname__
    return False


def procs():
    '''
    Return the process data

    CLI Example:

    .. code-block:: bash

        salt '*' status.procs
    '''
    with salt.utils.winapi.Com():
        wmi_obj = wmi.WMI()
        processes = wmi_obj.win32_process()

        process_info = {}
        for proc in processes:
            process_info[proc.ProcessId] = _get_process_info(proc)

        return process_info


def _get_process_info(proc):
    '''
    Return  process information
    '''
    cmd = (proc.CommandLine or '').encode('utf-8')
    name = proc.Name.encode('utf-8')
    info = dict(
        cmd=cmd,
        name=name,
        **_get_process_owner(proc)
    )
    return info


def _get_process_owner(process):
    owner = {}
    domain, error_code, user = None, None, None
    try:
        domain, error_code, user = process.GetOwner()
        owner['user'] = user.encode('utf-8')
        owner['user_domain'] = domain.encode('utf-8')
    except Exception as exc:
        pass
    if not error_code and all((user, domain)):
        owner['user'] = user.encode('utf-8')
        owner['user_domain'] = domain.encode('utf-8')
    elif process.ProcessId in [0, 4] and error_code == 2:
        # Access Denied for System Idle Process and System
        owner['user'] = 'SYSTEM'
        owner['user_domain'] = 'NT AUTHORITY'
    else:
        log.warning('Error getting owner of process; PID=\'{0}\'; Error: {1}'
                    .format(process.ProcessId, error_code))
    return owner


def master(master=None, connected=True):
    '''
    Fire an event if the minion gets disconnected from its master. This
    function is meant to be run via a scheduled job from the minion. If
    master_ip is an FQDN/Hostname, is must be resolvable to a valid IPv4
    address.

    CLI Example:

    .. code-block:: bash

        salt '*' status.master
    '''

    def _win_remotes_on(port):
        '''
        Windows specific helper function.
        Returns set of ipv4 host addresses of remote established connections
        on local or remote tcp port.

        Parses output of shell 'netstat' to get connections

        PS C:> netstat -n -p TCP

        Active Connections

          Proto  Local Address          Foreign Address        State
          TCP    10.1.1.26:3389         10.1.1.1:4505          ESTABLISHED
          TCP    10.1.1.26:56862        10.1.1.10:49155        TIME_WAIT
          TCP    10.1.1.26:56868        169.254.169.254:80     CLOSE_WAIT
          TCP    127.0.0.1:49197        127.0.0.1:49198        ESTABLISHED
          TCP    127.0.0.1:49198        127.0.0.1:49197        ESTABLISHED
        '''
        remotes = set()
        try:
            data = subprocess.check_output(['netstat', '-n', '-p', 'TCP'])
        except subprocess.CalledProcessError:
            log.error('Failed netstat')
            raise

        lines = data.split('\n')
        for line in lines:
            if 'ESTABLISHED' not in line:
                continue
            chunks = line.split()
            remote_host, remote_port = chunks[2].rsplit(':', 1)
            if int(remote_port) != port:
                continue
            remotes.add(remote_host)
        return remotes

    # the default publishing port
    port = 4505
    master_ip = None

    if __salt__['config.get']('publish_port') != '':
        port = int(__salt__['config.get']('publish_port'))

    # Check if we have FQDN/hostname defined as master
    # address and try resolving it first. _remote_port_tcp
    # only works with IP-addresses.
    if master is not None:
        tmp_ip = _host_to_ip(master)
        if tmp_ip is not None:
            master_ip = tmp_ip

    ips = _win_remotes_on(port)

    if connected:
        if master_ip not in ips:
            event = salt.utils.event.get_event('minion', opts=__opts__, listen=False)
            event.fire_event({'master': master}, '__master_disconnected')
    else:
        if master_ip in ips:
            event = salt.utils.event.get_event('minion', opts=__opts__, listen=False)
            event.fire_event({'master': master}, '__master_connected')
