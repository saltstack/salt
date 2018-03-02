# -*- coding: utf-8 -*-
'''
NAPALM Network
===============

Basic methods for interaction with the network device through the virtual proxy 'napalm'.

:codeauthor: Mircea Ulinic <mircea@cloudflare.com> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------

- :mod:`napalm proxy minion <salt.proxy.napalm>`

.. versionadded:: 2016.11.0
.. versionchanged:: 2017.7.0
'''

from __future__ import absolute_import, unicode_literals, print_function

# Import Python lib
import logging
log = logging.getLogger(__name__)

# Import Salt libs
import salt.utils.files
import salt.utils.napalm
import salt.utils.templates
import salt.utils.versions

# Import 3rd-party libs
from salt.ext import six

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'net'
__proxyenabled__ = ['napalm']
# uses NAPALM-based proxy to interact with network devices

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    '''
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    '''
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------


def _filter_list(input_list, search_key, search_value):

    '''
    Filters a list of dictionary by a set of key-value pair.

    :param input_list:   is a list of dictionaries
    :param search_key:   is the key we are looking for
    :param search_value: is the value we are looking for the key specified in search_key
    :return:             filered list of dictionaries
    '''

    output_list = list()

    for dictionary in input_list:
        if dictionary.get(search_key) == search_value:
            output_list.append(dictionary)

    return output_list


def _filter_dict(input_dict, search_key, search_value):

    '''
    Filters a dictionary of dictionaries by a key-value pair.

    :param input_dict:    is a dictionary whose values are lists of dictionaries
    :param search_key:    is the key in the leaf dictionaries
    :param search_values: is the value in the leaf dictionaries
    :return:              filtered dictionary
    '''

    output_dict = dict()

    for key, key_list in six.iteritems(input_dict):
        key_list_filtered = _filter_list(key_list, search_key, search_value)
        if key_list_filtered:
            output_dict[key] = key_list_filtered

    return output_dict


def _explicit_close(napalm_device):
    '''
    Will explicily close the config session with the network device,
    when running in a now-always-alive proxy minion or regular minion.
    This helper must be used in configuration-related functions,
    as the session is preserved and not closed before making any changes.
    '''
    if salt.utils.napalm.not_always_alive(__opts__):
        # force closing the configuration session
        # when running in a non-always-alive proxy
        # or regular minion
        try:
            napalm_device['DRIVER'].close()
        except Exception as err:
            log.error('Unable to close the temp connection with the device:')
            log.error(err)
            log.error('Please report.')


def _config_logic(napalm_device,
                  loaded_result,
                  test=False,
                  commit_config=True,
                  loaded_config=None):

    '''
    Builds the config logic for `load_config` and `load_template` functions.
    '''

    # As the Salt logic is built around independent events
    # when it comes to configuration changes in the
    # candidate DB on the network devices, we need to
    # make sure we're using the same session.
    # Hence, we need to pass the same object around.
    # the napalm_device object is inherited from
    # the load_config or load_template functions
    # and forwarded to compare, discard, commit etc.
    # then the decorator will make sure that
    # if not proxy (when the connection is always alive)
    # and the `inherit_napalm_device` is set,
    # `napalm_device` will be overridden.
    # See `salt.utils.napalm.proxy_napalm_wrap` decorator.

    loaded_result['already_configured'] = False

    loaded_result['loaded_config'] = ''
    if loaded_config:
        loaded_result['loaded_config'] = loaded_config

    _compare = compare_config(inherit_napalm_device=napalm_device)
    if _compare.get('result', False):
        loaded_result['diff'] = _compare.get('out')
        loaded_result.pop('out', '')  # not needed
    else:
        loaded_result['diff'] = None
        loaded_result['result'] = False
        loaded_result['comment'] = _compare.get('comment')
        __context__['retcode'] = 1
        return loaded_result

    _loaded_res = loaded_result.get('result', False)
    if not _loaded_res or test:
        # if unable to load the config (errors / warnings)
        # or in testing mode,
        # will discard the config
        if loaded_result['comment']:
            loaded_result['comment'] += '\n'
        if not len(loaded_result.get('diff', '')) > 0:
            loaded_result['already_configured'] = True
        _discarded = discard_config(inherit_napalm_device=napalm_device)
        if not _discarded.get('result', False):
            loaded_result['comment'] += _discarded['comment'] if _discarded.get('comment') \
                                                              else 'Unable to discard config.'
            loaded_result['result'] = False
            # make sure it notifies
            # that something went wrong
            _explicit_close(napalm_device)
            __context__['retcode'] = 1
            return loaded_result

        loaded_result['comment'] += 'Configuration discarded.'
        # loaded_result['result'] = False not necessary
        # as the result can be true when test=True
        _explicit_close(napalm_device)
        if not loaded_result['result']:
            __context__['retcode'] = 1
        return loaded_result

    if not test and commit_config:
        # if not in testing mode and trying to commit
        if len(loaded_result.get('diff', '')) > 0:
            # if not testing mode
            # and also the user wants to commit (default)
            # and there are changes to commit
            _commit = commit(inherit_napalm_device=napalm_device)  # calls the function commit, defined below
            if not _commit.get('result', False):
                # if unable to commit
                loaded_result['comment'] += _commit['comment'] if _commit.get('comment') else 'Unable to commit.'
                loaded_result['result'] = False
                # unable to commit, something went wrong
                _discarded = discard_config(inherit_napalm_device=napalm_device)
                # try to discard, thus release the config DB
                if not _discarded.get('result', False):
                    loaded_result['comment'] += '\n'
                    loaded_result['comment'] += _discarded['comment'] if _discarded.get('comment') \
                        else 'Unable to discard config.'
        else:
            # would like to commit, but there's no change
            # need to call discard_config() to release the config DB
            _discarded = discard_config(inherit_napalm_device=napalm_device)
            if not _discarded.get('result', False):
                loaded_result['comment'] += _discarded['comment'] if _discarded.get('comment') \
                                                                  else 'Unable to discard config.'
                loaded_result['result'] = False
                # notify if anything goes wrong
                _explicit_close(napalm_device)
                __context__['retcode'] = 1
                return loaded_result
            loaded_result['already_configured'] = True
            loaded_result['comment'] = 'Already configured.'
    _explicit_close(napalm_device)
    if not loaded_result['result']:
        __context__['retcode'] = 1
    return loaded_result


# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


@salt.utils.napalm.proxy_napalm_wrap
def connected(**kwargs):  # pylint: disable=unused-argument
    '''
    Specifies if the connection to the device succeeded.

    CLI Example:

    .. code-block:: bash

        salt '*' net.connected
    '''

    return {
        'out': napalm_device.get('UP', False)  # pylint: disable=undefined-variable
    }


