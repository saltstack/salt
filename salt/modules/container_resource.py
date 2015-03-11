# -*- coding: utf-8 -*-
'''
Common resources for LXC and systemd-nspawn containers

These functions are not designed to be called directly, but instead from the
:mod:`lxc <salt.modules.lxc>` and the (future) :mod:`nspawn
<salt.modules.nspawn>` execution modules.
'''

# Import python libs
from __future__ import absolute_import
import logging
import time
import traceback

# Import salt libs
from salt.exceptions import SaltInvocationError
from salt.utils import vt

log = logging.getLogger(__name__)


def run(name,
        cmd,
        output=None,
        no_start=False,
        stdin=None,
        python_shell=True,
        output_loglevel='debug',
        ignore_retcode=False,
        use_vt=False):
    '''
    Common logic for running shell commands in containers

    Requires the full command to be passed to :mod:`cmd.run
    <salt.modules.cmdmod.run>`/:mod:`cmd.run_all <salt.modules.cmdmod.run_all>`
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

    if not use_vt:
        ret = __salt__[cmd_func](cmd,
                                 stdin=stdin,
                                 python_shell=python_shell,
                                 output_loglevel=output_loglevel,
                                 ignore_retcode=ignore_retcode)
    else:
        stdout, stderr = '', ''
        try:
            proc = vt.Terminal(cmd,
                               shell=python_shell,
                               log_stdin_level=output_loglevel if
                                               output_loglevel == 'quiet'
                                               else 'info',
                               log_stdout_level=output_loglevel,
                               log_stderr_level=output_loglevel,
                               log_stdout=True,
                               log_stderr=True,
                               stream_stdout=False,
                               stream_stderr=False)
            # Consume output
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
