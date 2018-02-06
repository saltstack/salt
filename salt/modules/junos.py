# -*- coding: utf-8 -*-
'''
Module to interact with Junos devices.

:maturity: new
:dependencies: junos-eznc, jxmlease

.. note::

    Those who wish to use junos-eznc (PyEZ) version >= 2.1.0, must
    use the latest salt code from github until the next release.

Refer to :mod:`junos <salt.proxy.junos>` for information on connecting to junos proxy.

'''

# Import Python libraries
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os

try:
    from lxml import etree
except ImportError:
    from salt._compat import ElementTree as etree

# Import Salt libs
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
from salt.ext import six

# Juniper interface libraries
# https://github.com/Juniper/py-junos-eznc
try:
    # pylint: disable=W0611
    from jnpr.junos import Device
    from jnpr.junos.utils.config import Config
    from jnpr.junos.utils.sw import SW
    from jnpr.junos.utils.scp import SCP
    import jnpr.junos.utils
    import jnpr.junos.cfg
    import jxmlease
    # pylint: enable=W0611
    HAS_JUNOS = True
except ImportError:
    HAS_JUNOS = False

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'junos'

__proxyenabled__ = ['junos']


def __virtual__():
    '''
    We need the Junos adapter libraries for this
    module to work.  We also need a proxymodule entry in __opts__
    in the opts dictionary
    '''
    if HAS_JUNOS and 'proxy' in __opts__:
        return __virtualname__
    else:
        return (False, 'The junos module could not be loaded: '
                       'junos-eznc or jxmlease or proxy could not be loaded.')