@salt.utils.napalm.proxy_napalm_wrap
def facts(**kwargs):  # pylint: disable=unused-argument
    '''
    Returns characteristics of the network device.
    :return: a dictionary with the following keys:

        * uptime - Uptime of the device in seconds.
        * vendor - Manufacturer of the device.
        * model - Device model.
        * hostname - Hostname of the device
        * fqdn - Fqdn of the device
        * os_version - String with the OS version running on the device.
        * serial_number - Serial number of the device
        * interface_list - List of the interfaces of the device

    CLI Example:

    .. code-block:: bash

        salt '*' net.facts

    Example output:

    .. code-block:: python

        {
            'os_version': '13.3R6.5',
            'uptime': 10117140,
            'interface_list': [
                'lc-0/0/0',
                'pfe-0/0/0',
                'pfh-0/0/0',
                'xe-0/0/0',
                'xe-0/0/1',
                'xe-0/0/2',
                'xe-0/0/3',
                'gr-0/0/10',
                'ip-0/0/10'
            ],
            'vendor': 'Juniper',
            'serial_number': 'JN131356FBFA',
            'model': 'MX480',
            'hostname': 're0.edge05.syd01',
            'fqdn': 're0.edge05.syd01'
        }
    '''

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'get_facts',
        **{
        }
    )


@salt.utils.napalm.proxy_napalm_wrap
def environment(**kwargs):  # pylint: disable=unused-argument
    '''
    Returns the environment of the device.

    CLI Example:

    .. code-block:: bash

        salt '*' net.environment


    Example output:

    .. code-block:: python

        {
            'fans': {
                'Bottom Rear Fan': {
                    'status': True
                },
                'Bottom Middle Fan': {
                    'status': True
                },
                'Top Middle Fan': {
                    'status': True
                },
                'Bottom Front Fan': {
                    'status': True
                },
                'Top Front Fan': {
                    'status': True
                },
                'Top Rear Fan': {
                    'status': True
                }
            },
            'memory': {
                'available_ram': 16349,
                'used_ram': 4934
            },
            'temperature': {
               'FPC 0 Exhaust A': {
                    'is_alert': False,
                    'temperature': 35.0,
                    'is_critical': False
                }
            },
            'cpu': {
                '1': {
                    '%usage': 19.0
                },
                '0': {
                    '%usage': 35.0
                }
            }
        }
    '''

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'get_environment',
        **{
        }
    )


