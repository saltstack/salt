# -*- coding: utf-8 -*-
r'''
Proxy Minion for Cisco NX-OS Switches

.. versionadded: 2016.11.0

The Cisco NX-OS Proxy Minion is supported on NX-OS devices for the following connection types:
1) Connection Type SSH
2) Connection Type NX-API (If Supported By The Device and Image Version).

:maturity:   new
:platform:   nxos

SSH uses the built in SSHConnection module in :mod:`salt.utils.vt_helper <salt.utils.vt_helper>`

To configure the proxy minion for ssh:

.. code-block:: yaml

    proxy:
      proxytype: nxos
      connection: ssh
      host: 192.168.187.100
      username: admin
      password: admin
      prompt_name: nxos-switch
      ssh_args: '-o PubkeyAuthentication=no'
      key_accept: True

To configure the proxy minon for nxapi:

.. code-block:: yaml

    proxy:
      proxytype: nxos
      connection: nxapi
      host: 192.168.187.100
      username: admin
      password: admin
      transport: http
      port: 80
      verify: False
      no_save_config: True

proxytype:
    (REQUIRED) Use this proxy minion `nxos`

connection:
    (REQUIRED) connection transport type.
    Choices: `ssh, nxapi`
    Default: `ssh`

host:
    (REQUIRED) login ip address or dns hostname.

username:
    (REQUIRED) login username.

password:
    (REQUIRED) login password.

no_save_config:
    If False, 'copy running-config starting-config' is issues for every
        configuration command.
    If True, Running config is not saved to startup config
    Default: False

    The recommended approach is to use the `save_running_config` function
    instead of this option to improve performance.  The default behavior
    controlled by this option is preserved for backwards compatibility.

Conection SSH Args:

    prompt_name:
        (REQUIRED when `connection` is `ssh`)
        (REQUIRED, this or `prompt_regex` below, but not both)
        The name in the prompt on the switch.  Recommended to use your
        device's hostname.

    prompt_regex:
        (REQUIRED when `connection` is `ssh`)
        (REQUIRED, this or `prompt_name` above, but not both)
        A regular expression that matches the prompt on the switch
        and any other possible prompt at which you need the proxy minion
        to continue sending input.  This feature was specifically developed
        for situations where the switch may ask for confirmation.  `prompt_name`
        above would not match these, and so the session would timeout.

        Example:

        .. code-block:: yaml

            nxos-switch#.*|\(y\/n\)\?.*

        This should match

        .. code-block:: shell

            nxos-switch#

        or

        .. code-block:: shell

            Flash complete.  Reboot this switch (y/n)? [n]


        If neither `prompt_name` nor `prompt_regex` is specified the prompt will be
        defaulted to

        .. code-block:: shell

            .+#$

        which should match any number of characters followed by a `#` at the end
        of the line.  This may be far too liberal for most installations.

    ssh_args:
        Extra optional arguments used for connecting to switch.

    key_accept:
        Wheather or not to accept the host key of the switch on initial login.
        Default: `False`

Connection NXAPI Args:

    transport:
        (REQUIRED) when `connection` is `nxapi`.
        Choices: `http, https`
        Default: `https`

    port:
        (REQUIRED) when `connection` is `nxapi`.
        Default: `80`

    verify:
        (REQUIRED) when `connection` is `nxapi`.
        Either a boolean, in which case it controls whether we verify the NX-API
        TLS certificate, or a string, in which case it must be a path to a CA bundle
        to use.
        Default: `True`

        When there is no certificate configuration on the device and this option is
        set as ``True`` (default), the commands will fail with the following error:
        ``SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed (_ssl.c:581)``.
        In this case, you either need to configure a proper certificate on the
        device (*recommended*), or bypass the checks setting this argument as ``False``
        with all the security risks considered.

        Check https://www.cisco.com/c/en/us/td/docs/switches/datacenter/nexus3000/sw/programmability/6_x/b_Cisco_Nexus_3000_Series_NX-OS_Programmability_Guide/b_Cisco_Nexus_3000_Series_NX-OS_Programmability_Guide_chapter_01.html
        to see how to properly configure the certificate.


The functions from the proxy minion can be run from the salt commandline using
the :mod:`salt.modules.nxos<salt.modules.nxos>` execution module.

.. note:
    If `multiprocessing: True` is set for the proxy minion config, each forked
    worker will open up a new connection to the Cisco NX OS Switch.  If you
    only want one consistent connection used for everything, use
    `multiprocessing: False`

'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import multiprocessing
import copy

# Import Salt libs
import salt.utils.nxos
from salt.utils.vt_helper import SSHConnection
from salt.utils.vt import TerminalException
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__file__)

__proxyenabled__ = ['nxos']
__virtualname__ = 'nxos'

# Globals used to maintain state for ssh and nxapi proxy minions
DEVICE_DETAILS = {'grains_cache': {}}
CONNECTION = 'ssh'
COPY_RS = 'copy running-config startup-config'


def __virtual__():
    '''
    Only return if all the modules are available
    '''
    log.info('nxos proxy __virtual__() called...')

    return __virtualname__


# -----------------------------------------------------------------------------
# Device Connection Connection Agnostic Functions
# -----------------------------------------------------------------------------
def init(opts=None):
    '''
    Required.
    Initialize device connection using ssh or nxapi connection type.
    '''
    global CONNECTION
    if __opts__.get('proxy').get('connection') is not None:
        CONNECTION = __opts__.get('proxy').get('connection')

    if CONNECTION == 'ssh':
        log.info('NXOS PROXY: Initialize ssh proxy connection')
        return _init_ssh(opts)
    elif CONNECTION == 'nxapi':
        log.info('NXOS PROXY: Initialize nxapi proxy connection')
        return _init_nxapi(opts)
    else:
        log.error('Unknown Connection Type: {0}'.format(CONNECTION))
        return False


def initialized():
    '''
    Since grains are loaded in many different places and some of those
    places occur before the proxy can be initialized, return whether the
    init() function has been called.
    '''
    if CONNECTION == 'ssh':
        return _initialized_ssh()
    elif CONNECTION == 'nxapi':
        return _initialized_nxapi()


def ping():
    '''
    Ping the device on the other end of the connection.

    .. code-block: bash

        salt '*' nxos.cmd ping
    '''
    if CONNECTION == 'ssh':
        return _ping_ssh()
    elif CONNECTION == 'nxapi':
        return _ping_nxapi()


def grains(**kwargs):
    '''
    Get grains for minion.

    .. code-block: bash

        salt '*' nxos.cmd grains
    '''
    import __main__ as main
    if not DEVICE_DETAILS['grains_cache']:
        data = sendline('show version')
        if CONNECTION == 'nxapi':
            data = data[0]
        ret = salt.utils.nxos.system_info(data)
        log.debug(ret)
        DEVICE_DETAILS['grains_cache'].update(ret['nxos'])
    return DEVICE_DETAILS['grains_cache']


def grains_refresh(**kwargs):
    '''
    Refresh the grains for the NX-OS device.

    .. code-block: bash

        salt '*' nxos.cmd grains_refresh
    '''
    DEVICE_DETAILS['grains_cache'] = {}
    return grains(**kwargs)


def shutdown(opts):
    '''
    Closes connection with the device.
    '''
    if CONNECTION == 'ssh':
        return _shutdown_ssh(opts)
    elif CONNECTION == 'nxapi':
        return _shutdown_nxapi(opts)


def sendline(command, method='cli_show_ascii'):
    '''
    Send arbitrary show or config commands to the NX-OS device.

    command
        The command to be sent.

    method:
        ``cli_show_ascii``: Return raw test or unstructured output.
        ``cli_show``: Return structured output.
        ``cli_conf``: Send configuration commands to the device.
        Defaults to ``cli_show_ascii``.

        NOTES for SSH proxy minon:
          ``method`` is ignored for SSH proxy minion.
          Only show commands are supported and data is returned unstructured.
          This function is preserved for backwards compatibilty.

    .. code-block: bash

        salt '*' nxos.cmd sendline 'show run | include "^username admin password"'
    '''
    try:
        if CONNECTION == 'ssh':
            result = _sendline_ssh(command)
        elif CONNECTION == 'nxapi':
            result = _nxapi_request(command, method)
    except (TerminalException, CommandExecutionError) as e:
        log.error(e)
        return 'Command {0} failed'.format(command)
    return result


def proxy_config(commands, **kwargs):
    '''
    Send configuration commands over SSH or NX-API

    commands
        List of configuration commands

    no_save_config
        If True, don't save configuration commands to startup configuration.
        If False, save configuration to startup configuration.
        Default: False

    .. code-block: bash

        salt '*' nxos.cmd proxy_config 'feature bgp' no_save_config=True
        salt '*' nxos.cmd proxy_config 'feature bgp'
    '''
    no_save_config = DEVICE_DETAILS['no_save_config']
    no_save_config = kwargs.get('no_save_config', no_save_config)
    if not isinstance(commands, list):
        commands = [commands]
    try:
        if CONNECTION == 'ssh':
            _sendline_ssh('config terminal')
            single_cmd = ''
            for cmd in commands:
                single_cmd += cmd + ' ; '
            ret = _sendline_ssh(single_cmd + 'end')
            if no_save_config:
                pass
            else:
                _sendline_ssh(COPY_RS)
            if ret:
                log.error(ret)
        elif CONNECTION == 'nxapi':
            ret = _nxapi_request(commands)
            if no_save_config:
                pass
            else:
                _nxapi_request(COPY_RS)
            for each in ret:
                if 'Failure' in each:
                    log.error(each)
    except (TerminalException, CommandExecutionError) as e:
        log.error(e)
        return [commands, repr(e)]
    return [commands, ret]


# -----------------------------------------------------------------------------
# SSH Transport Functions
# -----------------------------------------------------------------------------
def _init_ssh(opts):
    '''
    Open a connection to the NX-OS switch over SSH.
    '''
    if opts is None:
        opts = __opts__
    try:
        this_prompt = None
        if 'prompt_regex' in opts['proxy']:
            this_prompt = opts['proxy']['prompt_regex']
        elif 'prompt_name' in opts['proxy']:
            this_prompt = '{0}.*#'.format(opts['proxy']['prompt_name'])
        else:
            log.warning('nxos proxy configuration does not specify a prompt match.')
            this_prompt = '.+#$'

        DEVICE_DETAILS[_worker_name()] = SSHConnection(
            host=opts['proxy']['host'],
            username=opts['proxy']['username'],
            password=opts['proxy']['password'],
            key_accept=opts['proxy'].get('key_accept', False),
            ssh_args=opts['proxy'].get('ssh_args', ''),
            prompt=this_prompt)
        out, err = DEVICE_DETAILS[_worker_name()].sendline('terminal length 0')
        log.info('SSH session establised for process {}'.format(_worker_name()))
    except TerminalException as e:
        log.error(e)
        return False
    DEVICE_DETAILS['initialized'] = True
    DEVICE_DETAILS['no_save_config'] = opts['proxy'].get('no_save_config', False)


def _initialized_ssh():
    return DEVICE_DETAILS.get('initialized', False)


def _ping_ssh():
    if _worker_name() not in DEVICE_DETAILS:
        _init_ssh(None)
    try:
        return DEVICE_DETAILS[_worker_name()].conn.isalive()
    except TerminalException as e:
        log.error(e)
        return False


def _shutdown_ssh(opts):
    DEVICE_DETAILS[_worker_name()].close_connection()


def _sendline_ssh(command):
    if _ping_ssh() is False:
        _init_ssh(None)
    out, err = DEVICE_DETAILS[_worker_name()].sendline(command)
    _, out = out.split('\n', 1)
    out, _, _ = out.rpartition('\n')
    return out


def _worker_name():
    return multiprocessing.current_process().name


# -----------------------------------------------------------------------------
# NX-API Transport Functions
# -----------------------------------------------------------------------------
def _init_nxapi(opts):
    '''
    Open a connection to the NX-OS switch over NX-API.

    As the communication is HTTP(S) based, there is no connection to maintain,
    however, in order to test the connectivity and make sure we are able to
    bring up this Minion, we are executing a very simple command (``show clock``)
    which doesn't come with much overhead and it's sufficient to confirm we are
    indeed able to connect to the NX-API endpoint as configured.
    '''
    proxy_dict = opts.get('proxy', {})
    conn_args = copy.deepcopy(proxy_dict)
    conn_args.pop('proxytype', None)
    opts['multiprocessing'] = conn_args.pop('multiprocessing', True)
    # This is not a SSH-based proxy, so it should be safe to enable
    # multiprocessing.
    try:
        rpc_reply = __utils__['nxos.nxapi_request']('show clock', **conn_args)
        # Execute a very simple command to confirm we are able to connect properly
        DEVICE_DETAILS['conn_args'] = conn_args
        DEVICE_DETAILS['initialized'] = True
        DEVICE_DETAILS['up'] = True
        DEVICE_DETAILS['no_save_config'] = opts['proxy'].get('no_save_config', False)
    except CommandExecutionError:
        log.error('Unable to connect to %s', conn_args['host'], exc_info=True)
        raise
    log.info('nxapi DEVICE_DETAILS info: {}'.format(DEVICE_DETAILS))
    return True


def _initialized_nxapi():
    return DEVICE_DETAILS.get('initialized', False)


def _ping_nxapi():
    return DEVICE_DETAILS.get('up', False)


def _shutdown_nxapi(opts):
    log.debug('NXOS NX-API PROXY: Shutting Proxy Minion %s', opts['id'])


def _nxapi_request(commands, method='cli_conf', **kwargs):
    '''
    Executes an nxapi_request request over NX-API.

    commands
        The exec or config commands to be sent.

    method: ``cli_show``
        ``cli_show_ascii``: Return raw test or unstructured output.
        ``cli_show``: Return structured output.
        ``cli_conf``: Send configuration commands to the device.
        Defaults to ``cli_conf``.
    '''
    if CONNECTION == 'ssh':
        return '_nxapi_request is not available for ssh proxy'
    conn_args = DEVICE_DETAILS['conn_args']
    conn_args.update(kwargs)
    data = __utils__['nxos.nxapi_request'](commands, method=method, **conn_args)
    return data