def facts_refresh():
    '''
    Reload the facts dictionary from the device. Usually only needed if,
    the device configuration is changed by some other actor.
    This function will also refresh the facts stored in the salt grains.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.facts_refresh

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True
    try:
        conn.facts_refresh()
    except Exception as exception:
        ret['message'] = 'Execution failed due to "{0}"'.format(exception)
        ret['out'] = False
        return ret

    ret['facts'] = __proxy__['junos.get_serialized_facts']()

    try:
        __salt__['saltutil.sync_grains']()
    except Exception as exception:
        log.error('Grains could not be updated due to "%s"', exception)
    return ret


def facts():
    '''
    Displays the facts gathered during the connection.
    These facts are also stored in Salt grains.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.facts

    '''
    ret = dict()
    try:
        ret['facts'] = __proxy__['junos.get_serialized_facts']()
        ret['out'] = True
    except Exception as exception:
        ret['message'] = 'Could not display facts due to "{0}"'.format(
            exception)
        ret['out'] = False
    return ret


def rpc(cmd=None, dest=None, format='xml', **kwargs):
    '''
    This function executes the rpc provided as arguments on the junos device.
    The returned data can be stored in a file.

    Usage:

    .. code-block:: bash

        salt 'device' junos.rpc 'get_config' '/var/log/config.txt' 'text' filter='<configuration><system/></configuration>'

        salt 'device' junos.rpc 'get-interface-information' '/home/user/interface.xml' interface_name='lo0' terse=True

        salt 'device' junos.rpc 'get-chassis-inventory'

    Parameters:
      Required
        * cmd:
          The rpc to be executed. (default = None)
      Optional
        * dest:
          Destination file where the rpc output is stored. (default = None)
          Note that the file will be stored on the proxy minion. To push the
          files to the master use the salt's following execution module:
          :py:func:`cp.push <salt.modules.cp.push>`
        * format:
          The format in which the rpc reply is received from the device.
          (default = xml)
        * kwargs: keyworded arguments taken by rpc call like-
            * dev_timeout:
              Set NETCONF RPC timeout. Can be used for commands which
              take a while to execute. (default= 30 seconds)
            * filter:
              Only to be used with 'get-config' rpc to get specific configuration.
            * terse:
              Amount of information you want.
            * interface_name:
              Name of the interface whose information you want.

    '''

    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True

    if cmd is None:
        ret['message'] = 'Please provide the rpc to execute.'
        ret['out'] = False
        return ret

    op = dict()
    if '__pub_arg' in kwargs:
        if kwargs['__pub_arg']:
            if isinstance(kwargs['__pub_arg'][-1], dict):
                op.update(kwargs['__pub_arg'][-1])
    elif '__pub_schedule' in kwargs:
        for key, value in six.iteritems(kwargs):
            if not key.startswith('__pub_'):
                op[key] = value
    else:
        op.update(kwargs)
    op['dev_timeout'] = six.text_type(op.pop('timeout', conn.timeout))

    if cmd in ['get-config', 'get_config']:
        filter_reply = None
        if 'filter' in op:
            filter_reply = etree.XML(op['filter'])
            del op['filter']

        op.update({'format': format})
        try:
            reply = getattr(
                conn.rpc,
                cmd.replace('-',
                            '_'))(filter_reply,
                                  options=op)
        except Exception as exception:
            ret['message'] = 'RPC execution failed due to "{0}"'.format(
                exception)
            ret['out'] = False
            return ret
    else:
        op['dev_timeout'] = int(op['dev_timeout'])
        if 'filter' in op:
            log.warning(
                'Filter ignored as it is only used with "get-config" rpc')
        try:
            reply = getattr(
                conn.rpc,
                cmd.replace('-',
                            '_'))({'format': format},
                                  **op)
        except Exception as exception:
            ret['message'] = 'RPC execution failed due to "{0}"'.format(
                exception)
            ret['out'] = False
            return ret

    if format == 'text':
        # Earlier it was ret['message']
        ret['rpc_reply'] = reply.text
    elif format == 'json':
        # Earlier it was ret['message']
        ret['rpc_reply'] = reply
    else:
        # Earlier it was ret['message']
        ret['rpc_reply'] = jxmlease.parse(etree.tostring(reply))

    if dest:
        if format == 'text':
            write_response = reply.text
        elif format == 'json':
            write_response = salt.utils.json.dumps(reply, indent=1)
        else:
            write_response = etree.tostring(reply)
        with salt.utils.files.fopen(dest, 'w') as fp:
            fp.write(salt.utils.stringutils.to_str(write_response))
    return ret


def set_hostname(hostname=None, **kwargs):
    '''
    To set the name of the device.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.set_hostname salt-device

    Parameters:
     Required
        * hostname: The name to be set. (default = None)
     Optional
        * kwargs: Keyworded arguments which can be provided like-
            * dev_timeout:
              Set NETCONF RPC timeout. Can be used for commands
              which take a while to execute. (default = 30 seconds)
            * comment:
              Provide a comment to the commit. (default = None)
            * confirm:
              Provide time in minutes for commit confirmation. \
              If this option is specified, the commit will be rollbacked in \
              the given time unless the commit is confirmed.

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    if hostname is None:
        ret['message'] = 'Please provide the hostname.'
        ret['out'] = False
        return ret

    op = dict()
    if '__pub_arg' in kwargs:
        if kwargs['__pub_arg']:
            if isinstance(kwargs['__pub_arg'][-1], dict):
                op.update(kwargs['__pub_arg'][-1])
    else:
        op.update(kwargs)

    # Added to recent versions of JunOs
    # Use text format instead
    set_string = 'set system host-name {0}'.format(hostname)
    try:
        conn.cu.load(set_string, format='set')
    except Exception as exception:
        ret['message'] = 'Could not load configuration due to error "{0}"'.format(
            exception)
        ret['out'] = False
        return ret

    try:
        commit_ok = conn.cu.commit_check()
    except Exception as exception:
        ret['message'] = 'Could not commit check due to error "{0}"'.format(
            exception)
        ret['out'] = False
        return ret

    if commit_ok:
        try:
            conn.cu.commit(**op)
            ret['message'] = 'Successfully changed hostname.'
            ret['out'] = True
        except Exception as exception:
            ret['out'] = False
            ret['message'] = 'Successfully loaded host-name but commit failed with "{0}"'.format(
                exception)
            return ret
    else:
        ret['out'] = False
        ret[
            'message'] = 'Successfully loaded host-name but pre-commit check failed.'
        conn.cu.rollback()
    return ret