@salt.utils.napalm.proxy_napalm_wrap
def cli(*commands, **kwargs):  # pylint: disable=unused-argument
    '''
    Returns a dictionary with the raw output of all commands passed as arguments.

    commands
        List of commands to be executed on the device.

    textfsm_parse: ``False``
        Try parsing the outputs using the TextFSM templates.

        .. versionadded:: 2018.3.0

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``napalm_cli_textfsm_parse``.

    textfsm_path
        The path where the TextFSM templates can be found. This option implies
        the usage of the TextFSM index file.
        ``textfsm_path`` can be either absolute path on the server,
        either specified using the following URL mschemes: ``file://``,
        ``salt://``, ``http://``, ``https://``, ``ftp://``,
        ``s3://``, ``swift://``.

        .. versionadded:: 2018.3.0

        .. note::
            This needs to be a directory with a flat structure, having an
            index file (whose name can be specified using the ``index_file`` option)
            and a number of TextFSM templates.

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``textfsm_path``.

    textfsm_template
        The path to a certain the TextFSM template.
        This can be specified using the absolute path
        to the file, or using one of the following URL schemes:

        - ``salt://``, to fetch the template from the Salt fileserver.
        - ``http://`` or ``https://``
        - ``ftp://``
        - ``s3://``
        - ``swift://``

        .. versionadded:: 2018.3.0

    textfsm_template_dict
        A dictionary with the mapping between a command
        and the corresponding TextFSM path to use to extract the data.
        The TextFSM paths can be specified as in ``textfsm_template``.

        .. versionadded:: 2018.3.0

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``napalm_cli_textfsm_template_dict``.

    platform_grain_name: ``os``
        The name of the grain used to identify the platform name
        in the TextFSM index file. Default: ``os``.

        .. versionadded:: 2018.3.0

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``textfsm_platform_grain``.

    platform_column_name: ``Platform``
        The column name used to identify the platform,
        exactly as specified in the TextFSM index file.
        Default: ``Platform``.

        .. versionadded:: 2018.3.0

        .. note::
            This is field is case sensitive, make sure
            to assign the correct value to this option,
            exactly as defined in the index file.

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``textfsm_platform_column_name``.

    index_file: ``index``
        The name of the TextFSM index file, under the ``textfsm_path``. Default: ``index``.

        .. versionadded:: 2018.3.0

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``textfsm_index_file``.

    saltenv: ``base``
        Salt fileserver envrionment from which to retrieve the file.
        Ignored if ``textfsm_path`` is not a ``salt://`` URL.

        .. versionadded:: 2018.3.0

    include_empty: ``False``
        Include empty files under the ``textfsm_path``.

        .. versionadded:: 2018.3.0

    include_pat
        Glob or regex to narrow down the files cached from the given path.
        If matching with a regex, the regex must be prefixed with ``E@``,
        otherwise the expression will be interpreted as a glob.

        .. versionadded:: 2018.3.0

    exclude_pat
        Glob or regex to exclude certain files from being cached from the given path.
        If matching with a regex, the regex must be prefixed with ``E@``,
        otherwise the expression will be interpreted as a glob.

        .. versionadded:: 2018.3.0

        .. note::
            If used with ``include_pat``, files matching this pattern will be
            excluded from the subset of files defined by ``include_pat``.

    CLI Example:

    .. code-block:: bash

        salt '*' net.cli "show version" "show chassis fan"

    CLI Example with TextFSM template:

    .. code-block:: bash

        salt '*' net.cli textfsm_parse=True textfsm_path=salt://textfsm/

    Example output:

    .. code-block:: python

        {
            'show version and haiku':  'Hostname: re0.edge01.arn01
                                          Model: mx480
                                          Junos: 13.3R6.5
                                            Help me, Obi-Wan
                                            I just saw Episode Two
                                            You're my only hope
                                         ',
            'show chassis fan' :   'Item                      Status   RPM     Measurement
                                      Top Rear Fan              OK       3840    Spinning at intermediate-speed
                                      Bottom Rear Fan           OK       3840    Spinning at intermediate-speed
                                      Top Middle Fan            OK       3900    Spinning at intermediate-speed
                                      Bottom Middle Fan         OK       3840    Spinning at intermediate-speed
                                      Top Front Fan             OK       3810    Spinning at intermediate-speed
                                      Bottom Front Fan          OK       3840    Spinning at intermediate-speed
                                     '
        }

    Example output with TextFSM parsing:

    .. code-block:: json

        {
          "comment": "",
          "result": true,
          "out": {
            "sh ver": [
              {
                "kernel": "9.1S3.5",
                "documentation": "9.1S3.5",
                "boot": "9.1S3.5",
                "crypto": "9.1S3.5",
                "chassis": "",
                "routing": "9.1S3.5",
                "base": "9.1S3.5",
                "model": "mx960"
              }
            ]
          }
        }
    '''
    raw_cli_outputs = salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'cli',
        **{
            'commands': list(commands)
        }
    )
    # thus we can display the output as is
    # in case of errors, they'll be catched in the proxy
    if not raw_cli_outputs['result']:
        # Error -> dispaly the output as-is.
        return raw_cli_outputs
    textfsm_parse = kwargs.get('textfsm_parse') or __opts__.get('napalm_cli_textfsm_parse') or\
                    __pillar__.get('napalm_cli_textfsm_parse', False)
    if not textfsm_parse:
        # No TextFSM parsing required, return raw commands.
        log.debug('No TextFSM parsing requested.')
        return raw_cli_outputs
    if 'textfsm.extract' not in __salt__ or 'textfsm.index' not in __salt__:
        raw_cli_outputs['comment'] += 'Unable to process: is TextFSM installed?'
        log.error(raw_cli_outputs['comment'])
        return raw_cli_outputs
    textfsm_template = kwargs.get('textfsm_template')
    log.debug('textfsm_template: %s', textfsm_template)
    textfsm_path = kwargs.get('textfsm_path') or __opts__.get('textfsm_path') or\
                   __pillar__.get('textfsm_path')
    log.debug('textfsm_path: %s', textfsm_path)
    textfsm_template_dict = kwargs.get('textfsm_template_dict') or __opts__.get('napalm_cli_textfsm_template_dict') or\
                            __pillar__.get('napalm_cli_textfsm_template_dict', {})
    log.debug('TextFSM command-template mapping: %s', textfsm_template_dict)
    index_file = kwargs.get('index_file') or __opts__.get('textfsm_index_file') or\
                 __pillar__.get('textfsm_index_file')
    log.debug('index_file: %s', index_file)
    platform_grain_name = kwargs.get('platform_grain_name') or __opts__.get('textfsm_platform_grain') or\
                          __pillar__.get('textfsm_platform_grain', 'os')
    log.debug('platform_grain_name: %s', platform_grain_name)
    platform_column_name = kwargs.get('platform_column_name') or __opts__.get('textfsm_platform_column_name') or\
                           __pillar__.get('textfsm_platform_column_name', 'Platform')
    log.debug('platform_column_name: %s', platform_column_name)
    saltenv = kwargs.get('saltenv', 'base')
    include_empty = kwargs.get('include_empty', False)
    include_pat = kwargs.get('include_pat')
    exclude_pat = kwargs.get('exclude_pat')
    processed_cli_outputs = {
        'comment': raw_cli_outputs.get('comment', ''),
        'result': raw_cli_outputs['result'],
        'out': {}
    }
    log.debug('Starting to analyse the raw outputs')
    for command in list(commands):
        command_output = raw_cli_outputs['out'][command]
        log.debug('Output from command: %s', command)
        log.debug(command_output)
        processed_command_output = None
        if textfsm_path:
            log.debug('Using the templates under %s', textfsm_path)
            processed_cli_output = __salt__['textfsm.index'](command,
                                                             platform_grain_name=platform_grain_name,
                                                             platform_column_name=platform_column_name,
                                                             output=command_output.strip(),
                                                             textfsm_path=textfsm_path,
                                                             saltenv=saltenv,
                                                             include_empty=include_empty,
                                                             include_pat=include_pat,
                                                             exclude_pat=exclude_pat)
            log.debug('Processed CLI output:')
            log.debug(processed_cli_output)
            if not processed_cli_output['result']:
                log.debug('Apparently this didnt work, returnin the raw output')
                processed_command_output = command_output
                processed_cli_outputs['comment'] += '\nUnable to process the output from {0}: {1}.'.format(command,
                    processed_cli_output['comment'])
                log.error(processed_cli_outputs['comment'])
            elif processed_cli_output['out']:
                log.debug('All good, %s has a nice output!', command)
                processed_command_output = processed_cli_output['out']
            else:
                comment = '''\nProcessing "{}" didn't fail, but didn't return anything either. Dumping raw.'''.format(
                    command)
                processed_cli_outputs['comment'] += comment
                log.error(comment)
                processed_command_output = command_output
        elif textfsm_template or command in textfsm_template_dict:
            if command in textfsm_template_dict:
                textfsm_template = textfsm_template_dict[command]
            log.debug('Using %s to process the command: %s', textfsm_template, command)
            processed_cli_output = __salt__['textfsm.extract'](textfsm_template,
                                                               raw_text=command_output,
                                                               saltenv=saltenv)
            log.debug('Processed CLI output:')
            log.debug(processed_cli_output)
            if not processed_cli_output['result']:
                log.debug('Apparently this didnt work, returning '
                          'the raw output')
                processed_command_output = command_output
                processed_cli_outputs['comment'] += '\nUnable to process the output from {0}: {1}'.format(command,
                    processed_cli_output['comment'])
                log.error(processed_cli_outputs['comment'])
            elif processed_cli_output['out']:
                log.debug('All good, %s has a nice output!', command)
                processed_command_output = processed_cli_output['out']
            else:
                log.debug('Processing %s didnt fail, but didnt return'
                          ' anything either. Dumping raw.', command)
                processed_command_output = command_output
        else:
            log.error('No TextFSM template specified, or no TextFSM path defined')
            processed_command_output = command_output
            processed_cli_outputs['comment'] += '\nUnable to process the output from {}.'.format(command)
        processed_cli_outputs['out'][command] = processed_command_output
    processed_cli_outputs['comment'] = processed_cli_outputs['comment'].strip()
    return processed_cli_outputs


