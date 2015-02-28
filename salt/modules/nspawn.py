# -*- coding: utf-8 -*-
'''
Manage nspawn containers

.. versionadded:: Beryllium

`systemd-nspawn(1)`__ is a tool used to manage lightweight namespace
containers. This execution module provides several functions to help manage
these containers.

.. __: http://www.freedesktop.org/software/systemd/man/systemd-nspawn.html

Container root directories will live under /var/lib/container.

.. note:

    ``nsenter(1)`` is required to run commands within containers. It should
    already be present on any systemd host, as part of the **util-linux**
    package.
'''
# Import python libs
import logging
import os
import re
import shutil

# Import Salt libs
import salt.defaults.exitcodes
import salt.utils.systemd
from salt.exceptions import CommandExecutionError
from salt.ext.six import string_types

log = logging.getLogger(__name__)

__func_alias__ = {
    'list_': 'list'
}
__virtualname__ = 'nspawn'
WANT = '/etc/systemd/system/multi-user.target.wants/systemd-nspawn@{0}.service'
PATH = 'PATH=/bin:/usr/bin:/sbin:/usr/sbin:/opt/bin:' \
       '/usr/local/bin:/usr/local/sbin'


def __virtual__():
    '''
    Only work on systems that have been booted with systemd
    '''
    if __grains__['kernel'] == 'Linux' and salt.utils.systemd.booted(__context__):
        return __virtualname__
    return False


def _root():
    '''
    Right now this is static, but if machinectl becomes configurable we will
    put additional logic here.
    '''
    return '/var/lib/container'


def _arch_bootstrap(name, **kwargs):
    '''
    Bootstrap an Arch Linux container
    '''
    dst = os.path.join(_root(), name)
    if os.path.exists(dst):
        __context__['retcode'] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        return {'err': 'Container {0} already exists'.format(name)}
    cmd = 'pacstrap -c -d {0} base'.format(dst)
    os.makedirs(dst)
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode'] != 0:
        __context__['retcode'] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        shutil.rmtree(dst)
        return {'err': 'Container {0} failed to build'.format(name)}
    return ret


def _debian_bootstrap(name, **kwargs):
    '''
    Bootstrap a Debian Linux container (only unstable is currently supported)
    '''
    dst = os.path.join(_root(), name)
    if os.path.exists(dst):
        __context__['retcode'] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        return {'err': 'Container {0} already exists'.format(name)}
    cmd = 'debootstrap --arch=amd64 unstable {0}'.format(dst)
    os.makedirs(dst)
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode'] != 0:
        __context__['retcode'] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        shutil.rmtree(dst)
        return {'err': 'Container {0} failed to build'.format(name)}
    return ret


def _fedora_bootstrap(name, **kwargs):
    '''
    Bootstrap a Fedora container
    '''
    dst = os.path.join(_root(), name)
    if not kwargs.get('version', False):
        if __grains__['os'].lower() == 'fedora':
            version = __grains__['osrelease']
        else:
            version = '21'
    else:
        version = '21'
    if os.path.exists(dst):
        __context__['retcode'] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        return {'err': 'Container {0} already exists'.format(name)}
    cmd = 'yum -y --releasever={0} --nogpg --installroot={1} --disablerepo="*" --enablerepo=fedora install systemd passwd yum fedora-release vim-minimal'.format(version, dst)
    os.makedirs(dst)
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode'] != 0:
        __context__['retcode'] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        shutil.rmtree(dst)
        return {'err': 'Container {0} failed to build'.format(name)}
    return ret


def _ensure_exists(name):
    '''
    Raise an exception if the container does not exist
    '''
    if not exists(name):
        raise CommandExecutionError(
            'Container \'{0}\' does not exist'.format(name)
        )


def _machinectl(cmd):
    '''
    Interface to run machinectl with no header/footer and without a pager
    '''
    prefix = 'machinectl --no-legend --no-pager'
    return __salt__['cmd.run_all']('{0} {1}'.format(prefix, cmd))


