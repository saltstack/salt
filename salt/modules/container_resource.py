# -*- coding: utf-8 -*-
'''
Common resources for LXC and systemd-nspawn containers

.. versionadded:: 2015.8.0

These functions are not designed to be called directly, but instead from the
:mod:`lxc <salt.modules.lxc>`, :mod:`nspawn <salt.modules.nspawn>`, and
:mod:`dockerng <salt.modules.dockerng>` execution modules. They provide for
common logic to be re-used for common actions.
'''

# Import python libs
from __future__ import absolute_import
import functools
import copy
import logging
import os
import pipes
import time
import traceback

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils import vt

log = logging.getLogger(__name__)

PATH = 'PATH=/bin:/usr/bin:/sbin:/usr/sbin:/opt/bin:' \
       '/usr/local/bin:/usr/local/sbin'


def _validate(wrapped):
    '''
    Decorator for common function argument validation
    '''
    @functools.wraps(wrapped)
    def wrapper(*args, **kwargs):
        container_type = kwargs.get('container_type')
        exec_driver = kwargs.get('exec_driver')
        valid_driver = {
            'dockerng': ('lxc-attach', 'nsenter', 'docker-exec'),
            'lxc': ('lxc-attach',),
            'nspawn': ('nsenter',),
        }
        if container_type not in valid_driver:
            raise SaltInvocationError(
                'Invalid container type \'{0}\'. Valid types are: {1}'
                .format(container_type, ', '.join(sorted(valid_driver)))
            )
        if exec_driver not in valid_driver[container_type]:
            raise SaltInvocationError(
                'Invalid command execution driver. Valid drivers are: {0}'
                .format(', '.join(valid_driver[container_type]))
            )
        if exec_driver == 'lxc-attach' and not salt.utils.which('lxc-attach'):
            raise SaltInvocationError(
                'The \'lxc-attach\' execution driver has been chosen, but '
                'lxc-attach is not available. LXC may not be installed.'
            )
        return wrapped(*args, **salt.utils.clean_kwargs(**kwargs))
    return wrapper


def _nsenter(pid):
    '''
    Return the nsenter command to attach to the named container
    '''
    return (
        'nsenter --target {0} --mount --uts --ipc --net --pid'
        .format(pid)
    )


def _get_md5(name, path, run_func):
    '''
    Get the MD5 checksum of a file from a container
    '''
    output = run_func(name,
                      'md5sum {0}'.format(pipes.quote(path)),
                      ignore_retcode=True)['stdout']
    try:
        return output.split()[0]
    except IndexError:
        # Destination file does not exist or could not be accessed
        return None


def cache_file(source):
    '''
    Wrapper for cp.cache_file which raises an error if the file was unable to
    be cached.

    CLI Example:

    .. code-block:: bash

        salt myminion container_resource.cache_file salt://foo/bar/baz.txt
    '''
    try:
        # Don't just use cp.cache_file for this. Docker has its own code to
        # pull down images from the web.
        if source.startswith('salt://'):
            cached_source = __salt__['cp.cache_file'](source)
            if not cached_source:
                raise CommandExecutionError(
                    'Unable to cache {0}'.format(source)
                )
            return cached_source
    except AttributeError:
        raise SaltInvocationError('Invalid source file {0}'.format(source))
    return source


