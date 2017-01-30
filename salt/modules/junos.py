# -*- coding: utf-8 -*-
'''
Module to interact with Junos devices.
'''

# Import python libraries
from __future__ import absolute_import
from __future__ import print_function
import logging
import json
import os
import yaml

# Import salt libraries
from salt.utils import fopen

try:
    from lxml import etree
except ImportError:
    from salt._compat import ElementTree as etree

# Juniper interface libraries
# https://github.com/Juniper/py-junos-eznc
try:
    # pylint: disable=W0611
    from jnpr.junos import Device
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
        return (False, 'The junos module could not be \
                loaded: junos-eznc or jxmlease or proxy could not be loaded.')


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
        __salt__['saltutil.sync_grains']()
    except Exception as exception:
        log.error('Grains could not be updated due to "{0}"'.format(exception))
    try:
        ret['message'] = conn.facts_refresh()
    except Exception as exception:
        ret['message'] = 'Execution failed due to "{0}"'.format(exception)
        ret['out'] = False

    return ret


def facts():
    '''
    Displays the facts gathered during the connection.
    These facts are also stored in Salt grains.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.facts

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    try:
        facts = conn.facts
        ret['message'] = json.dumps(facts)
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

        salt 'device' junos.rpc 'get_config' dest='/var/log/config.txt' format='text' filter='<configuration><system/></configuration>'

        salt 'device' junos.rpc 'get-interface-information' dest='/home/user/interface.xml' interface_name='lo0' terse=True

        salt 'device' junos.rpc 'get-chassis-inventory'

    Parameters:
      Required
        * cmd:
          The rpc to be executed. (default = None)
      Optional
        * dest:
          Destination file where the rpc ouput is stored. (default = None)
        * format:
          The format in which the rpc reply must be stored in file specified in the dest
          (used only when dest is specified) (default = xml)
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
    else:
        op.update(kwargs)

    if dest is None and format != 'xml':
        log.warning(
            'Format ignored as it is only used for \
            output which is dumped in the file.')

    write_response = ''
    try:
        if cmd in ['get-config', 'get_config']:
            filter_reply = None
            if 'filter' in op:
                filter_reply = etree.XML(op['filter'])
                del op['filter']
            xml_reply = getattr(
                conn.rpc,
                cmd.replace('-',
                            '_'))(filter_reply,
                                  options=op)
            ret['message'] = jxmlease.parse(etree.tostring(xml_reply))
            write_response = etree.tostring(xml_reply)

            if dest is not None and format != 'xml':
                op.update({'format': format})
                rpc_reply = getattr(
                    conn.rpc,
                    cmd.replace('-',
                                '_'))(filter_reply,
                                      options=op)
                if format == 'json':
                    write_response = json.dumps(rpc_reply, indent=1)
                else:
                    write_response = rpc_reply.text
        else:
            if 'filter' in op:
                log.warning(
                    'Filter ignored as it is only used with "get-config" rpc')
            xml_reply = getattr(conn.rpc, cmd.replace('-', '_'))(**op)
            ret['message'] = jxmlease.parse(etree.tostring(xml_reply))
            write_response = etree.tostring(xml_reply)

            if dest is not None and format != 'xml':
                rpc_reply = getattr(
                    conn.rpc,
                    cmd.replace('-',
                                '_'))({'format': format},
                                      **op)
                if format == 'json':
                    write_response = json.dumps(rpc_reply, indent=1)
                else:
                    write_response = rpc_reply.text

    except Exception as exception:
        ret['message'] = 'Execution failed due to "{0}"'.format(exception)
        ret['out'] = False
        return ret

    if dest is not None:
        with fopen(dest, 'w') as fp:
            fp.write(write_response)

    return ret


def set_hostname(hostname=None, **kwargs):
    '''
    To set the name of the device.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.set_hostname hostname=salt-device

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

    detail = False
    if 'detail' in op and op['detail']:
        detail = True

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
                if detail:
                    ret['message'] = jxmlease.parse(etree.tostring(commit))
                else:
                    ret['message'] = 'Commit Successful.'
            else:
                ret['message'] = 'Commit failed.'
                ret['out'] = False
        except Exception as exception:
            ret['out'] = False
            ret['message'] = 'Pre-commit check succeeded but \
            actual commit failed with "{0}"'.format(
                exception)
    else:
        ret['out'] = False
        ret['message'] = 'Pre-commit check failed.'
        conn.cu.rollback()

    return ret