@salt.utils.napalm.proxy_napalm_wrap
def traceroute(destination, source=None, ttl=None, timeout=None, vrf=None, **kwargs):  # pylint: disable=unused-argument

    '''
    Calls the method traceroute from the NAPALM driver object and returns a dictionary with the result of the traceroute
    command executed on the device.

    destination
        Hostname or address of remote host

    source
        Source address to use in outgoing traceroute packets

    ttl
        IP maximum time-to-live value (or IPv6 maximum hop-limit value)

    timeout
        Number of seconds to wait for response (seconds)

    vrf
        VRF (routing instance) for traceroute attempt

        .. versionadded:: 2016.11.4

    CLI Example:

    .. code-block:: bash

        salt '*' net.traceroute 8.8.8.8
        salt '*' net.traceroute 8.8.8.8 source=127.0.0.1 ttl=5 timeout=1
    '''

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'traceroute',
        **{
            'destination': destination,
            'source': source,
            'ttl': ttl,
            'timeout': timeout,
            'vrf': vrf
        }
    )


@salt.utils.napalm.proxy_napalm_wrap
def ping(destination, source=None, ttl=None, timeout=None, size=None, count=None, vrf=None, **kwargs):  # pylint: disable=unused-argument

    '''
    Executes a ping on the network device and returns a dictionary as a result.

    destination
        Hostname or IP address of remote host

    source
        Source address of echo request

    ttl
        IP time-to-live value (IPv6 hop-limit value) (1..255 hops)

    timeout
        Maximum wait time after sending final packet (seconds)

    size
        Size of request packets (0..65468 bytes)

    count
        Number of ping requests to send (1..2000000000 packets)

    vrf
        VRF (routing instance) for ping attempt

        .. versionadded:: 2016.11.4

    CLI Example:

    .. code-block:: bash

        salt '*' net.ping 8.8.8.8
        salt '*' net.ping 8.8.8.8 ttl=3 size=65468
        salt '*' net.ping 8.8.8.8 source=127.0.0.1 timeout=1 count=100
    '''

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'ping',
        **{
            'destination': destination,
            'source': source,
            'ttl': ttl,
            'timeout': timeout,
            'size': size,
            'count': count,
            'vrf': vrf
        }
    )


@salt.utils.napalm.proxy_napalm_wrap
def arp(interface='', ipaddr='', macaddr='', **kwargs):  # pylint: disable=unused-argument

    '''
    NAPALM returns a list of dictionaries with details of the ARP entries.

    :param interface: interface name to filter on
    :param ipaddr: IP address to filter on
    :param macaddr: MAC address to filter on
    :return: List of the entries in the ARP table

    CLI Example:

    .. code-block:: bash

        salt '*' net.arp
        salt '*' net.arp macaddr='5c:5e:ab:da:3c:f0'

    Example output:

    .. code-block:: python

        [
            {
                'interface' : 'MgmtEth0/RSP0/CPU0/0',
                'mac'       : '5c:5e:ab:da:3c:f0',
                'ip'        : '172.17.17.1',
                'age'       : 1454496274.84
            },
            {
                'interface': 'MgmtEth0/RSP0/CPU0/0',
                'mac'       : '66:0e:94:96:e0:ff',
                'ip'        : '172.17.17.2',
                'age'       : 1435641582.49
            }
        ]
    '''

    proxy_output = salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'get_arp_table',
        **{
        }
    )

    if not proxy_output.get('result'):
        return proxy_output

    arp_table = proxy_output.get('out')

    if interface:
        arp_table = _filter_list(arp_table, 'interface', interface)

    if ipaddr:
        arp_table = _filter_list(arp_table, 'ip', ipaddr)

    if macaddr:
        arp_table = _filter_list(arp_table, 'mac', macaddr)

    proxy_output.update({
        'out': arp_table
    })

    return proxy_output


@salt.utils.napalm.proxy_napalm_wrap
def ipaddrs(**kwargs):  # pylint: disable=unused-argument

    '''
    Returns IP addresses configured on the device.


    :return:   A dictionary with the IPv4 and IPv6 addresses of the interfaces.\
    Returns all configured IP addresses on all interfaces as a dictionary of dictionaries.\
    Keys of the main dictionary represent the name of the interface.\
    Values of the main dictionary represent are dictionaries that may consist of two keys\
    'ipv4' and 'ipv6' (one, both or none) which are themselvs dictionaries with the IP addresses as keys.\

    CLI Example:

    .. code-block:: bash

        salt '*' net.ipaddrs

    Example output:

    .. code-block:: python

        {
            'FastEthernet8': {
                'ipv4': {
                    '10.66.43.169': {
                        'prefix_length': 22
                    }
                }
            },
            'Loopback555': {
                'ipv4': {
                    '192.168.1.1': {
                        'prefix_length': 24
                    }
                },
                'ipv6': {
                    '1::1': {
                        'prefix_length': 64
                    },
                    '2001:DB8:1::1': {
                        'prefix_length': 64
                    },
                    'FE80::3': {
                        'prefix_length': 'N/A'
                    }
                }
            }
        }
    '''

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'get_interfaces_ip',
        **{
        }
    )


@salt.utils.napalm.proxy_napalm_wrap
def interfaces(**kwargs):  # pylint: disable=unused-argument

    '''
    Returns details of the interfaces on the device.

    :return: Returns a dictionary of dictionaries. \
    The keys for the first dictionary will be the interfaces in the devices.

    CLI Example:

    .. code-block:: bash

        salt '*' net.interfaces

    Example output:

    .. code-block:: python

        {
            'Management1': {
                'is_up': False,
                'is_enabled': False,
                'description': '',
                'last_flapped': -1,
                'speed': 1000,
                'mac_address': 'dead:beef:dead',
            },
            'Ethernet1':{
                'is_up': True,
                'is_enabled': True,
                'description': 'foo',
                'last_flapped': 1429978575.1554043,
                'speed': 1000,
                'mac_address': 'beef:dead:beef',
            }
        }
    '''

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'get_interfaces',
        **{
        }
    )


@salt.utils.napalm.proxy_napalm_wrap
def lldp(interface='', **kwargs):  # pylint: disable=unused-argument

    '''
    Returns a detailed view of the LLDP neighbors.

    :param interface: interface name to filter on
    :return:          A dictionary with the LLDL neighbors.\
    The keys are the interfaces with LLDP activated on.

    CLI Example:

    .. code-block:: bash

        salt '*' net.lldp
        salt '*' net.lldp interface='TenGigE0/0/0/8'

    Example output:

    .. code-block:: python

        {
            'TenGigE0/0/0/8': [
                {
                    'parent_interface': 'Bundle-Ether8',
                    'interface_description': 'TenGigE0/0/0/8',
                    'remote_chassis_id': '8c60.4f69.e96c',
                    'remote_system_name': 'switch',
                    'remote_port': 'Eth2/2/1',
                    'remote_port_description': 'Ethernet2/2/1',
                    'remote_system_description': 'Cisco Nexus Operating System (NX-OS) Software 7.1(0)N1(1a)
                          TAC support: http://www.cisco.com/tac
                          Copyright (c) 2002-2015, Cisco Systems, Inc. All rights reserved.',
                    'remote_system_capab': 'B, R',
                    'remote_system_enable_capab': 'B'
                }
            ]
        }
    '''

    proxy_output = salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'get_lldp_neighbors_detail',
        **{
        }
    )

    if not proxy_output.get('result'):
        return proxy_output

    lldp_neighbors = proxy_output.get('out')

    if interface:
        lldp_neighbors = {interface: lldp_neighbors.get(interface)}

    proxy_output.update({
        'out': lldp_neighbors
    })

    return proxy_output