def commit(**kwargs):
    '''
    To commit the changes loaded in the candidate configuration.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.commit comment='Commiting via saltstack' detail=True

        salt 'device_name' junos.commit dev_timeout=60 confirm=10

        salt 'device_name' junos.commit sync=True dev_timeout=90


    Parameters:
      Optional
        * kwargs: Keyworded arguments which can be provided like-
            * dev_timeout:
              Set NETCONF RPC timeout. Can be used for commands which take a \
              while to execute. (default = 30 seconds)
            * comment:
              Provide a comment to the commit. (default = None)
            * confirm:
              Provide time in minutes for commit confirmation. If this option \
              is specified, the commit will be rollbacked in the given time \
              unless the commit is confirmed.
            * sync:
              On dual control plane systems, requests that the candidate\
              configuration on one control plane be copied to the other \
              control plane,checked for correct syntax, and committed on \
              both Routing Engines. (default = False)
            * force_sync:
              On dual control plane systems, force the candidate configuration
              on one control plane to be copied to the other control plane.
            * full:
              When set to True requires all the daemons to check and evaluate \
              the new configuration.
            * detail:
              When true return commit detail.

    '''

    conn = __proxy__['junos.conn']()
    ret = {}
    op = dict()
    if '__pub_arg' in kwargs:
        if kwargs['__pub_arg']:
            if isinstance(kwargs['__pub_arg'][-1], dict):
                op.update(kwargs['__pub_arg'][-1])
    else:
        op.update(kwargs)

    op['detail'] = op.get('detail', False)

    try:
        commit_ok = conn.cu.commit_check()
    except Exception as exception:
        ret['message'] = 'Could not perform commit check due to "{0}"'.format(
            exception)
        ret['out'] = False
        return ret

    if commit_ok:
        try:
            commit = conn.cu.commit(**op)
            ret['out'] = True
            if commit:
                if op['detail']:
                    ret['message'] = jxmlease.parse(etree.tostring(commit))
                else:
                    ret['message'] = 'Commit Successful.'
            else:
                ret['message'] = 'Commit failed.'
                ret['out'] = False
        except Exception as exception:
            ret['out'] = False
            ret['message'] = \
                'Commit check succeeded but actual commit failed with "{0}"' \
                .format(exception)
    else:
        ret['out'] = False
        ret['message'] = 'Pre-commit check failed.'
        conn.cu.rollback()
    return ret


def rollback(id=0, **kwargs):
    '''
    To rollback the last committed configuration changes and commit the same.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.rollback 10

    Parameters:
      Optional
        * id:
          The rollback id value [0-49]. (default = 0)
        * kwargs: Keyworded arguments which can be provided like-
            * dev_timeout:
              Set NETCONF RPC timeout. Can be used for commands which
              take a while to execute. (default = 30 seconds)
            * comment:
              Provide a comment to the commit. (default = None)
            * confirm:
              Provide time in minutes for commit confirmation. If this option \
              is specified, the commit will be rollbacked in the given time \
              unless the commit is confirmed.
            * diffs_file:
              Path to the file where any diffs will be written. (default = None)

    '''

    ret = dict()
    conn = __proxy__['junos.conn']()

    op = dict()
    if '__pub_arg' in kwargs:
        if kwargs['__pub_arg']:
            if isinstance(kwargs['__pub_arg'][-1], dict):
                op.update(kwargs['__pub_arg'][-1])
    else:
        op.update(kwargs)

    try:
        ret['out'] = conn.cu.rollback(id)
    except Exception as exception:
        ret['message'] = 'Rollback failed due to "{0}"'.format(exception)
        ret['out'] = False
        return ret

    if ret['out']:
        ret['message'] = 'Rollback successful'
    else:
        ret['message'] = 'Rollback failed'
        return ret

    if 'diffs_file' in op and op['diffs_file'] is not None:
        diff = conn.cu.diff()
        if diff is not None:
            with salt.utils.files.fopen(op['diffs_file'], 'w') as fp:
                fp.write(salt.utils.stringutils.to_str(diff))
        else:
            log.info(
                'No diff between current configuration and \
                rollbacked configuration, so no diff file created')

    try:
        commit_ok = conn.cu.commit_check()
    except Exception as exception:
        ret['message'] = 'Could not commit check due to "{0}"'.format(
            exception)
        ret['out'] = False
        return ret

    if commit_ok:
        try:
            conn.cu.commit(**op)
            ret['out'] = True
        except Exception as exception:
            ret['out'] = False
            ret['message'] = \
                'Rollback successful but commit failed with error "{0}"'\
                .format(exception)
            return ret
    else:
        ret['message'] = 'Rollback succesfull but pre-commit check failed.'
        ret['out'] = False
    return ret