@_validate
def run(name,
        cmd,
        container_type=None,
        exec_driver=None,
        output=None,
        no_start=False,
        stdin=None,
        python_shell=True,
        output_loglevel='debug',
        ignore_retcode=False,
        path=None,
        use_vt=False,
        keep_env=None):
    '''
    Common logic for running shell commands in containers

    path
        path to the container parent (for LXC only)
        default: /var/lib/lxc (system default)

    CLI Example:

    .. code-block:: bash

        salt myminion container_resource.run mycontainer 'ps aux' container_type=docker exec_driver=nsenter output=stdout
    '''
    valid_output = ('stdout', 'stderr', 'retcode', 'all')
    if output is None:
        cmd_func = 'cmd.run'
    elif output not in valid_output:
        raise SaltInvocationError(
            '\'output\' param must be one of the following: {0}'
            .format(', '.join(valid_output))
        )
    else:
        cmd_func = 'cmd.run_all'

    if keep_env is None or isinstance(keep_env, bool):
        to_keep = []
    elif not isinstance(keep_env, (list, tuple)):
        try:
            to_keep = keep_env.split(',')
        except AttributeError:
            log.warning('Invalid keep_env value, ignoring')
            to_keep = []
    else:
        to_keep = keep_env

    if exec_driver == 'lxc-attach':
        full_cmd = 'lxc-attach '
        if path:
            full_cmd += '-P {0} '.format(pipes.quote(path))
        if keep_env is not True:
            full_cmd += '--clear-env '
            if 'PATH' not in to_keep:
                full_cmd += '--set-var {0} '.format(PATH)
                # --clear-env results in a very restrictive PATH
                # (/bin:/usr/bin), use a good fallback.
        full_cmd += ' '.join(
            ['--set-var {0}={1}'.format(x, pipes.quote(os.environ[x]))
                for x in to_keep
                if x in os.environ]
        )
        full_cmd += ' -n {0} -- {1}'.format(pipes.quote(name), cmd)
    elif exec_driver == 'nsenter':
        pid = __salt__['{0}.pid'.format(container_type)](name)
        full_cmd = (
            'nsenter --target {0} --mount --uts --ipc --net --pid -- '
            .format(pid)
        )
        if keep_env is not True:
            full_cmd += 'env -i '
            if 'PATH' not in to_keep:
                full_cmd += '{0} '.format(PATH)
        full_cmd += ' '.join(
            ['{0}={1}'.format(x, pipes.quote(os.environ[x]))
                for x in to_keep
                if x in os.environ]
        )
        full_cmd += ' {0}'.format(cmd)
    elif exec_driver == 'docker-exec':
        # We're using docker exec on the CLI as opposed to via docker-py, since
        # the Docker API doesn't return stdout and stderr separately.
        full_cmd = 'docker exec '
        if stdin:
            full_cmd += '-i '
        full_cmd += '{0} '.format(name)
        if keep_env is not True:
            full_cmd += 'env -i '
            if 'PATH' not in to_keep:
                full_cmd += '{0} '.format(PATH)
        full_cmd += ' '.join(
            ['{0}={1}'.format(x, pipes.quote(os.environ[x]))
                for x in to_keep
                if x in os.environ]
        )
        full_cmd += ' {0}'.format(cmd)

    if not use_vt:
        ret = __salt__[cmd_func](full_cmd,
                                 stdin=stdin,
                                 python_shell=python_shell,
                                 output_loglevel=output_loglevel,
                                 ignore_retcode=ignore_retcode)
    else:
        stdout, stderr = '', ''
        proc = vt.Terminal(
            full_cmd,
            shell=python_shell,
            log_stdin_level='quiet' if output_loglevel == 'quiet' else 'info',
            log_stdout_level=output_loglevel,
            log_stderr_level=output_loglevel,
            log_stdout=True,
            log_stderr=True,
            stream_stdout=False,
            stream_stderr=False
        )
        # Consume output
        try:
            while proc.has_unread_data:
                try:
                    cstdout, cstderr = proc.recv()
                    if cstdout:
                        stdout += cstdout
                    if cstderr:
                        if output is None:
                            stdout += cstderr
                        else:
                            stderr += cstderr
                    time.sleep(0.5)
                except KeyboardInterrupt:
                    break
            ret = stdout if output is None \
                else {'retcode': proc.exitstatus,
                      'pid': 2,
                      'stdout': stdout,
                      'stderr': stderr}
        except vt.TerminalException:
            trace = traceback.format_exc()
            log.error(trace)
            ret = stdout if output is None \
                else {'retcode': 127,
                      'pid': 2,
                      'stdout': stdout,
                      'stderr': stderr}
        finally:
            proc.terminate()

    return ret


