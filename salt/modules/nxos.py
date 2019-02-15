# -*- coding: utf-8 -*-
'''
Execution module for Cisco NX OS Switches.

.. versionadded:: 2016.11.0

This module supports execution using a Proxy Minion or Native Minion:
1) Proxy Minion: Connect over SSH or NX-API HTTP(S).
   See :mod:`salt.proxy.nxos <salt.proxy.nxos>` for proxy minion setup details.
2) Native Minion: Connect over NX-API Unix Domain Socket (UDS).
   Install the minion inside the GuestShell running on the NX-OS device.

:maturity:   new
:platform:   nxos

.. note::

    To use this module over remote NX-API the feature must be enabled on the
    NX-OS device by executing ``feature nxapi`` in configuration mode.

    This is not required for NX-API over UDS.

    Configuration example:

    .. code-block:: bash

        switch# conf t
        switch(config)# feature nxapi

    To check that NX-API is properly enabled, execute ``show nxapi``.

    Output example:

    .. code-block:: bash

        switch# show nxapi
        nxapi enabled
        HTTPS Listen on port 443

Native minon configuration options:

.. code-block:: yaml

    nxos:
      cookie: 'username'
      no_save_config: True

cookie
    Use the option to override the default cookie 'admin:local' when
    connecting over UDS and use 'username:local' instead. This is needed when
    running the salt-minion in the GuestShell using a non-admin user.

    This option is ignored for SSH and NX-API Proxy minions.

no_save_config:
    If False, 'copy running-config starting-config' is issues for every
        configuration command.
    If True, Running config is not saved to startup config
    Default: False

    The recommended approach is to use the `save_running_config` function
    instead of this option to improve performance.  The default behavior
    controlled by this option is preserved for backwards compatibility.


The APIs defined in this execution module can also be executed using
salt-call from the GuestShell environment as follows.

.. code-block:: bash

    salt-call --local nxos.show 'show lldp neighbors' raw_text

.. note::

    The functions in this module can be executed using either of the
    following syntactic forms.

    salt '*' nxos.cmd <function>
    salt '*' nxos.cmd get_user username=admin

    or

    salt '*' nxos.<function>
    salt '*' nxos.get_user username=admin

    The nxos.cmd <function> syntax is preserved for backwards compatibility.
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python stdlib
import logging
import difflib
import re
import ast

# Import Salt libs
from salt.utils.pycrypto import gen_hash, secure_password
import salt.utils.platform
import salt.utils.nxos
from salt.ext import six
from salt.exceptions import CommandExecutionError

__virtualname__ = 'nxos'

log = logging.getLogger(__name__)

DEVICE_DETAILS = {'grains_cache': {}}
COPY_RS = 'copy running-config startup-config'


def __virtual__():
    return __virtualname__


def ping(**kwargs):
    '''
    Ping the device on the other end of the connection.

    .. code-block: bash

        salt '*' nxos.cmd ping
    '''
    if salt.utils.platform.is_proxy():
        return __proxy__['nxos.ping']()
    return __utils__['nxos.ping'](**kwargs)


# -----------------------------------------------------------------------------
# Device Get Functions
# -----------------------------------------------------------------------------
def check_password(username, password, encrypted=False, **kwargs):
    '''
    Verify user password.

    username
        Username on which to perform password check

    password
        Password to check

    encrypted
        Whether or not the password is encrypted
        Default: False

    .. code-block: bash

        salt '*' nxos.cmd check_password username=admin password=admin
        salt '*' nxos.cmd check_password username=admin \\
            password='$5$2fWwO2vK$s7.Hr3YltMNHuhywQQ3nfOd.gAPHgs3SOBYYdGT3E.A' \\
            encrypted=True
    '''
    hash_algorithms = {'1': 'md5',
                       '2a': 'blowfish',
                       '5': 'sha256',
                       '6': 'sha512', }
    password_line = get_user(username, **kwargs)
    if not password_line:
        return None
    if '!' in password_line:
        return False
    cur_hash = re.search(r'(\$[0-6](?:\$[^$ ]+)+)', password_line).group(0)
    if encrypted is False:
        hash_type, cur_salt, hashed_pass = re.search(r'^\$([0-6])\$([^$]+)\$(.*)$', cur_hash).groups()
        new_hash = gen_hash(crypt_salt=cur_salt, password=password, algorithm=hash_algorithms[hash_type])
    else:
        new_hash = password
    if new_hash == cur_hash:
        return True
    return False


def check_role(username, role, **kwargs):
    '''
    Verify role assignment for user.

    .. code-block:: bash

        salt '*' nxos.cmd check_role username=admin role=network-admin
    '''
    return role in get_roles(username, **kwargs)


def cmd(command, *args, **kwargs):
    '''
    NOTE: This function is preserved for backwards compatibilty.  This allows
    commands to be executed using either of the following syntactic forms.

    salt '*' nxos.cmd <function>

    or

    salt '*' nxos.<function>

    command
        function from `salt.modules.nxos` to run

    args
        positional args to pass to `command` function

    kwargs
        key word arguments to pass to `command` function

    .. code-block:: bash

        salt '*' nxos.cmd sendline 'show ver'
        salt '*' nxos.cmd show_run
        salt '*' nxos.cmd check_password username=admin password='$5$lkjsdfoi$blahblahblah' encrypted=True
    '''
    for k in list(kwargs):
        if k.startswith('__pub_'):
            kwargs.pop(k)
    local_command = '.'.join(['nxos', command])
    log.info('local command: {}'.format(local_command))
    if local_command not in __salt__:
        return False
    return __salt__[local_command](*args, **kwargs)


def find(pattern, **kwargs):
    '''
    Find all instances where the pattern is in the running configuration.

    .. code-block:: bash

        salt '*' nxos.cmd find '^snmp-server.*$'

    .. note::
        This uses the `re.MULTILINE` regex format for python, and runs the
        regex against the whole show_run output.
    '''
    matcher = re.compile(pattern, re.MULTILINE)
    return matcher.findall(show_run(**kwargs))


def get_roles(username, **kwargs):
    '''
    Get roles assigned to a username.

    .. code-block: bash

        salt '*' nxos.cmd get_roles username=admin
    '''
    user = get_user(username)
    if not user:
        return []
    command = 'show user-account {0}'.format(username)
    info = ''
    info = show(command, **kwargs)
    if isinstance(info, list):
        info = info[0]
    roles = re.search(r'^\s*roles:(.*)$', info, re.MULTILINE)
    if roles:
        roles = roles.group(1).strip().split(' ')
    else:
        roles = []
    return roles


def get_user(username, **kwargs):
    '''
    Get username line from switch.

    .. code-block: bash

        salt '*' nxos.cmd get_user username=admin
    '''
    command = 'show run | include "^username {0} password 5 "'.format(username)
    info = ''
    info = show(command, **kwargs)
    if isinstance(info, list):
        info = info[0]
    return info


def grains(**kwargs):
    '''
    Get grains for minion.

    .. code-block: bash

        salt '*' nxos.cmd grains
    '''
    import __main__ as main
    if not DEVICE_DETAILS['grains_cache']:
        ret = salt.utils.nxos.system_info(show_ver(**kwargs))
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


def sendline(command, method='cli_show_ascii', **kwargs):
    '''
    Send arbitray commands to the NX-OS device.

    command
        The command to be sent.

    method:
        ``cli_show_ascii``: Return raw test or unstructured output.
        ``cli_show``: Return structured output.
        ``cli_conf``: Send configuration commands to the device.
        Defaults to ``cli_show_ascii``.
        NOTE: method is ignored for SSH proxy minion.  All data is returned
        unstructured.

    .. code-block: bash

        salt '*' nxos.cmd sendline 'show run | include "^username admin password"'
    '''
    smethods = ['cli_show_ascii', 'cli_show', 'cli_conf']
    if method not in smethods:
        msg = "INPUT ERROR: Second argument 'method' must be one of %s" % smethods
        msg = msg + "\n  Value passed: %s" % method
        msg = msg + "\n  Hint: White space separated commands should be wrapped by double quotes"
        return msg

    if salt.utils.platform.is_proxy():
        return __proxy__['nxos.sendline'](command, method, **kwargs)
    else:
        return _nxapi_request(command, method, **kwargs)


def show(commands, raw_text=True, **kwargs):
    '''
    Execute one or more show (non-configuration) commands.

    commands
        The commands to be executed.

    raw_text: ``True``
        Whether to return raw text or structured data.
        NOTE: raw_text option is ignored for SSH proxy minion.  Data is
        returned unstructured.

    CLI Example:

    .. code-block:: bash

        salt-call --local nxos.show version
        salt '*' nxos.show 'bgp sessions ; processes' raw_text=False
        salt 'regular-minion' nxos.show interfaces host=sw01.example.com username=test password=test
    '''
    if not isinstance(raw_text, bool):
        msg = "INPUT ERROR: Second argument 'raw_text' must be either True or False"
        msg = msg + "\n  Value passed: %s" % raw_text
        msg = msg + "\n  Hint: White space separated show commands should be wrapped by double quotes"
        return msg

    if raw_text:
        method = 'cli_show_ascii'
    else:
        method = 'cli_show'

    commands = commands.replace('show', '').lstrip()
    response_list = sendline('show ' + commands, method, **kwargs)
    if isinstance(response_list, list):
        ret = [response for response in response_list if response]
        if not ret:
            ret = ['']
        return ret
    else:
        return response_list


def show_ver(**kwargs):
    '''
    Shortcut to run `show version` on the NX-OS device.

    .. code-block:: bash

        salt '*' nxos.cmd show_ver
    '''
    command = 'show version'
    info = ''
    info = show(command, **kwargs)
    if isinstance(info, list):
        info = info[0]
    return info


def show_run(**kwargs):
    '''
    Shortcut to run `show running-config` on the NX-OS device.

    .. code-block:: bash

        salt '*' nxos.cmd show_run
    '''
    command = 'show running-config'
    info = ''
    info = show(command, **kwargs)
    if isinstance(info, list):
        info = info[0]
    return info


def system_info(**kwargs):
    '''
    Return system information for grains of the minion.

    .. code-block:: bash

        salt '*' nxos.system_info
    '''
    return salt.utils.nxos.system_info(show_ver(**kwargs))['nxos']


# -----------------------------------------------------------------------------
# Device Get Functions
# -----------------------------------------------------------------------------
def add_config(lines, **kwargs):
    '''
    Add one or more config lines to the NX-OS device running config.

    lines
        Configuration lines to add

    no_save_config
        If True, don't save configuration commands to startup configuration.
        If False, save configuration to startup configuration.
        Default: False

    .. code-block:: bash

        salt '*' nxos.cmd add_config 'snmp-server community TESTSTRINGHERE group network-operator'

    .. note::
        For more than one config added per command, lines should be a list.
    '''
    return config(lines, **kwargs)


def config(commands=None,
           config_file=None,
           template_engine='jinja',
           context=None,
           defaults=None,
           saltenv='base',
           **kwargs):
    '''
    Configures the Nexus switch with the specified commands.

    This method is used to send configuration commands to the switch.  It
    will take either a string or a list and prepend the necessary commands
    to put the session into config mode.

    .. warning::

        All the commands will be applied directly to the running-config.

    config_file
        The source file with the configuration commands to be sent to the
        device.

        The file can also be a template that can be rendered using the template
        engine of choice.

        This can be specified using the absolute path to the file, or using one
        of the following URL schemes:

        - ``salt://``, to fetch the file from the Salt fileserver.
        - ``http://`` or ``https://``
        - ``ftp://``
        - ``s3://``
        - ``swift://``

    commands
        The commands to send to the switch in config mode.  If the commands
        argument is a string it will be cast to a list.
        The list of commands will also be prepended with the necessary commands
        to put the session in config mode.

        .. note::

            This argument is ignored when ``config_file`` is specified.

    template_engine: ``jinja``
        The template engine to use when rendering the source file. Default:
        ``jinja``. To simply fetch the file without attempting to render, set
        this argument to ``None``.

    context
        Variables to add to the template context.

    defaults
        Default values of the context_dict.

    no_save_config
        If True, don't save configuration commands to startup configuration.
        If False, save configuration to startup configuration.
        Default: False

    CLI Example:

    .. code-block:: bash

        salt '*' nxos.config commands="['spanning-tree mode mstp']"
        salt '*' nxos.config config_file=salt://config.txt
        salt '*' nxos.config config_file=https://bit.ly/2LGLcDy context="{'servers': ['1.2.3.4']}"
    '''
    initial_config = show('show running-config', **kwargs)
    if isinstance(initial_config, list):
        initial_config = initial_config[0]
    if config_file:
        file_str = __salt__['cp.get_file_str'](config_file, saltenv=saltenv)
        if file_str is False:
            raise CommandExecutionError('Source file {} not found'.format(config_file))
    elif commands:
        if isinstance(commands, (six.string_types, six.text_type)):
            commands = [commands]
        file_str = '\n'.join(commands)
        # unify all the commands in a single file, to render them in a go
    if template_engine:
        file_str = __salt__['file.apply_template_on_contents'](file_str,
                                                               template_engine,
                                                               context,
                                                               defaults,
                                                               saltenv)
    # whatever the source of the commands would be, split them line by line
    commands = [line for line in file_str.splitlines() if line.strip()]
    config_result = _parse_config_result(_configure_device(commands, **kwargs))
    current_config = show('show running-config', **kwargs)
    if isinstance(current_config, list):
        current_config = current_config[0]
    diff = difflib.unified_diff(initial_config.splitlines(1)[4:], current_config.splitlines(1)[4:])
    clean_diff = ''.join([x.replace('\r', '') for x in diff])
    head = 'COMMAND_LIST: '
    cc = config_result[0]
    cr = config_result[1]
    return head + cc + '\n' + cr + '\n' + clean_diff


def _parse_config_result(data):
    command_list = ' ; '.join([x.strip() for x in data[0]])
    config_result = data[1]
    if isinstance(config_result, list):
        result = ''
        if isinstance(config_result[0], dict):
            for key in config_result[0]:
                result += config_result[0][key]
            config_result = result
        else:
            config_result = config_result[0]
    return [command_list, config_result]


def delete_config(lines, **kwargs):
    '''
    Delete one or more config lines to the switch running config.

    lines
        Configuration lines to remove.

    no_save_config
        If True, don't save configuration commands to startup configuration.
        If False, save configuration to startup configuration.
        Default: False

    .. code-block:: bash

        salt '*' nxos.cmd delete_config 'snmp-server community TESTSTRINGHERE group network-operator'

    .. note::
        For more than one config deleted per command, lines should be a list.
    '''
    if not isinstance(lines, list):
        lines = [lines]
    for i, _ in enumerate(lines):
        lines[i] = 'no ' + lines[i]
    result = None
    try:
        result = config(lines, **kwargs)
    except CommandExecutionError as e:
        # Some commands will generate error code 400 if they do not exist
        # and we try to remove them.  These can be ignored.
        if ast.literal_eval(e.message)['code'] != '400':
            raise
    return result


def remove_user(username, **kwargs):
    '''
    Remove user from switch.

    username
        Username to remove

    no_save_config
        If True, don't save configuration commands to startup configuration.
        If False, save configuration to startup configuration.
        Default: False

    .. code-block:: bash

        salt '*' nxos.cmd remove_user username=daniel
    '''
    user_line = 'no username {0}'.format(username)
    return config(user_line, **kwargs)


def replace(old_value, new_value, full_match=False, **kwargs):
    '''
    Replace string or full line matches in switch's running config.

    If full_match is set to True, then the whole line will need to be matched
    as part of the old value.

    .. code-block:: bash

        salt '*' nxos.cmd replace 'TESTSTRINGHERE' 'NEWTESTSTRINGHERE'
    '''
    if full_match is False:
        matcher = re.compile('^.*{0}.*$'.format(re.escape(old_value)), re.MULTILINE)
        repl = re.compile(re.escape(old_value))
    else:
        matcher = re.compile(old_value, re.MULTILINE)
        repl = re.compile(old_value)

    lines = {'old': [], 'new': []}
    for line in matcher.finditer(show_run()):
        lines['old'].append(line.group(0))
        lines['new'].append(repl.sub(new_value, line.group(0)))

    delete_config(lines['old'], **kwargs)
    add_config(lines['new'], **kwargs)

    return lines


def save_running_config(**kwargs):
    '''
    Save the running configuration to startup configuration.

    .. code-block:: bash

        salt '*' nxos.save_running_config
    '''
    return config(COPY_RS, **kwargs)


def set_password(username,
                 password,
                 encrypted=False,
                 role=None,
                 crypt_salt=None,
                 algorithm='sha256',
                 **kwargs):
    '''
    Set users password on switch.

    username
        Username to configure

    password
        Password to configure for username

    encrypted
        Whether or not to encrypt the password
        Default: False

    role
        Configure role for the username
        Default: None

    crypt_salt
        Configure crypt_salt setting
        Default: None

    alogrithm
        Encryption algorithm
        Default: sha256

    no_save_config
        If True, don't save configuration commands to startup configuration.
        If False, save configuration to startup configuration.
        Default: False

    .. code-block:: bash

        salt '*' nxos.cmd set_password admin TestPass
        salt '*' nxos.cmd set_password admin \\
            password='$5$2fWwO2vK$s7.Hr3YltMNHuhywQQ3nfOd.gAPHgs3SOBYYdGT3E.A' \\
            encrypted=True
    '''
    password_line = get_user(username, **kwargs)
    if encrypted is False:
        if crypt_salt is None:
            # NXOS does not like non alphanumeric characters.  Using the random module from pycrypto
            # can lead to having non alphanumeric characters in the salt for the hashed password.
            crypt_salt = secure_password(8, use_random=False)
        hashed_pass = gen_hash(crypt_salt=crypt_salt, password=password, algorithm=algorithm)
    else:
        hashed_pass = password
    password_line = 'username {0} password 5 {1}'.format(username, hashed_pass)
    if role is not None:
        password_line += ' role {0}'.format(role)
    return config(password_line, **kwargs)


def set_role(username, role, **kwargs):
    '''
    Assign role to username.

    username
        Username for role configuration

    role
        Configure role for username

    no_save_config
        If True, don't save configuration commands to startup configuration.
        If False, save configuration to startup configuration.
        Default: False

    .. code-block:: bash

        salt '*' nxos.cmd set_role username=daniel role=vdc-admin.
    '''
    role_line = 'username {0} role {1}'.format(username, role)
    return config(role_line, **kwargs)


def unset_role(username, role, **kwargs):
    '''
    Remove role from username.

    username
        Username for role removal

    role
        Role to remove

    no_save_config
        If True, don't save configuration commands to startup configuration.
        If False, save configuration to startup configuration.
        Default: False

    .. code-block:: bash

        salt '*' nxos.cmd unset_role username=daniel role=vdc-admin
    '''
    role_line = 'no username {0} role {1}'.format(username, role)
    return config(role_line, **kwargs)


# -----------------------------------------------------------------------------
# helper functions
# -----------------------------------------------------------------------------
def _configure_device(commands, **kwargs):
    '''
    Helper function to send configuration commands to the device over a
    proxy minion or native minion using NX-API or SSH.
    '''
    if salt.utils.platform.is_proxy():
        return __proxy__['nxos.proxy_config'](commands, **kwargs)
    else:
        return _nxapi_config(commands, **kwargs)


def _nxapi_config(commands, methods='cli_conf', bsb_arg=None, **kwargs):
    '''
    Helper function to send configuration commands using NX-API.
    '''
    api_kwargs = __salt__['config.get']('nxos', {})
    api_kwargs.update(**kwargs)
    if not isinstance(commands, list):
        commands = [commands]
    try:
        ret = _nxapi_request(commands, **kwargs)
        if api_kwargs.get('no_save_config'):
            pass
        else:
            _nxapi_request(COPY_RS, **kwargs)
        for each in ret:
            if 'Failure' in each:
                log.error(each)
    except CommandExecutionError as e:
        log.error(e)
        return [commands, repr(e)]
    return [commands, ret]


def _nxapi_request(commands,
                   method='cli_conf',
                   **kwargs):
    '''
    Helper function to send exec and config requests over NX-API.

    commands
        The exec or config commands to be sent.

    method: ``cli_show``
        ``cli_show_ascii``: Return raw test or unstructured output.
        ``cli_show``: Return structured output.
        ``cli_conf``: Send configuration commands to the device.
        Defaults to ``cli_conf``.
    '''
    if salt.utils.platform.is_proxy():
        return __proxy__['nxos._nxapi_request'](commands, method=method, **kwargs)
    else:
        api_kwargs = __salt__['config.get']('nxos', {})
        api_kwargs.update(**kwargs)
        return __utils__['nxos.nxapi_request'](commands, method=method, **api_kwargs)