def diff(id=0):
    '''
    Gives the difference between the candidate and the current configuration.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.diff 3


    Parameters:
      Optional
        * id:
          The rollback id value [0-49]. (default = 0)

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True
    try:
        ret['message'] = conn.cu.diff(rb_id=id)
    except Exception as exception:
        ret['message'] = 'Could not get diff with error "{0}"'.format(
            exception)
        ret['out'] = False

    return ret


def ping(dest_ip=None, **kwargs):
    '''
    To send ping RPC to a device.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.ping '8.8.8.8' count=5

        salt 'device_name' junos.ping '8.8.8.8' ttl=1 rapid=True


    Parameters:
      Required
        * dest_ip:
          The IP which is to be pinged. (default = None)
      Optional
        * kwargs: Keyworded arguments which can be provided like-
            * dev_timeout:
              Set NETCONF RPC timeout. Can be used for commands which
              take a while to execute. (default = 30 seconds)
            * rapid:
              Setting this to True executes ping at 100pps instead of 1pps. \
              (default = False)
            * ttl:
              Maximum number of IP routers (IP hops) allowed between source \
              and destination.
            * routing_instance:
              Name of the routing instance to use to send the ping.
            * interface:
              Interface used to send traffic out.
            * count:
              Number of packets to send. (default = 5)

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()

    if dest_ip is None:
        ret['message'] = 'Please specify the destination ip to ping.'
        ret['out'] = False
        return ret

    op = {'host': dest_ip}
    if '__pub_arg' in kwargs:
        if kwargs['__pub_arg']:
            if isinstance(kwargs['__pub_arg'][-1], dict):
                op.update(kwargs['__pub_arg'][-1])
    else:
        op.update(kwargs)

    op['count'] = six.text_type(op.pop('count', 5))
    if 'ttl' in op:
        op['ttl'] = six.text_type(op['ttl'])

    ret['out'] = True
    try:
        ret['message'] = jxmlease.parse(etree.tostring(conn.rpc.ping(**op)))
    except Exception as exception:
        ret['message'] = 'Execution failed due to "{0}"'.format(exception)
        ret['out'] = False
    return ret


def cli(command=None, format='text', **kwargs):
    '''
    Executes the CLI commands and returns the output in specified format. \
    (default is text) The ouput can also be stored in a file.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.cli 'show system commit'

        salt 'device_name' junos.cli 'show version' dev_timeout=40

        salt 'device_name' junos.cli 'show system alarms' 'xml' dest=/home/user/cli_output.txt


    Parameters:
      Required
        * command:
          The command that need to be executed on Junos CLI. (default = None)
      Optional
        * format:
          Format in which to get the CLI output. (text or xml, \
            default = 'text')
        * kwargs: Keyworded arguments which can be provided like-
            * dev_timeout:
              Set NETCONF RPC timeout. Can be used for commands which
              take a while to execute. (default = 30 seconds)
            * dest:
              The destination file where the CLI output can be stored.\
               (default = None)

    '''
    conn = __proxy__['junos.conn']()

    # Cases like salt 'device_name' junos.cli 'show system alarms' ''
    # In this case the format becomes '' (empty string). And reply is sent in xml
    # We want the format to default to text.
    if not format:
        format = 'text'

    ret = dict()
    if command is None:
        ret['message'] = 'Please provide the CLI command to be executed.'
        ret['out'] = False
        return ret

    op = dict()
    if '__pub_arg' in kwargs:
        if kwargs['__pub_arg']:
            if isinstance(kwargs['__pub_arg'][-1], dict):
                op.update(kwargs['__pub_arg'][-1])
    else:
        op.update(kwargs)

    try:
        result = conn.cli(command, format, warning=False)
    except Exception as exception:
        ret['message'] = 'Execution failed due to "{0}"'.format(exception)
        ret['out'] = False
        return ret

    if format == 'text':
        ret['message'] = result
    else:
        result = etree.tostring(result)
        ret['message'] = jxmlease.parse(result)

    if 'dest' in op and op['dest'] is not None:
        with salt.utils.files.fopen(op['dest'], 'w') as fp:
            fp.write(salt.utils.stringutils.to_str(result))

    ret['out'] = True
    return ret