def _pid(name):
    '''
    Return container pid
    '''
    try:
        return info(name).get('Leader', '').split()[0]
    except IndexError:
        raise CommandExecutionError(
            'Unable to get PID for container \'{0}\''.format(name)
        )


def _nsenter(name):
    '''
    Return the nsenter command to attach to the named container
    '''
    return (
        'nsenter --target {0} --mount --uts --ipc --net --pid'
        .format(_pid(name))
    )


def _run(name,
         cmd,
         output=None,
         no_start=False,
         stdin=None,
         python_shell=True,
         preserve_state=False,
         output_loglevel='debug',
         ignore_retcode=False,
         use_vt=False,
         keep_env=None):
    '''
    Common logic for nspawn.run functions
    '''
    # No need to call _ensure_exists(), it will be called via _nsenter()
    full_cmd = _nsenter(name)
    if keep_env is not True:
        full_cmd += ' env -i'
    if keep_env is None:
        full_cmd += ' {0}'.format(PATH)
    elif isinstance(keep_env, string_types):
        for var in keep_env.split(','):
            if var in os.environ:
                full_cmd += ' {0}="{1}"'.format(var, os.environ[var])
    full_cmd += ' {0}'.format(cmd)

    orig_state = state(name)
    exc = None
    try:
        ret = __salt__['container_resource.run'](
            name,
            full_cmd,
            output=output,
            no_start=no_start,
            stdin=stdin,
            python_shell=python_shell,
            output_loglevel=output_loglevel,
            ignore_retcode=ignore_retcode,
            use_vt=use_vt)
    except Exception as exc:
        raise
    finally:
        # Make sure we stop the container if necessary, even if an exception
        # was raised.
        if preserve_state \
                and orig_state == 'stopped' \
                and state(name) != 'stopped':
            stop(name)

    if output in (None, 'all'):
        return ret
    else:
        return ret[output]