def rollback(id=0, **kwargs):
    '''
    To rollback the last committed configuration changes

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.rollback id=10

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

    if 'diffs_file' in op and op['diffs_file'] is not None:
        diff = conn.cu.diff()
        if diff is not None:
            with fopen(op['diffs_file'], 'w') as fp:
                fp.write(diff)
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
            ret['message'] = 'Rollback successful but commit failed with error "{0}"'.format(
                exception)
            return ret
    else:
        ret['out'] = False
        ret['message'] = 'Rollback succesfull but pre-commit check failed.'

    return ret


def diff(id=0):
    '''
    Gives the difference between the candidate and the current configuration.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.diff id=3


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
        ret['out'] = False
        ret['message'] = 'Could not get diff with error "{0}"'.format(
            exception)

    return ret


def ping(dest_ip=None, **kwargs):
    '''
    To send ping RPC to a device.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.ping dest_ip='8.8.8.8' count=5

        salt 'device_name' junos.ping dest_ip='8.8.8.8' ttl=1 rapid=True


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

    if 'count' in op:
        op['count'] = str(op['count'])
    else:
        op['count'] = '5'
    if 'ttl' in op:
        op['ttl'] = str(op['ttl'])

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

        salt 'device_name' junos.cli command='show system commit'

        salt 'device_name' junos.cli command='show version' dev_timeout=40

        salt 'device_name' junos.cli command='show system alarms' format='xml' dest=/home/user/cli_output.txt


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
        result = conn.cli(command, format)
    except Exception as exception:
        ret['message'] = 'Execution failed due to "{0}"'.format(exception)
        ret['out'] = False
        return ret

    if format == 'xml':
        ret['message'] = jxmlease.parse(etree.tostring(result))
    else:
        ret['message'] = result

    if 'dest' in op and op['dest'] is not None:
        if format == 'text':
            write_response = result
        else:
            write_response = etree.tostring(result)
        with fopen(op['dest'], 'w') as fp:
            fp.write(write_response)

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

        salt 'device_name' junos.shutdown in_min=10

        salt 'device_name' junos.shutdown


    Parameters:
      Optional
        * kwargs:
            * reboot:
              Whether to reboot instead of shutdown. (default=False)
            * at:
              Specify time for reboot. (To be used only if reboot=yes)
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

    try:
        if 'reboot' in op and op['reboot']:
            shut = sw.reboot
        else:
            shut = sw.poweroff

        if 'in_min' in op:
            shut(in_min=op['in_min'])
        elif 'at' in op:
            shut(at=op['at'])
        else:
            shut()
        ret['message'] = 'Successfully powered off/rebooted.'
        ret['out'] = True
    except Exception as exception:
        ret['message'] = 'Could not poweroff/reboot.'
        ret['out'] = False

    return ret


def install_config(path=None, **kwargs):
    '''
    Installs the given configuration file into the candidate configuration.
    Commits the changes if the commit checks or throws an error.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.install_config path='/home/user/config.set'

        salt 'device_name' junos.install_config path='/home/user/replace_config.conf' replace=True comment='Committed via SaltStack'

        salt 'device_name' junos.install_config path='/home/user/my_new_configuration.conf' dev_timeout=300 diffs_file='/salt/confs/old_config.conf' overwrite=True


    Parameters:
      Required
        * path:
          Path where the configuration file is present. If the file has a \
          '*.conf' extension,
          the content is treated as text format. If the file has a '*.xml' \
          extension,
          the content is treated as XML format. If the file has a '*.set' \
          extension,
          the content is treated as Junos OS 'set' commands.(default = None)
      Optional
        * kwargs: Keyworded arguments which can be provided like-
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
            * comment:
              Provide a comment to the commit. (default = None)
            * confirm:
              Provide time in minutes for commit confirmation.
              If this option is specified, the commit will be rollbacked in \
              the given time unless the commit is confirmed.
            * diffs_file:
              Path to the file where the diff (difference in old configuration
              and the newly commited configuration) will be stored.\
               (default = None)

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True

    if path is None:
        ret[
            'message'] = 'Please provide the absolute path where the \
            configuration is present'
        ret['out'] = False
        return ret

    if not os.path.isfile(path):
        ret['message'] = 'Invalid file path.'
        ret['out'] = False
        return ret

    op = dict()
    if '__pub_arg' in kwargs:
        if kwargs['__pub_arg']:
            if isinstance(kwargs['__pub_arg'][-1], dict):
                op.update(kwargs['__pub_arg'][-1])
    else:
        op.update(kwargs)

    write_diff = ''
    if 'diffs_file' in op and op['diffs_file'] is not None:
        write_diff = op['diffs_file']
        del op['diffs_file']

    if 'template_path' in op:
        if not os.path.isfile(op['template_path']):
            ret['message'] = 'Invlaid template path.'
            ret['out'] = False
            return ret
        if 'template_vars' not in op:
            ret[
                'message'] = 'Please provide jinja variable along with the \
                jina template.'
            ret['out'] = False
            return ret
        if not os.path.isfile(op['template_vars']):
            ret['message'] = 'Invlaid template_vars path.'
            ret['out'] = False
            return ret
        data = yaml.load(open(op['template_vars']))
        op['template_vars'] = data
    else:
        op = {'path': path}

    if 'replace' in op and op['replace']:
        op['merge'] = False
        del op['replace']
    elif 'overwrite' in op and op['overwrite']:
        load_params['overwrite'] = True
    elif 'overwrite' in op and not op['overwrite']:
        load_params['merge'] = True
        del op['overwrite']

    try:
        conn.cu.load(**op)

    except Exception as exception:
        ret['message'] = 'Could not load configuration due to : "{0}"'.format(
            exception)
        ret['out'] = False
        return ret

    try:
        if write_diff:
            diff = conn.cu.diff()
            if diff is not None:
                with fopen(write_diff, 'w') as fp:
                    fp.write(diff)
    except Exception as exception:
        ret['message'] = 'Could not write into diffs_file due to: "{0}"'.format(
            exception)
        ret['out'] = False
        return ret

    commit_params = {}
    if 'confirm' in op:
        commit_params['confirm'] = op['confirm']
    if 'comment' in op:
        commit_params['comment'] = op['comment']

    try:
        check = conn.cu.commit_check()
    except Exception as exception:
        ret['message'] = 'Commit check failed with "{0}"'.format(exception)
        ret['out'] = False
        return ret

    if check:
        try:
            conn.cu.commit(**commit_params)
            ret['message'] = 'Successfully loaded and committed!'
        except Exception as exception:
            ret['message'] = 'Commit check successful but commit failed with "{0}"'.format(
                exception)
            ret['out'] = False
            return ret
    else:
        ret['message'] = 'Loaded configuration but commit check failed.'
        ret['out'] = False
        conn.cu.rollback()

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

        salt 'device_name' junos.install_os path='/home/user/junos_image.tgz' reboot=True

        salt 'device_name' junos.install_os path='/home/user/junos_16_1.tgz' dev_timeout=300


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
        ret[
            'message'] = 'Please provide the absolute path \
            where the junos image is present.'
        ret['out'] = False
        return ret
    if not os.path.isfile(path):
        ret['message'] = 'Invalid file path'
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
        install = conn.sw.install(path, progress=True)
        ret['message'] = 'Installed the os.'
    except Exception as exception:
        ret['message'] = 'Installation failed due to : "{0}"'.format(exception)
        ret['out'] = False
        return ret

    if 'reboot' in op and op['reboot'] is True:
        try:
            rbt = conn.sw.reboot()
        except Exception as exception:
            ret['message'] = 'Installation successful but \
            reboot failed due to : "{0}"'.format(
                exception)
            ret['out'] = False
            return ret
        ret['message'] = 'Successfully installed and rebooted!'

    return ret


def file_copy(src=None, dest=None, **kwargs):
    '''
    Copies the file from the local device to the junos device.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.file_copy src=/home/m2/info.txt dest=info_copy.txt


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
        ret[
            'message'] = 'Please provide the absolute path \
            of the file to be copied.'
        ret['out'] = False
        return ret
    if not os.path.isfile(src):
        ret['message'] = 'Invalid source file path'
        ret['out'] = False
        return ret

    if dest is None:
        ret[
            'message'] = 'Please provide the absolute path of\
             the destination where the file is to be copied.'
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
        with SCP(conn, progress=True) as scp:
            scp.put(src, dest)
        ret['message'] = 'Successfully copied file from {0} to {1}'.format(
            src, dest)

    except Exception as exception:
        ret['message'] = 'Could not copy file : "{0}"'.format(exception)
        ret['out'] = False

    return ret