def shutdown(**kwargs):
    '''
    Shut down (power off) or reboot a device running Junos OS.
    This includes all Routing Engines in a Virtual Chassis or a dual Routing \
    Engine system.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.shutdown reboot=True

        salt 'device_name' junos.shutdown shutdown=True in_min=10

        salt 'device_name' junos.shutdown shutdown=True


    Parameters:
      Optional
        * kwargs:
            * shutdown:
              Set this to true if you want to shutdown the machine.
              (default=False, this is a safety mechanism so that the user does
              not accidentally shutdown the junos device.)
            * reboot:
              Whether to reboot instead of shutdown. (default=False)
              Note that either one of the above arguments has to be specified
              (shutdown or reboot) for this function to work.
            * at:
              Date and time the reboot should take place. The
              string must match the junos cli reboot syntax
              (To be used only if reboot=True)
            * in_min:
              Specify delay in minutes for shutdown

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    sw = SW(conn)

    op = dict()
    if '__pub_arg' in kwargs:
        if kwargs['__pub_arg']:
            if isinstance(kwargs['__pub_arg'][-1], dict):
                op.update(kwargs['__pub_arg'][-1])
    else:
        op.update(kwargs)
    if 'shutdown' not in op and 'reboot' not in op:
        ret['message'] = \
            'Provide either one of the arguments: shutdown or reboot.'
        ret['out'] = False
        return ret

    try:
        if 'reboot' in op and op['reboot']:
            shut = sw.reboot
        elif 'shutdown' in op and op['shutdown']:
            shut = sw.poweroff
        else:
            ret['message'] = 'Nothing to be done.'
            ret['out'] = False
            return ret

        if 'in_min' in op:
            shut(in_min=op['in_min'])
        elif 'at' in op:
            shut(at=op['at'])
        else:
            shut()
        ret['message'] = 'Successfully powered off/rebooted.'
        ret['out'] = True
    except Exception as exception:
        ret['message'] = \
            'Could not poweroff/reboot beacause "{0}"'.format(exception)
        ret['out'] = False
    return ret


def install_config(path=None, **kwargs):
    '''
    Installs the given configuration file into the candidate configuration.
    Commits the changes if the commit checks or throws an error.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.install_config 'salt://production/network/routers/config.set'

        salt 'device_name' junos.install_config 'salt://templates/replace_config.conf' replace=True comment='Committed via SaltStack'

        salt 'device_name' junos.install_config 'salt://my_new_configuration.conf' dev_timeout=300 diffs_file='/salt/confs/old_config.conf' overwrite=True

        salt 'device_name' junos.install_config 'salt://syslog_template.conf' template_vars='{"syslog_host": "10.180.222.7"}'

    Parameters:
      Required
        * path:
          Path where the configuration/template file is present. If the file has a \
          '*.conf' extension,
          the content is treated as text format. If the file has a '*.xml' \
          extension,
          the content is treated as XML format. If the file has a '*.set' \
          extension,
          the content is treated as Junos OS 'set' commands.(default = None)
      Optional
        * kwargs: Keyworded arguments which can be provided like-
            * mode: The mode in which the configuration is locked.
              (Options: private, dynamic, batch, exclusive; default= exclusive)
            * dev_timeout:
              Set NETCONF RPC timeout. Can be used for commands which
              take a while to execute. (default = 30 seconds)
            * overwrite:
              Set to True if you want this file is to completely replace the\
               configuration file. (default = False)
            * replace:
              Specify whether the configuration file uses "replace:" statements.
              Those statements under the 'replace' tag will only be changed.\
               (default = False)
            * format:
              Determines the format of the contents.
            * update:
              Compare a complete loaded configuration against
              the candidate configuration. For each hierarchy level or
              configuration object that is different in the two configurations,
              the version in the loaded configuration replaces the version in the
              candidate configuration. When the configuration is later committed,
              only system processes that are affected by the changed configuration
              elements parse the new configuration. This action is supported from
              PyEZ 2.1 (default = False)
            * comment:
              Provide a comment to the commit. (default = None)
            * confirm:
              Provide time in minutes for commit confirmation.
              If this option is specified, the commit will be rollbacked in \
              the given time unless the commit is confirmed.
            * diffs_file:
              Path to the file where the diff (difference in old configuration
              and the committed configuration) will be stored.(default = None)
              Note that the file will be stored on the proxy minion. To push the
              files to the master use the salt's following execution module: \
              :py:func:`cp.push <salt.modules.cp.push>`
            * template_vars:
              Variables to be passed into the template processing engine in addition
              to those present in __pillar__, __opts__, __grains__, etc.
              You may reference these variables in your template like so:
              {{ template_vars["var_name"] }}

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True

    if path is None:
        ret['message'] = \
            'Please provide the salt path where the configuration is present'
        ret['out'] = False
        return ret

    op = dict()
    if '__pub_arg' in kwargs:
        if kwargs['__pub_arg']:
            if isinstance(kwargs['__pub_arg'][-1], dict):
                op.update(kwargs['__pub_arg'][-1])
    else:
        op.update(kwargs)

    template_vars = dict()
    if "template_vars" in op:
        template_vars = op["template_vars"]

    template_cached_path = salt.utils.files.mkstemp()
    __salt__['cp.get_template'](
        path,
        template_cached_path,
        template_vars=template_vars)

    if not os.path.isfile(template_cached_path):
        ret['message'] = 'Invalid file path.'
        ret['out'] = False
        return ret

    if os.path.getsize(template_cached_path) == 0:
        ret['message'] = 'Template failed to render'
        ret['out'] = False
        return ret

    write_diff = ''
    if 'diffs_file' in op and op['diffs_file'] is not None:
        write_diff = op['diffs_file']
        del op['diffs_file']

    op['path'] = template_cached_path

    if 'format' not in op:
        if path.endswith('set'):
            template_format = 'set'
        elif path.endswith('xml'):
            template_format = 'xml'
        else:
            template_format = 'text'

        op['format'] = template_format

    if 'replace' in op and op['replace']:
        op['merge'] = False
        del op['replace']
    elif 'overwrite' in op and op['overwrite']:
        op['overwrite'] = True
    elif 'overwrite' in op and not op['overwrite']:
        op['merge'] = True
        del op['overwrite']

    db_mode = op.pop('mode', 'exclusive')
    with Config(conn, mode=db_mode) as cu:
        try:
            cu.load(**op)

        except Exception as exception:
            ret['message'] = 'Could not load configuration due to : "{0}"'.format(
                exception)
            ret['format'] = template_format
            ret['out'] = False
            return ret

        finally:
            salt.utils.files.safe_rm(template_cached_path)

        config_diff = cu.diff()
        if config_diff is None:
            ret['message'] = 'Configuration already applied!'
            ret['out'] = True
            return ret

        commit_params = {}
        if 'confirm' in op:
            commit_params['confirm'] = op['confirm']
        if 'comment' in op:
            commit_params['comment'] = op['comment']

        try:
            check = cu.commit_check()
        except Exception as exception:
            ret['message'] = \
                'Commit check threw the following exception: "{0}"'\
                .format(exception)

            ret['out'] = False
            return ret

        if check:
            try:
                cu.commit(**commit_params)
                ret['message'] = 'Successfully loaded and committed!'
            except Exception as exception:
                ret['message'] = \
                    'Commit check successful but commit failed with "{0}"'\
                    .format(exception)
                ret['out'] = False
                return ret
        else:
            ret['message'] = 'Loaded configuration but commit check failed.'
            ret['out'] = False
            cu.rollback()

        try:
            if write_diff and config_diff is not None:
                with salt.utils.files.fopen(write_diff, 'w') as fp:
                    fp.write(salt.utils.stringutils.to_str(config_diff))
        except Exception as exception:
            ret['message'] = 'Could not write into diffs_file due to: "{0}"'.format(
                exception)
            ret['out'] = False

    return ret


