# -*- coding: utf-8 -*-
'''
Module for interfacing to Junos devices.
'''
from __future__ import absolute_import

# Import python libraries
import logging
import json
from lxml import etree
# Juniper interface libraries
# https://github.com/Juniper/py-junos-eznc


try:
    # pylint: disable=W0611
    from jnpr.junos import Device
    from jnpr.junos.utils.sw import SW
    from jnpr.junos.utils.scp import SCP
    import jnpr.junos.utils
    import jnpr.junos.cfg
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
                loaded: junos-eznc or proxy could not be loaded.')


def facts_refresh():
    '''
    Reload the facts dictionary from the device.  Usually only needed
    if the device configuration is changed by some other actor.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.facts_refresh

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True
    try:
        ret['message'] = conn.facts_refresh()

    except Exception as exception:
        ret['message'] = 'Execution failed due to "{0}"'.format(exception)
        ret['out'] = False

    return ret


def facts():
    '''
    Displays the facts gathered during the connection.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.facts

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['message'] = json.dumps(conn.facts)
    ret['out'] = True
    return ret


def call_rpc(cmd=None, *args, **kwargs):
    '''
    This function executes the rpc provided as arguments on the junos device.
    The returned data can be stored in a file whose destination can be
    specified with 'dest' keyword in the arguments.

    Usage:

    .. code-block:: bash

        salt 'device' junos.call_rpc 'get_config' '<configuration><system/></configuration>' terse=True

        salt 'device' junos.call_rpc 'get-chassis-inventory' dest=/home/user/rpc_information.txt


    Options:
      * cmd: the rpc to be executed
      * args: other arguments as taken by rpc call of PyEZ
      * kwargs: keyworded arguments taken by rpc call of PyEZ
    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True

    op = dict()
    if '__pub_arg' in kwargs and isinstance(kwargs['__pub_arg'][-1], dict):
        op.update(kwargs['__pub_arg'][-1])
    else:
        op.update(kwargs)

    for k, v in op.iteritems():
        op[k] = str(v)
    op['format'] = 'json'

    try:
        if cmd in ['get-config', 'get_config']:
            filter_reply = None
            if len(args) > 0:
                filter_reply = etree.XML(args[0])
            ret['message'] = getattr(conn.rpc, cmd.replace('-', '_'))(filter_reply, options=op)
        else:
            ret['message'] = getattr(conn.rpc, cmd.replace('-', '_'))(op)

    except Exception as exception:

        ret['message'] = 'Execution failed due to "{0}"'.format(exception)
        ret['out'] = False

    if 'dest' in op:
        f = open(op['dest'], 'w')
        f.write(ret['message'])
        f.close()

    return ret


def set_hostname(hostname=None, commit_change=True):
    '''
    To set the name of the device.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.set_hostname hostname=salt-device


    Options:
      * hostname: The name to be set.
      * commit_change: Whether to commit the changes.(default=True)
    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    if hostname is None:
        ret['out'] = False
        return ret

    # Added to recent versions of JunOs
    # Use text format instead
    set_string = 'set system host-name {0}'.format(hostname)
    conn.cu.load(set_string, format='set')
    if commit_change:
        return commit()
    else:
        ret['out'] = True
        ret['msg'] = 'set system host-name {0} is queued'.format(hostname)

    return ret


def commit():
    '''
    To commit the changes loaded in the candidate configuration.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.commit

    '''

    conn = __proxy__['junos.conn']()
    ret = {}
    commit_ok = conn.cu.commit_check()
    if commit_ok:
        try:
            conn.cu.commit(confirm=True)
            ret['out'] = True
            ret['message'] = 'Commit Successful.'
        except Exception as exception:
            ret['out'] = False
            ret['message'] = 'Pre-commit check succeeded but actual commit failed with "{0}"'.format(
                exception)
    else:
        ret['out'] = False
        ret['message'] = 'Pre-commit check failed.'

    return ret


def rollback():
    '''
    To rollback the last committed configuration changes

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.rollback

    '''
    ret = dict()
    conn = __proxy__['junos.conn']()

    ret['out'] = conn.cu.rollback(0)

    if ret['out']:
        ret['message'] = 'Rollback successful'
    else:
        ret['message'] = 'Rollback failed'

    return ret


def diff():
    '''
    Gives the difference between the candidate and the current configuration.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.diff

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True
    ret['message'] = conn.cu.diff()

    return ret


def ping():
    '''
    To check the connection with the device

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.ping

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['message'] = conn.probe()
    if ret['message']:
        ret['out'] = True
    else:
        ret['out'] = False
    return ret


def cli(command=None):
    '''
    Executes the CLI commands and reuturns the text output.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.cli 'show version'


    Options:
      * command: The command that need to be executed on Junos CLI.
    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['message'] = conn.cli(command)
    ret['out'] = True
    return ret


def shutdown(time=0):
    '''
    Shuts down the device after the given time.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.shutdown 10


    Options:
      * time: Time in seconds after which the device should shutdown (default=0)
    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    sw = SW(conn)
    try:
        shut = sw.poweroff()
        shut(time)
        ret['message'] = 'Successfully powered off.'
        ret['out'] = False
    except Exception as exception:
        ret['message'] = 'Could not poweroff'
        ret['out'] = False

    return ret


def install_config(path=None, **kwargs):
    '''
    Installs the given configuration file into the candidate configuration.
    Commits the changes if the commit checks or throws an error.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.install_config '/home/user/config.set' timeout=300


    Options:
      * path: Path where the configuration file is present.
      * kwargs: keyworded arguments taken by load fucntion of PyEZ
    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True

    if 'timeout' in kwargs:
        conn.timeout = kwargs['timeout']

    options = {'path': path}

    try:
        conn.cu.load(**options)
        conn.cu.pdiff()

    except Exception as exception:
        ret['message'] = 'Could not load configuration due to : "{0}"'.format(
            exception)
        ret['out'] = False

    if conn.cu.commit_check():
        ret['message'] = 'Successfully loaded and committed!'
        conn.cu.commit()
    else:
        ret['message'] = 'Commit check failed.'
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
    Installs the given image on the device. After the installation is complete the device is rebooted,
    if reboot=True is given as a keyworded argument.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.install_os '/home/user/junos_image.tgz' reboot=True


    Options
      * path: Path where the image file is present.
      * kwargs: keyworded arguments to be given such as timeout, reboot etc

    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True

    if 'timeout' in kwargs:
        conn.timeout = kwargs['timeout']

    try:
        install = conn.sw.install(path, progress=True)
        ret['message'] = 'Installed the os.'
    except Exception as exception:
        ret['message'] = 'Installation failed due to : "{0}"'.format(exception)
        ret['out'] = False

    if 'reboot' in kwargs and kwargs['reboot'] is True:
        rbt = conn.sw.reboot()
        ret['message'] = 'Successfully installed and rebooted!'

    return ret


def file_copy(src=None, dest=None):
    '''
    Copies the file from the local device to the junos device.

    Usage:

    .. code-block:: bash

        salt 'device_name' junos.file_copy /home/m2/info.txt info_copy.txt


    Options
      * src: The sorce path where the file is kept.
      * dest: The destination path where the file will be copied.
    '''
    conn = __proxy__['junos.conn']()
    ret = dict()
    ret['out'] = True
    try:
        with SCP(conn, progress=True) as scp:
            scp.put(src, dest)
        ret['message'] = 'Successfully copied file from {0} to {1}'.format(
            src, dest)

    except Exception as exception:
        ret['message'] = 'Could not copy file : "{0}"'.format(exception)
        ret['out'] = False

    return ret