@salt.utils.napalm.proxy_napalm_wrap
def mac(address='', interface='', vlan=0, **kwargs):  # pylint: disable=unused-argument

    '''
    Returns the MAC Address Table on the device.

    :param address:   MAC address to filter on
    :param interface: Interface name to filter on
    :param vlan:      VLAN identifier
    :return:          A list of dictionaries representing the entries in the MAC Address Table

    CLI Example:

    .. code-block:: bash

        salt '*' net.mac
        salt '*' net.mac vlan=10

    Example output:

    .. code-block:: python

        [
            {
                'mac'       : '00:1c:58:29:4a:71',
                'interface' : 'xe-3/0/2',
                'static'    : False,
                'active'    : True,
                'moves'     : 1,
                'vlan'      : 10,
                'last_move' : 1454417742.58
            },
            {
                'mac'       : '8c:60:4f:58:e1:c1',
                'interface' : 'xe-1/0/1',
                'static'    : False,
                'active'    : True,
                'moves'     : 2,
                'vlan'      : 42,
                'last_move' : 1453191948.11
            }
        ]
    '''

    proxy_output = salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'get_mac_address_table',
        **{
        }
    )

    if not proxy_output.get('result'):
        # if negative, leave the output unchanged
        return proxy_output

    mac_address_table = proxy_output.get('out')

    if vlan and isinstance(vlan, int):
        mac_address_table = _filter_list(mac_address_table, 'vlan', vlan)

    if address:
        mac_address_table = _filter_list(mac_address_table, 'mac', address)

    if interface:
        mac_address_table = _filter_list(mac_address_table, 'interface', interface)

    proxy_output.update({
        'out': mac_address_table
    })

    return proxy_output


@salt.utils.napalm.proxy_napalm_wrap
def config(source=None, **kwargs):  # pylint: disable=unused-argument
    '''
    .. versionadded:: 2017.7.0

    Return the whole configuration of the network device.
    By default, it will return all possible configuration
    sources supported by the network device.
    At most, there will be:

    - running config
    - startup config
    - candidate config

    To return only one of the configurations, you can use
    the ``source`` argument.

    source (optional)
        Which configuration type you want to display, default is all of them.

        Options:

        - running
        - candidate
        - startup

    :return:
        The object returned is a dictionary with the following keys:

        - running (string): Representation of the native running configuration.
        - candidate (string): Representation of the native candidate configuration.
            If the device doesnt differentiate between running and startup
            configuration this will an empty string.
        - startup (string): Representation of the native startup configuration.
            If the device doesnt differentiate between running and startup
            configuration this will an empty string.

    CLI Example:

    .. code-block:: bash

        salt '*' net.config
        salt '*' net.config source=candidate
    '''
    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'get_config',
        **{
            'retrieve': source
        }
    )


@salt.utils.napalm.proxy_napalm_wrap
def optics(**kwargs):  # pylint: disable=unused-argument
    '''
    .. versionadded:: 2017.7.0

    Fetches the power usage on the various transceivers installed
    on the network device (in dBm), and returns a view that conforms with the
    OpenConfig model openconfig-platform-transceiver.yang.

    :return:
        Returns a dictionary where the keys are as listed below:
            * intf_name (unicode)
                * physical_channels
                    * channels (list of dicts)
                        * index (int)
                        * state
                            * input_power
                                * instant (float)
                                * avg (float)
                                * min (float)
                                * max (float)
                            * output_power
                                * instant (float)
                                * avg (float)
                                * min (float)
                                * max (float)
                            * laser_bias_current
                                * instant (float)
                                * avg (float)
                                * min (float)
                                * max (float)

    CLI Example:

    .. code-block:: bash

        salt '*' net.optics
    '''
    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'get_optics',
        **{
        }
    )

# <---- Call NAPALM getters --------------------------------------------------------------------------------------------

# ----- Configuration specific functions ------------------------------------------------------------------------------>