@_validate
def copy_to(name,
            source,
            dest,
            container_type=None,
            path=None,
            exec_driver=None,
            overwrite=False,
            makedirs=False):
    '''
    Common logic for copying files to containers

    path
        path to the container parent (for LXC only)
        default: /var/lib/lxc (system default)

    CLI Example:

    .. code-block:: bash

        salt myminion container_resource.copy_to mycontainer /local/file/path /container/file/path container_type=docker exec_driver=nsenter
    '''
    # Get the appropriate functions
    state = __salt__['{0}.state'.format(container_type)]

    def run_all(*args, **akwargs):
        akwargs = copy.deepcopy(akwargs)
        if container_type in ['lxc'] and 'path' not in akwargs:
            akwargs['path'] = path
        return __salt__['{0}.run_all'.format(container_type)](
            *args, **akwargs)

    state_kwargs = {}
    cmd_kwargs = {'ignore_retcode': True}
    if container_type in ['lxc']:
        cmd_kwargs['path'] = path
        state_kwargs['path'] = path

    def _state(name):
        if state_kwargs:
            return state(name, **state_kwargs)
        else:
            return state(name)

    c_state = _state(name)
    if c_state != 'running':
        raise CommandExecutionError(
            'Container \'{0}\' is not running'.format(name)
        )

    local_file = cache_file(source)
    source_dir, source_name = os.path.split(local_file)

    # Source file sanity checks
    if not os.path.isabs(local_file):
        raise SaltInvocationError('Source path must be absolute')
    elif not os.path.exists(local_file):
        raise SaltInvocationError(
            'Source file {0} does not exist'.format(local_file)
        )
    elif not os.path.isfile(local_file):
        raise SaltInvocationError('Source must be a regular file')

    # Destination file sanity checks
    if not os.path.isabs(dest):
        raise SaltInvocationError('Destination path must be absolute')
    if run_all(name,
               'test -d {0}'.format(pipes.quote(dest)),
               **cmd_kwargs)['retcode'] == 0:
        # Destination is a directory, full path to dest file will include the
        # basename of the source file.
        dest = os.path.join(dest, source_name)
    else:
        # Destination was not a directory. We will check to see if the parent
        # dir is a directory, and then (if makedirs=True) attempt to create the
        # parent directory.
        dest_dir, dest_name = os.path.split(dest)
        if run_all(name,
                   'test -d {0}'.format(pipes.quote(dest_dir)),
                   **cmd_kwargs)['retcode'] != 0:
            if makedirs:
                result = run_all(name,
                                 'mkdir -p {0}'.format(pipes.quote(dest_dir)),
                                 **cmd_kwargs)
                if result['retcode'] != 0:
                    error = ('Unable to create destination directory {0} in '
                             'container \'{1}\''.format(dest_dir, name))
                    if result['stderr']:
                        error += ': {0}'.format(result['stderr'])
                    raise CommandExecutionError(error)
            else:
                raise SaltInvocationError(
                    'Directory {0} does not exist on {1} container \'{2}\''
                    .format(dest_dir, container_type, name)
                )
    if not overwrite and run_all(name,
                                 'test -e {0}'.format(pipes.quote(dest)),
                                 **cmd_kwargs)['retcode'] == 0:
        raise CommandExecutionError(
            'Destination path {0} already exists. Use overwrite=True to '
            'overwrite it'.format(dest)
        )

    # Before we try to replace the file, compare checksums.
    source_md5 = __salt__['file.get_sum'](local_file, 'md5')
    if source_md5 == _get_md5(name, dest, run_all):
        log.debug('{0} and {1}:{2} are the same file, skipping copy'
                  .format(source, name, dest))
        return True

    log.debug('Copying {0} to {1} container \'{2}\' as {3}'
              .format(source, container_type, name, dest))

    # Using cat here instead of opening the file, reading it into memory,
    # and passing it as stdin to run(). This will keep down memory
    # usage for the minion and make the operation run quicker.
    if exec_driver == 'lxc-attach':
        lxcattach = 'lxc-attach'
        if path:
            lxcattach += ' -P {0}'.format(pipes.quote(path))
        copy_cmd = (
            'cat "{0}" | {4} --clear-env --set-var {1} -n {2} -- '
            'tee "{3}"'.format(local_file, PATH, name, dest, lxcattach)
        )
    elif exec_driver == 'nsenter':
        pid = __salt__['{0}.pid'.format(container_type)](name)
        copy_cmd = (
            'cat "{0}" | {1} env -i {2} tee "{3}"'
            .format(local_file, _nsenter(pid), PATH, dest)
        )
    elif exec_driver == 'docker-exec':
        copy_cmd = (
            'cat "{0}" | docker exec -i {1} env -i {2} tee "{3}"'
            .format(local_file, name, PATH, dest)
        )
    __salt__['cmd.run'](copy_cmd, python_shell=True, output_loglevel='quiet')
    return source_md5 == _get_md5(name, dest, run_all)