def zeroize():
    '''
    Resets the device to default factory settings

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.zeroize

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True
    try:
        conn.cli('request system zeroize')
        ret['message'] = 'Completed zeroize and rebooted'
    except Exception as exception:
        ret['message'] = 'Could not zeroize due to : "{0}"'.format(exception)
        ret['out'] = False

    return ret


def install_os(path=None, **kwargs):
    '''
    Installs the given image on the device. After the installation is complete\
     the device is rebooted,
    if reboot=True is given as a keyworded argument.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.install_os 'salt://images/junos_image.tgz' reboot=True

        salt 'device_name' junos.install_os 'salt://junos_16_1.tgz' dev_timeout=300


    Parameters:
      Required
        * path:
          Path where the image file is present on the proxy minion.
      Optional
        * kwargs: keyworded arguments to be given such as dev_timeout, reboot etc
            * dev_timeout:
              Set NETCONF RPC timeout. Can be used to RPCs which
              take a while to execute. (default = 30 seconds)
            * reboot:
              Whether to reboot after installation (default = False)
            * no_copy:
              When True the software package will not be SCP’d to the device. \
              (default = False)

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True

    if path is None:
        ret['message'] = \
            'Please provide the salt path where the junos image is present.'
        ret['out'] = False
        return ret

    image_cached_path = salt.utils.files.mkstemp()
    __salt__['cp.get_file'](path, image_cached_path)

    if not os.path.isfile(image_cached_path):
        ret['message'] = 'Invalid image path.'
        ret['out'] = False
        return ret

    if os.path.getsize(image_cached_path) == 0:
        ret['message'] = 'Failed to copy image'
        ret['out'] = False
        return ret
    path = image_cached_path

    op = dict()
    if '__pub_arg' in kwargs:
        if kwargs['__pub_arg']:
            if isinstance(kwargs['__pub_arg'][-1], dict):
                op.update(kwargs['__pub_arg'][-1])
    else:
        op.update(kwargs)

    try:
        conn.sw.install(path, progress=True)
        ret['message'] = 'Installed the os.'
    except Exception as exception:
        ret['message'] = 'Installation failed due to: "{0}"'.format(exception)
        ret['out'] = False
        return ret
    finally:
        salt.utils.files.safe_rm(image_cached_path)

    if 'reboot' in op and op['reboot'] is True:
        try:
            conn.sw.reboot()
        except Exception as exception:
            ret['message'] = \
                'Installation successful but reboot failed due to : "{0}"' \
                .format(exception)
            ret['out'] = False
            return ret
        ret['message'] = 'Successfully installed and rebooted!'
    return ret