@salt.utils.napalm.proxy_napalm_wrap
def load_config(filename=None,
                text=None,
                test=False,
                commit=True,
                debug=False,
                replace=False,
                inherit_napalm_device=None,
                saltenv='base',
                **kwargs):  # pylint: disable=unused-argument
    '''
    Applies configuration changes on the device. It can be loaded from a file or from inline string.
    If you send both a filename and a string containing the configuration, the file has higher precedence.

    By default this function will commit the changes. If there are no changes, it does not commit and
    the flag ``already_configured`` will be set as ``True`` to point this out.

    To avoid committing the configuration, set the argument ``test`` to ``True`` and will discard (dry run).

    To keep the changes but not commit, set ``commit`` to ``False``.

    To replace the config, set ``replace`` to ``True``.

    filename
        Path to the file containing the desired configuration.
        This can be specified using the absolute path to the file,
        or using one of the following URL schemes:

        - ``salt://``, to fetch the template from the Salt fileserver.
        - ``http://`` or ``https://``
        - ``ftp://``
        - ``s3://``
        - ``swift://``

        .. versionchanged:: 2018.3.0

    text
        String containing the desired configuration.
        This argument is ignored when ``filename`` is specified.

    test: False
        Dry run? If set as ``True``, will apply the config, discard and return the changes. Default: ``False``
        and will commit the changes on the device.

    commit: True
        Commit? Default: ``True``.

    debug: False
        Debug mode. Will insert a new key under the output dictionary, as ``loaded_config`` containing the raw
        configuration loaded on the device.

        .. versionadded:: 2016.11.2

    replace: False
        Load and replace the configuration. Default: ``False``.

        .. versionadded:: 2016.11.2

    saltenv: ``base``
        Specifies the Salt environment name.

        .. versionadded:: 2018.3.0

    :return: a dictionary having the following keys:

    * result (bool): if the config was applied successfully. It is ``False`` only in case of failure. In case \
    there are no changes to be applied and successfully performs all operations it is still ``True`` and so will be \
    the ``already_configured`` flag (example below)
    * comment (str): a message for the user
    * already_configured (bool): flag to check if there were no changes applied
    * loaded_config (str): the configuration loaded on the device. Requires ``debug`` to be set as ``True``
    * diff (str): returns the config changes applied

    CLI Example:

    .. code-block:: bash

        salt '*' net.load_config text='ntp peer 192.168.0.1'
        salt '*' net.load_config filename='/absolute/path/to/your/file'
        salt '*' net.load_config filename='/absolute/path/to/your/file' test=True
        salt '*' net.load_config filename='/absolute/path/to/your/file' commit=False

    Example output:

    .. code-block:: python

        {
            'comment': 'Configuration discarded.',
            'already_configured': False,
            'result': True,
            'diff': '[edit interfaces xe-0/0/5]+   description "Adding a description";'
        }
    '''
    fun = 'load_merge_candidate'
    if replace:
        fun = 'load_replace_candidate'
    if salt.utils.napalm.not_always_alive(__opts__):
        # if a not-always-alive proxy
        # or regular minion
        # do not close the connection after loading the config
        # this will be handled in _config_logic
        # after running the other features:
        # compare_config, discard / commit
        # which have to be over the same session
        napalm_device['CLOSE'] = False  # pylint: disable=undefined-variable
    if filename:
        text = __salt__['cp.get_file_str'](filename, saltenv=saltenv)
        if text is False:
            # When using salt:// or https://, if the resource is not available,
            #   it will either raise an exception, or return False.
            ret = {
                'result': False,
                'out': None
            }
            ret['comment'] = 'Unable to read from {}. Please specify a valid file or text.'.format(filename)
            log.error(ret['comment'])
            return ret
    _loaded = salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        fun,
        **{
            'config': text
        }
    )
    loaded_config = None
    if debug:
        if filename:
            with salt.utils.files.fopen(filename) as rfh:
                loaded_config = salt.utils.stringutils.to_unicode(rfh.read())
        else:
            loaded_config = text
    return _config_logic(napalm_device,  # pylint: disable=undefined-variable
                         _loaded,
                         test=test,
                         commit_config=commit,
                         loaded_config=loaded_config)