def run(name,
        cmd,
        no_start=False,
        preserve_state=True,
        stdin=None,
        python_shell=True,
        output_loglevel='debug',
        use_vt=False,
        ignore_retcode=False,
        keep_env=None):
    '''
    Run :mod:`cmd.run <salt.modules.cmdmod.run>` within a container

    name
        Name of the container in which to run the command

    cmd
        Command to run

    no_start : False
        If the container is not running, don't start it

    preserve_state : True
        After running the command, return the container to its previous state

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console. Assumes
        ``output=all``.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.


    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.run mycontainer 'ifconfig -a'
    '''
    return _run(name,
                cmd,
                output=None,
                no_start=no_start,
                preserve_state=preserve_state,
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def run_stdout(name,
               cmd,
               no_start=False,
               preserve_state=True,
               stdin=None,
               python_shell=True,
               output_loglevel='debug',
               use_vt=False,
               ignore_retcode=False,
               keep_env=None):
    '''
    Run :mod:`cmd.run_stdout <salt.modules.cmdmod.run_stdout>` within a container

    name
        Name of the container in which to run the command

    cmd
        Command to run

    no_start : False
        If the container is not running, don't start it

    preserve_state : True
        After running the command, return the container to its previous state

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console. Assumes
        ``output=all``.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.


    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.run_stdout mycontainer 'ifconfig -a'
    '''
    return _run(name,
                cmd,
                output='stdout',
                no_start=no_start,
                preserve_state=preserve_state,
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def run_stderr(name,
               cmd,
               no_start=False,
               preserve_state=True,
               stdin=None,
               python_shell=True,
               output_loglevel='debug',
               use_vt=False,
               ignore_retcode=False,
               keep_env=None):
    '''
    Run :mod:`cmd.run_stderr <salt.modules.cmdmod.run_stderr>` within a container

    name
        Name of the container in which to run the command

    cmd
        Command to run

    no_start : False
        If the container is not running, don't start it

    preserve_state : True
        After running the command, return the container to its previous state

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console. Assumes
        ``output=all``.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.


    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.run_stderr mycontainer 'ip addr show'
    '''
    return _run(name,
                cmd,
                output='stderr',
                no_start=no_start,
                preserve_state=preserve_state,
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def retcode(name,
            cmd,
            no_start=False,
            preserve_state=True,
            stdin=None,
            python_shell=True,
            output_loglevel='debug',
            use_vt=False,
            ignore_retcode=False,
            keep_env=None):
    '''
    Run :mod:`cmd.retcode <salt.modules.cmdmod.retcode>` within a container

    name
        Name of the container in which to run the command

    cmd
        Command to run

    no_start : False
        If the container is not running, don't start it

    preserve_state : True
        After running the command, return the container to its previous state

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console. Assumes
        ``output=all``.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.


    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.retcode mycontainer 'ip addr show'
    '''
    return _run(name,
                cmd,
                output='retcode',
                no_start=no_start,
                preserve_state=preserve_state,
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def run_all(name,
            cmd,
            no_start=False,
            preserve_state=True,
            stdin=None,
            python_shell=True,
            output_loglevel='debug',
            use_vt=False,
            ignore_retcode=False,
            keep_env=None):
    '''
    Run :mod:`cmd.run_all <salt.modules.cmdmod.run_all>` within a container

    name
        Name of the container in which to run the command

    cmd
        Command to run

    no_start : False
        If the container is not running, don't start it

    preserve_state : True
        After running the command, return the container to its previous state

    stdin : None
        Standard input to be used for the command

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

    use_vt : False
        Use SaltStack's utils.vt to stream output to console. Assumes
        ``output=all``.

    keep_env : None
        If not passed, only a sane default PATH environment variable will be
        set. If ``True``, all environment variables from the container's host
        will be kept. Otherwise, a comma-separated list (or Python list) of
        environment variable names can be passed, and those environment
        variables will be kept.


    CLI Example:

    .. code-block:: bash

        salt myminion nspawn.run_all mycontainer 'ip addr show'
    '''
    return _run(name,
                cmd,
                output='all',
                no_start=no_start,
                preserve_state=preserve_state,
                stdin=stdin,
                python_shell=python_shell,
                output_loglevel=output_loglevel,
                use_vt=use_vt,
                ignore_retcode=ignore_retcode,
                keep_env=keep_env)


def bootstrap_container(name, dist=None, version=None):
    '''
    Bootstrap a container from package servers, if dist is None the os the
    minion is running as will be created, otherwise the needed bootstrapping
    tools will need to be available on the host.

    CLI Example::

        salt '*' nspawn.bootstrap_container <name>
    '''
    if not dist:
        dist = __grains__['os'].lower()
        log.debug(
            'nspawn.bootstrap: no dist provided, defaulting to \'{0}\''
            .format(dist)
        )
    return globals()['_{0}_bootstrap'.format(dist)](name, version=version)


def list_all():
    '''
    Lists all nspawn containers

    CLI Example:

    .. code-block:: bash

        salt '*' nspawn.list_all
    '''
    rootdir = _root()
    return sorted(
        [x for x in os.listdir(rootdir)
         if os.path.isdir(os.path.join(rootdir, x))]
    )


def list_running():
    '''
    Lists running nspawn containers

    .. note::

        ``nspawn.list`` also works to list running containers

    CLI Example:

    .. code-block:: bash

        salt '*' nspawn.list_running
        salt '*' nspawn.list
    '''
    ret = []
    for line in _machinectl('list')['stdout'].splitlines():
        try:
            ret.append(line.split()[0])
        except IndexError:
            pass
    return sorted(ret)

# 'machinectl list' shows only running containers, so allow this to work as an
# alias to nspawn.list_running
list_ = list_running


def list_stopped():
    '''
    Lists stopped nspawn containers

    CLI Example:

    .. code-block:: bash

        salt '*' nspawn.list_stopped
    '''
    return sorted(set(list_all()) - set(list_running()))


def exists(name):
    '''
    Returns true if the named container exists
    '''
    return name in list_all()


def state(name):
    '''
    Return state of container
    '''
    _ensure_exists(name)
    try:
        cmd = 'show {0} --property=State'.format(name)
        return _machinectl(cmd)['stdout'].split('=')[1]
    except IndexError:
        return 'stopped'


def info(name, force_start=True):
    '''
    Return info about a container

    .. note::

        The container must be running for ``machinectl`` to gather information
        about it. If the container is stopped, then this function will start
        it.

    force_start : True

        If ``False``, then this function will result in an error if the
        container is not already running.

    CLI Example:

    .. code-block:: bash

        salt '*' nspawn.info arch1
        salt '*' nspawn.info arch1 force_start=False
    '''
    _ensure_exists(name)
    running_containers = list_running()
    needs_stop = False
    if name not in running_containers:
        if start:
            start(name)
            needs_stop = True
        else:
            raise CommandExecutionError(
                'Container \'{0}\' is not running'.format(name)
            )
    # Have to parse 'machinectl status' here since 'machinectl show' doesn't
    # contain IP address info. *shakes fist angrily*
    c_info = _machinectl('status {0}'.format(name))
    if c_info['retcode'] != 0:
        raise CommandExecutionError(
            'Unable to get info for container \'{0}\''.format(name)
        )
    ret = {}
    kv_pair = re.compile(r'^\s+([A-Za-z]+): (.+)$')
    tree = re.compile(r'[|`]')
    lines = c_info['stdout'].splitlines()
    multiline = False
    cur_key = None
    for idx in range(len(lines)):
        match = kv_pair.match(lines[idx])
        if match:
            key, val = match.groups()
            cur_key = key
            if multiline:
                multiline = False
            ret[key] = val
        else:
            if cur_key is None:
                continue
            if tree.search(lines[idx]):
                # We've reached the process tree, bail out
                break
            if multiline:
                ret[cur_key].append(lines[idx].strip())
            else:
                ret[cur_key] = [ret[key], lines[idx].strip()]
                multiline = True
    return ret


def enable(name):
    '''
    Set the named container to be launched at boot

    CLI Example:

    .. code-block:: bash

        salt '*' nspawn.enable <name>
    '''
    _ensure_exists(name)
    cmd = 'systemctl enable systemd-nspawn@{0}'.format(name)
    if __salt__['cmd.retcode'](cmd, python_shell=False) != 0:
        __context__['retcode'] = salt.defaults.exitcodes.EX_UNAVAILABLE
        return False
    return True


def disable(name):
    '''
    Set the named container to *not* be launched at boot

    CLI Example:

    .. code-block:: bash

        salt '*' nspawn.enable <name>
    '''
    _ensure_exists(name)
    cmd = 'systemctl disable systemd-nspawn@{0}'.format(name)
    if __salt__['cmd.retcode'](cmd, python_shell=False) != 0:
        __context__['retcode'] = salt.defaults.exitcodes.EX_UNAVAILABLE
        return False
    return True


def start(name):
    '''
    Start the named container

    CLI Example::

        salt '*' nspawn.start <name>
    '''
    _ensure_exists(name)
    cmd = 'systemctl start systemd-nspawn@{0}'.format(name)
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode'] != 0:
        __context__['retcode'] = salt.defaults.exitcodes.EX_UNAVAILABLE
        return False
    return True


def stop(name):
    '''
    Start the named container

    CLI Example::

        salt '*' nspawn.stop <name>
    '''
    _ensure_exists(name)
    cmd = 'systemctl stop systemd-nspawn@{0}'.format(name)
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode'] != 0:
        __context__['retcode'] = salt.defaults.exitcodes.EX_UNAVAILABLE
        return False
    return True