def file_copy(src=None, dest=None):
    '''
    Copies the file from the local device to the junos device.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.file_copy /home/m2/info.txt info_copy.txt


    Parameters:
      Required
        * src:
          The sorce path where the file is kept.
        * dest:
          The destination path where the file will be copied.

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True

    if src is None:
        ret['message'] = \
            'Please provide the absolute path of the file to be copied.'
        ret['out'] = False
        return ret
    if not os.path.isfile(src):
        ret['message'] = 'Invalid source file path'
        ret['out'] = False
        return ret

    if dest is None:
        ret['message'] = \
            'Please provide the absolute path of the destination where the file is to be copied.'
        ret['out'] = False
        return ret

    try:
        with SCP(conn, progress=True) as scp:
            scp.put(src, dest)
        ret['message'] = 'Successfully copied file from {0} to {1}'.format(
            src, dest)
    except Exception as exception:
        ret['message'] = 'Could not copy file : "{0}"'.format(exception)
        ret['out'] = False
    return ret


def lock():
    """
    Attempts an exclusive lock on the candidate configuration. This
    is a non-blocking call.

    .. note::
        Any user who wishes to use lock, must necessarily unlock the
        configuration too. Ensure :py:func:`unlock <salt.modules.junos.unlock>`
        is called in the same orchestration run in which the lock is called.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.lock

    """
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True
    try:
        conn.cu.lock()
        ret['message'] = "Successfully locked the configuration."
    except jnpr.junos.exception.LockError as exception:
        ret['message'] = 'Could not gain lock due to : "{0}"'.format(exception)
        ret['out'] = False

    return ret


def unlock():
    """
    Unlocks the candidate configuration.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.unlock

    """
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True
    try:
        conn.cu.unlock()
        ret['message'] = "Successfully unlocked the configuration."
    except jnpr.junos.exception.UnlockError as exception:
        ret['message'] = \
            'Could not unlock configuration due to : "{0}"'.format(exception)
        ret['out'] = False

    return ret


def load(path=None, **kwargs):
    """

    Loads the configuration from the file provided onto the device.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.load 'salt://production/network/routers/config.set'

        salt 'device_name' junos.load 'salt://templates/replace_config.conf' replace=True

        salt 'device_name' junos.load 'salt://my_new_configuration.conf' overwrite=True

        salt 'device_name' junos.load 'salt://syslog_template.conf' template_vars='{"syslog_host": "10.180.222.7"}'

    Parameters:
      Required
        * path:
          Path where the configuration/template file is present. If the file has a \
          '*.conf' extension,
          the content is treated as text format. If the file has a '*.xml' \
          extension,
          the content is treated as XML format. If the file has a '*.set' \
          extension,
          the content is treated as Junos OS 'set' commands.(default = None)
      Optional
        * kwargs: Keyworded arguments which can be provided like-
            * overwrite:
              Set to True if you want this file is to completely replace the\
              configuration file. (default = False)
            * replace:
              Specify whether the configuration file uses "replace:" statements.
              Those statements under the 'replace' tag will only be changed.\
               (default = False)
            * format:
              Determines the format of the contents.
            * update:
              Compare a complete loaded configuration against
              the candidate configuration. For each hierarchy level or
              configuration object that is different in the two configurations,
              the version in the loaded configuration replaces the version in the
              candidate configuration. When the configuration is later committed,
              only system processes that are affected by the changed configuration
              elements parse the new configuration. This action is supported from
              PyEZ 2.1 (default = False)
            * template_vars:
              Variables to be passed into the template processing engine in addition
              to those present in __pillar__, __opts__, __grains__, etc.
              You may reference these variables in your template like so:
              {{ template_vars["var_name"] }}


    """
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True

    if path is None:
        ret['message'] = \
            'Please provide the salt path where the configuration is present'
        ret['out'] = False
        return ret

    op = dict()
    if '__pub_arg' in kwargs:
        if kwargs['__pub_arg']:
            if isinstance(kwargs['__pub_arg'][-1], dict):
                op.update(kwargs['__pub_arg'][-1])
    else:
        op.update(kwargs)

    template_vars = dict()
    if "template_vars" in op:
        template_vars = op["template_vars"]

    template_cached_path = salt.utils.files.mkstemp()
    __salt__['cp.get_template'](
        path,
        template_cached_path,
        template_vars=template_vars)

    if not os.path.isfile(template_cached_path):
        ret['message'] = 'Invalid file path.'
        ret['out'] = False
        return ret

    if os.path.getsize(template_cached_path) == 0:
        ret['message'] = 'Template failed to render'
        ret['out'] = False
        return ret

    op['path'] = template_cached_path

    if 'format' not in op:
        if path.endswith('set'):
            template_format = 'set'
        elif path.endswith('xml'):
            template_format = 'xml'
        else:
            template_format = 'text'

        op['format'] = template_format

    if 'replace' in op and op['replace']:
        op['merge'] = False
        del op['replace']
    elif 'overwrite' in op and op['overwrite']:
        op['overwrite'] = True
    elif 'overwrite' in op and not op['overwrite']:
        op['merge'] = True
        del op['overwrite']

    try:
        conn.cu.load(**op)
        ret['message'] = "Successfully loaded the configuration."
    except Exception as exception:
        ret['message'] = 'Could not load configuration due to : "{0}"'.format(
            exception)
        ret['format'] = template_format
        ret['out'] = False
        return ret
    finally:
        salt.utils.files.safe_rm(template_cached_path)

    return ret


def commit_check():
    """

    Perform a commit check on the configuration.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.commit_check

    """
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True
    try:
        conn.cu.commit_check()
        ret['message'] = 'Commit check succeeded.'
    except Exception as exception:
        ret['message'] = 'Commit check failed with {0}'.format(exception)
        ret['out'] = False

    return ret