@salt.utils.napalm.proxy_napalm_wrap
def load_template(template_name,
                  template_source=None,
                  template_path=None,
                  template_hash=None,
                  template_hash_name=None,
                  template_user='root',
                  template_group='root',
                  template_mode='755',
                  template_attrs='--------------e----',
                  saltenv=None,
                  template_engine='jinja',
                  skip_verify=False,
                  defaults=None,
                  test=False,
                  commit=True,
                  debug=False,
                  replace=False,
                  inherit_napalm_device=None,  # pylint: disable=unused-argument
                  **template_vars):
    '''
    Renders a configuration template (default: Jinja) and loads the result on the device.

    By default this function will commit the changes. If there are no changes,
    it does not commit, discards he config and the flag ``already_configured``
    will be set as ``True`` to point this out.

    To avoid committing the configuration, set the argument ``test`` to ``True``
    and will discard (dry run).

    To preserve the changes, set ``commit`` to ``False``.
    However, this is recommended to be used only in exceptional cases
    when there are applied few consecutive states
    and/or configuration changes.
    Otherwise the user might forget that the config DB is locked
    and the candidate config buffer is not cleared/merged in the running config.

    To replace the config, set ``replace`` to ``True``.

    .. warning::
        The support for native NAPALM templates will be dropped in Salt Fluorine.
        Implicitly, the ``template_path`` argument will be removed.

    template_name
        Identifies path to the template source.
        The template can be either stored on the local machine, either remotely.
        The recommended location is under the ``file_roots``
        as specified in the master config file.
        For example, let's suppose the ``file_roots`` is configured as:

        .. code-block:: yaml

            file_roots:
                base:
                    - /etc/salt/states

        Placing the template under ``/etc/salt/states/templates/example.jinja``,
        it can be used as ``salt://templates/example.jinja``.
        Alternatively, for local files, the user can specify the absolute path.
        If remotely, the source can be retrieved via ``http``, ``https`` or ``ftp``.

        Examples:

        - ``salt://my_template.jinja``
        - ``/absolute/path/to/my_template.jinja``
        - ``http://example.com/template.cheetah``
        - ``https:/example.com/template.mako``
        - ``ftp://example.com/template.py``

    template_source: None
        Inline config template to be rendered and loaded on the device.

    template_path: None
        Required only in case the argument ``template_name`` provides only the file basename
        when referencing a local template using the absolute path.
        E.g.: if ``template_name`` is specified as ``my_template.jinja``,
        in order to find the template, this argument must be provided:
        ``template_path: /absolute/path/to/``.

        .. note::
            This argument will be deprecated beginning with release codename ``Fluorine``.

    template_hash: None
        Hash of the template file. Format: ``{hash_type: 'md5', 'hsum': <md5sum>}``

        .. versionadded:: 2016.11.2

    template_hash_name: None
        When ``template_hash`` refers to a remote file,
        this specifies the filename to look for in that file.

        .. versionadded:: 2016.11.2

    template_group: root
        Owner of file.

        .. versionadded:: 2016.11.2

    template_user: root
        Group owner of file.

        .. versionadded:: 2016.11.2

    template_mode: 755
        Permissions of file.

        .. versionadded:: 2016.11.2

    template_attrs: "--------------e----"
        attributes of file. (see `man lsattr`)

        .. versionadded:: 2018.3.0

    saltenv: base
        Specifies the template environment.
        This will influence the relative imports inside the templates.

        .. versionadded:: 2016.11.2

    template_engine: jinja
        The following templates engines are supported:

        - :mod:`cheetah<salt.renderers.cheetah>`
        - :mod:`genshi<salt.renderers.genshi>`
        - :mod:`jinja<salt.renderers.jinja>`
        - :mod:`mako<salt.renderers.mako>`
        - :mod:`py<salt.renderers.py>`
        - :mod:`wempy<salt.renderers.wempy>`

        .. versionadded:: 2016.11.2

    skip_verify: True
        If ``True``, hash verification of remote file sources
        (``http://``, ``https://``, ``ftp://``) will be skipped,
        and the ``source_hash`` argument will be ignored.

        .. versionadded:: 2016.11.2

    test: False
        Dry run? If set to ``True``, will apply the config,
        discard and return the changes.
        Default: ``False`` and will commit the changes on the device.

    commit: True
        Commit? (default: ``True``)

    debug: False
        Debug mode. Will insert a new key under the output dictionary,
        as ``loaded_config`` containing the raw result after the template was rendered.

        .. versionadded:: 2016.11.2

    replace: False
        Load and replace the configuration.

        .. versionadded:: 2016.11.2

    defaults: None
        Default variables/context passed to the template.

        .. versionadded:: 2016.11.2

    **template_vars
        Dictionary with the arguments/context to be used when the template is rendered.

        .. note::

            Do not explicitly specify this argument.
            This represents any other variable that will be sent
            to the template rendering system.
            Please see the examples below!

    :return: a dictionary having the following keys:

    * result (bool): if the config was applied successfully. It is ``False`` only in case of failure. In case \
    there are no changes to be applied and successfully performs all operations it is still ``True`` and so will be \
    the ``already_configured`` flag (example below)
    * comment (str): a message for the user
    * already_configured (bool): flag to check if there were no changes applied
    * loaded_config (str): the configuration loaded on the device, after rendering the template. Requires ``debug`` \
    to be set as ``True``
    * diff (str): returns the config changes applied

    The template can use variables from the ``grains``, ``pillar`` or ``opts``, for example:

    .. code-block:: jinja

        {% set router_model = grains.get('model') -%}
        {% set router_vendor = grains.get('vendor') -%}
        {% set os_version = grains.get('version') -%}
        {% set hostname = pillar.get('proxy', {}).get('host') -%}
        {% if router_vendor|lower == 'juniper' %}
        system {
            host-name {{hostname}};
        }
        {% elif router_vendor|lower == 'cisco' %}
        hostname {{hostname}}
        {% endif %}

    CLI Examples:

    .. code-block:: bash

        salt '*' net.load_template set_ntp_peers peers=[192.168.0.1]  # uses NAPALM default templates

        # inline template:
        salt -G 'os:junos' net.load_template set_hostname template_source='system { host-name {{host_name}}; }' \
        host_name='MX480.lab'

        # inline template using grains info:
        salt -G 'os:junos' net.load_template set_hostname \
        template_source='system { host-name {{grains.model}}.lab; }'
        # if the device is a MX480, the command above will set the hostname as: MX480.lab

        # inline template using pillar data:
        salt -G 'os:junos' net.load_template set_hostname template_source='system { host-name {{pillar.proxy.host}}; }'

        salt '*' net.load_template my_template template_path='/tmp/tpl/' my_param='aaa'  # will commit
        salt '*' net.load_template my_template template_path='/tmp/tpl/' my_param='aaa' test=True  # dry run

        salt '*' net.load_template salt://templates/my_stuff.jinja debug=True  # equivalent of the next command
        salt '*' net.load_template my_stuff.jinja template_path=salt://templates/ debug=True

        # in case the template needs to include files that are not under the same path (e.g. http://),
        # to help the templating engine find it, you will need to specify the `saltenv` argument:
        salt '*' net.load_template my_stuff.jinja template_path=salt://templates saltenv=/path/to/includes debug=True

        # render a mako template:
        salt '*' net.load_template salt://templates/my_stuff.mako template_engine=mako debug=True

        # render remote template
        salt -G 'os:junos' net.load_template http://bit.ly/2fReJg7 test=True debug=True peers=['192.168.0.1']
        salt -G 'os:ios' net.load_template http://bit.ly/2gKOj20 test=True debug=True peers=['192.168.0.1']

    Example output:

    .. code-block:: python

        {
            'comment': '',
            'already_configured': False,
            'result': True,
            'diff': '[edit system]+  host-name edge01.bjm01',
            'loaded_config': 'system { host-name edge01.bjm01; }''
        }
    '''
    _rendered = ''
    _loaded = {
        'result': True,
        'comment': '',
        'out': None
    }
    loaded_config = None
    if template_path:
        salt.utils.versions.warn_until(
            'Fluorine',
            'Use of `template_path` detected. This argument will be removed in Salt Fluorine.'
        )
    # prechecks
    if template_engine not in salt.utils.templates.TEMPLATE_REGISTRY:
        _loaded.update({
            'result': False,
            'comment': 'Invalid templating engine! Choose between: {tpl_eng_opts}'.format(
                tpl_eng_opts=', '.join(list(salt.utils.templates.TEMPLATE_REGISTRY.keys()))
            )
        })
        return _loaded  # exit

    # to check if will be rendered by salt or NAPALM
    salt_render_prefixes = ('salt://', 'http://', 'https://', 'ftp://')
    salt_render = False
    for salt_render_prefix in salt_render_prefixes:
        if not salt_render:
            salt_render = salt_render or template_name.startswith(salt_render_prefix) or \
                          (template_path and template_path.startswith(salt_render_prefix))
    file_exists = __salt__['file.file_exists'](template_name)

    if template_source or template_path or file_exists or salt_render:
        # either inline template
        # either template in a custom path
        # either abs path send
        # either starts with salt:// and
        # then use Salt render system

        # if needed to render the template send as inline arg
        if template_source:
            # render the content
            if not saltenv:
                saltenv = template_path if template_path else 'base'  # either use the env from the path, either base
            _rendered = __salt__['file.apply_template_on_contents'](
                contents=template_source,
                template=template_engine,
                context=template_vars,
                defaults=defaults,
                saltenv=saltenv
            )
            if not isinstance(_rendered, six.string_types):
                if 'result' in _rendered:
                    _loaded['result'] = _rendered['result']
                else:
                    _loaded['result'] = False
                if 'comment' in _rendered:
                    _loaded['comment'] = _rendered['comment']
                else:
                    _loaded['comment'] = 'Error while rendering the template.'
                return _loaded
        else:
            if template_path and not file_exists:
                template_name = __salt__['file.join'](template_path, template_name)
                if not saltenv:
                    # no saltenv overridden
                    # use the custom template path
                    saltenv = template_path if not salt_render else 'base'
            elif salt_render and not saltenv:
                # if saltenv not overrided and path specified as salt:// or http:// etc.
                # will use the default environment, from the base
                saltenv = template_path if template_path else 'base'
            if not saltenv:
                # still not specified, default to `base`
                saltenv = 'base'
            # render the file - either local, either remote
            _rand_filename = __salt__['random.hash'](template_name, 'md5')
            _temp_file = __salt__['file.join']('/tmp', _rand_filename)
            _managed = __salt__['file.get_managed'](name=_temp_file,
                                                    source=template_name,  # abs path
                                                    source_hash=template_hash,
                                                    source_hash_name=template_hash_name,
                                                    user=template_user,
                                                    group=template_group,
                                                    mode=template_mode,
                                                    attrs=template_attrs,
                                                    template=template_engine,
                                                    context=template_vars,
                                                    defaults=defaults,
                                                    saltenv=saltenv,
                                                    skip_verify=skip_verify)
            if not isinstance(_managed, (list, tuple)) and isinstance(_managed, six.string_types):
                _loaded['comment'] = _managed
                _loaded['result'] = False
            elif isinstance(_managed, (list, tuple)) and not len(_managed) > 0:
                _loaded['result'] = False
                _loaded['comment'] = 'Error while rendering the template.'
            elif isinstance(_managed, (list, tuple)) and not len(_managed[0]) > 0:
                _loaded['result'] = False
                _loaded['comment'] = _managed[-1]  # contains the error message
            if _loaded['result']:  # all good
                _temp_tpl_file = _managed[0]
                _temp_tpl_file_exists = __salt__['file.file_exists'](_temp_tpl_file)
                if not _temp_tpl_file_exists:
                    _loaded['result'] = False
                    _loaded['comment'] = 'Error while rendering the template.'
                    return _loaded
                with salt.utils.files.fopen(_temp_tpl_file) as rfh:
                    _rendered = salt.utils.stringutils.to_unicode(rfh.read())
                __salt__['file.remove'](_temp_tpl_file)
            else:
                return _loaded  # exit

        if debug:  # all good, but debug mode required
            # valid output and debug mode
            loaded_config = _rendered
        if _loaded['result']:  # all good
            fun = 'load_merge_candidate'
            if replace:  # replace requested
                fun = 'load_replace_candidate'
            if salt.utils.napalm.not_always_alive(__opts__):
                # if a not-always-alive proxy
                # or regular minion
                # do not close the connection after loading the config
                # this will be handled in _config_logic
                # after running the other features:
                # compare_config, discard / commit
                # which have to be over the same session
                napalm_device['CLOSE'] = False  # pylint: disable=undefined-variable
            _loaded = salt.utils.napalm.call(
                napalm_device,  # pylint: disable=undefined-variable
                fun,
                **{
                    'config': _rendered
                }
            )
    else:
        # otherwise, use NAPALM render system, injecting pillar/grains/opts vars
        load_templates_params = defaults if defaults else {}
        load_templates_params.update(template_vars)
        load_templates_params.update(
            {
                'template_name': template_name,
                'template_source': template_source,  # inline template
                'template_path': template_path,
                'pillar': __pillar__,  # inject pillar content
                'grains': __grains__,  # inject grains content
                'opts': __opts__  # inject opts content
            }
        )
        if salt.utils.napalm.not_always_alive(__opts__):
            # if a not-always-alive proxy
            # or regular minion
            # do not close the connection after loading the config
            # this will be handled in _config_logic
            # after running the other features:
            # compare_config, discard / commit
            # which have to be over the same session
            # so we'll set the CLOSE global explicitely as False
            napalm_device['CLOSE'] = False  # pylint: disable=undefined-variable
        _loaded = salt.utils.napalm.call(
            napalm_device,  # pylint: disable=undefined-variable
            'load_template',
            **load_templates_params
        )
    return _config_logic(napalm_device,  # pylint: disable=undefined-variable
                         _loaded,
                         test=test,
                         commit_config=commit,
                         loaded_config=loaded_config)


@salt.utils.napalm.proxy_napalm_wrap
def commit(inherit_napalm_device=None, **kwargs):  # pylint: disable=unused-argument

    '''
    Commits the configuration changes made on the network device.

    CLI Example:

    .. code-block:: bash

        salt '*' net.commit
    '''

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'commit_config',
        **{}
    )


@salt.utils.napalm.proxy_napalm_wrap
def discard_config(inherit_napalm_device=None, **kwargs):  # pylint: disable=unused-argument

    """
    Discards the changes applied.

    CLI Example:

    .. code-block:: bash

        salt '*' net.discard_config
    """

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'discard_config',
        **{}
    )


@salt.utils.napalm.proxy_napalm_wrap
def compare_config(inherit_napalm_device=None, **kwargs):  # pylint: disable=unused-argument

    '''
    Returns the difference between the running config and the candidate config.

    CLI Example:

    .. code-block:: bash

        salt '*' net.compare_config
    '''

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'compare_config',
        **{}
    )


@salt.utils.napalm.proxy_napalm_wrap
def rollback(inherit_napalm_device=None, **kwargs):  # pylint: disable=unused-argument

    '''
    Rollbacks the configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' net.rollback
    '''

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'rollback',
        **{}
    )


@salt.utils.napalm.proxy_napalm_wrap
def config_changed(inherit_napalm_device=None, **kwargs):  # pylint: disable=unused-argument

    '''
    Will prompt if the configuration has been changed.

    :return: A tuple with a boolean that specifies if the config was changed on the device.\
    And a string that provides more details of the reason why the configuration was not changed.

    CLI Example:

    .. code-block:: bash

        salt '*' net.config_changed
    '''

    is_config_changed = False
    reason = ''
    try_compare = compare_config(inherit_napalm_device=napalm_device)  # pylint: disable=undefined-variable

    if try_compare.get('result'):
        if try_compare.get('out'):
            is_config_changed = True
        else:
            reason = 'Configuration was not changed on the device.'
    else:
        reason = try_compare.get('comment')

    return is_config_changed, reason


@salt.utils.napalm.proxy_napalm_wrap
def config_control(inherit_napalm_device=None, **kwargs):  # pylint: disable=unused-argument

    '''
    Will check if the configuration was changed.
    If differences found, will try to commit.
    In case commit unsuccessful, will try to rollback.

    :return: A tuple with a boolean that specifies if the config was changed/committed/rollbacked on the device.\
    And a string that provides more details of the reason why the configuration was not committed properly.

    CLI Example:

    .. code-block:: bash

        salt '*' net.config_control
    '''

    result = True
    comment = ''

    changed, not_changed_rsn = config_changed(inherit_napalm_device=napalm_device)  # pylint: disable=undefined-variable
    if not changed:
        return (changed, not_changed_rsn)

    # config changed, thus let's try to commit
    try_commit = commit()
    if not try_commit.get('result'):
        result = False
        comment = 'Unable to commit the changes: {reason}.\n\
        Will try to rollback now!'.format(
            reason=try_commit.get('comment')
        )
        try_rollback = rollback()
        if not try_rollback.get('result'):
            comment += '\nCannot rollback! {reason}'.format(
                reason=try_rollback.get('comment')
            )

    return result, comment

# <---- Configuration specific functions -------------------------------------------------------------------------------
