# -*- coding: utf-8 -*-
'''
Create ssh executor system
'''
# Import python libs
from __future__ import absolute_import, print_function
import base64
import copy
import getpass
import json
import logging
import multiprocessing
import subprocess
import hashlib
import tarfile
import os
import re
import sys
import time
import uuid
import tempfile
import binascii
import sys
import datetime

# Import salt libs
import salt.output
import salt.client.ssh.shell
import salt.client.ssh.wrapper
import salt.config
import salt.exceptions
import salt.defaults.exitcodes
import salt.log
import salt.loader
import salt.minion
import salt.roster
import salt.serializers.yaml
import salt.state
import salt.utils
import salt.utils.args
import salt.utils.atomicfile
import salt.utils.event
import salt.utils.files
import salt.utils.network
import salt.utils.path
import salt.utils.stringutils
import salt.utils.thin
import salt.utils.url
import salt.utils.verify
from salt.utils.locales import sdecode
from salt.utils.platform import is_windows
from salt.utils.process import MultiprocessingProcess
import salt.roster
from salt.template import compile_template

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import input  # pylint: disable=import-error,redefined-builtin
try:
    import saltwinshell
    HAS_WINSHELL = False
except ImportError:
    HAS_WINSHELL = False
try:
    import zmq
    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

# The directory where salt thin is deployed
DEFAULT_THIN_DIR = u'/var/tmp/.%%USER%%_%%FQDNUUID%%_salt'

# RSTR is just a delimiter to distinguish the beginning of salt STDOUT
# and STDERR.  There is no special meaning.  Messages prior to RSTR in
# stderr and stdout are either from SSH or from the shim.
#
# RSTR on both stdout and stderr:
#    no errors in SHIM - output after RSTR is from salt
# No RSTR in stderr, RSTR in stdout:
#    no errors in SSH_SH_SHIM, but SHIM commands for salt master are after
#    RSTR in stdout
# No RSTR in stderr, no RSTR in stdout:
#    Failure in SHIM
# RSTR in stderr, No RSTR in stdout:
#    Undefined behavior
RSTR = u'_edbc7885e4f9aac9b83b35999b68d015148caf467b78fa39c05f669c0ff89878'

# The regex to find RSTR in output - Must be on an output line by itself
# NOTE - must use non-grouping match groups or output splitting will fail.
RSTR_RE = sdecode(r'(?:^|\r?\n)' + RSTR + r'(?:\r?\n|$)')  # future lint: disable=non-unicode-string

# METHODOLOGY:
#
#   1) Make the _thinnest_ /bin/sh shim (SSH_SH_SHIM) to find the python
#      interpreter and get it invoked
#   2) Once a qualified python is found start it with the SSH_PY_SHIM
#   3) The shim is converted to a single semicolon separated line, so
#      some constructs are needed to keep it clean.

# NOTE:
#   * SSH_SH_SHIM is generic and can be used to load+exec *any* python
#     script on the target.
#   * SSH_PY_SHIM is in a separate file rather than stuffed in a string
#     in salt/client/ssh/__init__.py - this makes testing *easy* because
#     it can be invoked directly.
#   * SSH_PY_SHIM is base64 encoded and formatted into the SSH_SH_SHIM
#     string.  This makes the python script "armored" so that it can
#     all be passed in the SSH command and will not need special quoting
#     (which likely would be impossibe to do anyway)
#   * The formatted SSH_SH_SHIM with the SSH_PY_SHIM payload is a bit
#     big (~7.5k).  If this proves problematic for an SSH command we
#     might try simply invoking "/bin/sh -s" and passing the formatted
#     SSH_SH_SHIM on SSH stdin.

# NOTE: there are two passes of formatting:
# 1) Substitute in static values
#   - EX_THIN_PYTHON_INVALID  - exit code if a suitable python is not found
# 2) Substitute in instance-specific commands
#   - DEBUG       - enable shim debugging (any non-zero string enables)
#   - SUDO        - load python and execute as root (any non-zero string enables)
#   - SSH_PY_CODE - base64-encoded python code to execute
#   - SSH_PY_ARGS - arguments to pass to python code

# This shim generically loads python code . . . and *no* more.
# - Uses /bin/sh for maximum compatibility - then jumps to
#   python for ultra-maximum compatibility.
#
# 1. Identify a suitable python
# 2. Jump to python

# Note the list-comprehension syntax to define SSH_SH_SHIM is needed
# to be able to define the string with indentation for readability but
# still strip the white space for compactness and to avoid issues with
# some multi-line embedded python code having indentation errors
# future lint: disable=non-unicode-string
SSH_SH_SHIM = \
    u'\n'.join(
        [s.strip() for s in r'''/bin/sh << 'EOF'
set -e
set -u
DEBUG="{{DEBUG}}"
if [ -n "$DEBUG" ]
    then set -x
fi
SUDO=""
if [ -n "{{SUDO}}" ]
    then SUDO="sudo "
fi
SUDO_USER="{{SUDO_USER}}"
if [ "$SUDO" ] && [ "$SUDO_USER" ]
then SUDO="sudo -u {{SUDO_USER}}"
elif [ "$SUDO" ] && [ -n "$SUDO_USER" ]
then SUDO="sudo "
fi
EX_PYTHON_INVALID={EX_THIN_PYTHON_INVALID}
PYTHON_CMDS="python3 python27 python2.7 python26 python2.6 python2 python"
for py_cmd in $PYTHON_CMDS
do
    if command -v "$py_cmd" >/dev/null 2>&1 && "$py_cmd" -c \
        "import sys; sys.exit(not (sys.version_info >= (2, 6)
                              and sys.version_info[0] == {{HOST_PY_MAJOR}}));"
    then
        py_cmd_path=`"$py_cmd" -c \
                   'from __future__ import print_function;
                   import sys; print(sys.executable);'`
        cmdpath=$(command -v $py_cmd 2>/dev/null || which $py_cmd 2>/dev/null)
        if file $cmdpath | grep "shell script" > /dev/null
        then
            ex_vars="'PATH', 'LD_LIBRARY_PATH', 'MANPATH', \
                   'XDG_DATA_DIRS', 'PKG_CONFIG_PATH'"
            export $($py_cmd -c \
                  "from __future__ import print_function;
                  import sys;
                  import os;
                  map(sys.stdout.write, [u'{{{{0}}}}={{{{1}}}} ' \
                  .format(x, os.environ[x]) for x in [$ex_vars]])")
            exec $SUDO PATH=$PATH LD_LIBRARY_PATH=$LD_LIBRARY_PATH \
                     MANPATH=$MANPATH XDG_DATA_DIRS=$XDG_DATA_DIRS \
                     PKG_CONFIG_PATH=$PKG_CONFIG_PATH \
                     "$py_cmd_path" -c \
                   'import base64;
                   exec(base64.b64decode("""{{SSH_PY_CODE}}""").decode("utf-8"))'
        else
            exec $SUDO "$py_cmd_path" -c \
                   'import base64;
                   exec(base64.b64decode("""{{SSH_PY_CODE}}""").decode("utf-8"))'
        fi
        exit 0
    else
        continue
    fi
done
echo "ERROR: Unable to locate appropriate python command" >&2
exit $EX_PYTHON_INVALID
EOF'''.format(
            EX_THIN_PYTHON_INVALID=salt.defaults.exitcodes.EX_THIN_PYTHON_INVALID,
            ).split(u'\n')])
# future lint: enable=non-unicode-string

if not is_windows():
    shim_file = os.path.join(os.path.dirname(__file__), u'ssh_py_shim.py')
    if not os.path.exists(shim_file):
        # On esky builds we only have the .pyc file
        shim_file += u'c'
    with salt.utils.files.fopen(shim_file) as ssh_py_shim:
        SSH_PY_SHIM = ssh_py_shim.read()

log = logging.getLogger(__name__)


class SSH(object):
    '''
    Create an SSH execution system
    '''
    ROSTER_UPDATE_FLAG = '#__needs_update'

    def __init__(self, opts):
        self.__parsed_rosters = {SSH.ROSTER_UPDATE_FLAG: True}
        pull_sock = os.path.join(opts['sock_dir'], 'master_event_pull.ipc')
        if os.path.isfile(pull_sock) and HAS_ZMQ:
            self.event = salt.utils.event.get_event(
                    u'master',
                    opts[u'sock_dir'],
                    opts[u'transport'],
                    opts=opts,
                    listen=False)
        else:
            self.event = None
        self.opts = opts
        if self.opts['regen_thin']:
            self.opts['ssh_wipe'] = True
        if not salt.utils.path.which('ssh'):
            raise salt.exceptions.SaltSystemExit('No ssh binary found in path -- ssh must be '
                                                 'installed for salt-ssh to run. Exiting.')
        self.opts['_ssh_version'] = ssh_version()
        self.tgt_type = self.opts['selected_target_option'] \
            if self.opts['selected_target_option'] else 'glob'
        self._expand_target()
        self.roster = salt.roster.Roster(self.opts, self.opts.get('roster', 'flat'))
        self.targets = self.roster.targets(
                self.opts[u'tgt'],
                self.tgt_type)
        if not self.targets:
            self._update_targets()
        # If we're in a wfunc, we need to get the ssh key location from the
        # top level opts, stored in __master_opts__
        if u'__master_opts__' in self.opts:
            if self.opts[u'__master_opts__'].get(u'ssh_use_home_key') and \
                    os.path.isfile(os.path.expanduser(u'~/.ssh/id_rsa')):
                priv = os.path.expanduser(u'~/.ssh/id_rsa')
            else:
                priv = self.opts[u'__master_opts__'].get(
                        u'ssh_priv',
                        os.path.join(
                            self.opts[u'__master_opts__'][u'pki_dir'],
                            u'ssh',
                            u'salt-ssh.rsa'
                            )
                        )
        else:
            priv = self.opts.get(
                    u'ssh_priv',
                    os.path.join(
                        self.opts[u'pki_dir'],
                        u'ssh',
                        u'salt-ssh.rsa'
                        )
                    )
        if priv != u'agent-forwarding':
            if not os.path.isfile(priv):
                try:
                    salt.client.ssh.shell.gen_key(priv)
                except OSError:
                    raise salt.exceptions.SaltClientError(
                        u'salt-ssh could not be run because it could not generate keys.\n\n'
                        u'You can probably resolve this by executing this script with '
                        u'increased permissions via sudo or by running as root.\n'
                        u'You could also use the \'-c\' option to supply a configuration '
                        u'directory that you have permissions to read and write to.'
                    )
        self.defaults = {
            u'user': self.opts.get(
                u'ssh_user',
                salt.config.DEFAULT_MASTER_OPTS[u'ssh_user']
            ),
            u'port': self.opts.get(
                u'ssh_port',
                salt.config.DEFAULT_MASTER_OPTS[u'ssh_port']
            ),
            u'passwd': self.opts.get(
                u'ssh_passwd',
                salt.config.DEFAULT_MASTER_OPTS[u'ssh_passwd']
            ),
            u'priv': priv,
            u'timeout': self.opts.get(
                u'ssh_timeout',
                salt.config.DEFAULT_MASTER_OPTS[u'ssh_timeout']
            ) + self.opts.get(
                u'timeout',
                salt.config.DEFAULT_MASTER_OPTS[u'timeout']
            ),
            u'sudo': self.opts.get(
                u'ssh_sudo',
                salt.config.DEFAULT_MASTER_OPTS[u'ssh_sudo']
            ),
            u'sudo_user': self.opts.get(
                u'ssh_sudo_user',
                salt.config.DEFAULT_MASTER_OPTS[u'ssh_sudo_user']
            ),
            u'identities_only': self.opts.get(
                u'ssh_identities_only',
                salt.config.DEFAULT_MASTER_OPTS[u'ssh_identities_only']
            ),
            u'remote_port_forwards': self.opts.get(
                u'ssh_remote_port_forwards'
            ),
            u'ssh_options': self.opts.get(
                u'ssh_options'
            )
        }
        if self.opts.get(u'rand_thin_dir'):
            self.defaults[u'thin_dir'] = os.path.join(
                    u'/var/tmp',
                    u'.{0}'.format(uuid.uuid4().hex[:6]))
            self.opts[u'ssh_wipe'] = u'True'
        self.serial = salt.payload.Serial(opts)
        self.returners = salt.loader.returners(self.opts, {})
        self.fsclient = salt.fileclient.FSClient(self.opts)
        self.thin = salt.utils.thin.gen_thin(self.opts[u'cachedir'],
                                             extra_mods=self.opts.get(u'thin_extra_mods'),
                                             overwrite=self.opts[u'regen_thin'],
                                             python2_bin=self.opts[u'python2_bin'],
                                             python3_bin=self.opts[u'python3_bin'])
        self.mods = mod_data(self.fsclient)

    def _get_roster(self):
        '''
        Read roster filename as a key to the data.
        :return:
        '''
        roster_file = salt.roster.get_roster_file(self.opts)
        if roster_file not in self.__parsed_rosters:
            roster_data = compile_template(roster_file, salt.loader.render(self.opts, {}),
                                           self.opts['renderer'], self.opts['renderer_blacklist'],
                                           self.opts['renderer_whitelist'])
            self.__parsed_rosters[roster_file] = roster_data
        return roster_file

    def _expand_target(self):
        '''
        Figures out if the target is a reachable host without wildcards, expands if any.
        :return:
        '''
        # TODO: Support -L
        target = self.opts['tgt']
        if isinstance(target, list):
            return

        hostname = self.opts['tgt'].split('@')[-1]
        needs_expansion = '*' not in hostname and salt.utils.network.is_reachable_host(hostname)
        if needs_expansion:
            hostname = salt.utils.network.ip_to_host(hostname)
            self._get_roster()
            for roster_filename in self.__parsed_rosters:
                roster_data = self.__parsed_rosters[roster_filename]
                if not isinstance(roster_data, bool):
                    for host_id in roster_data:
                        if hostname in [host_id, roster_data.get('host')]:
                            if hostname != self.opts['tgt']:
                                self.opts['tgt'] = hostname
                            self.__parsed_rosters[self.ROSTER_UPDATE_FLAG] = False
                            return

    def _update_roster(self):
        '''
        Update default flat roster with the passed in information.
        :return:
        '''
        roster_file = self._get_roster()
        if os.access(roster_file, os.W_OK):
            if self.__parsed_rosters[self.ROSTER_UPDATE_FLAG]:
                with salt.utils.files.fopen(roster_file, 'a') as roster_fp:
                    roster_fp.write('# Automatically added by "{s_user}" at {s_time}\n{hostname}:\n    host: '
                                    '{hostname}\n    user: {user}'
                                    '\n    passwd: {passwd}\n'.format(s_user=getpass.getuser(),
                                                                      s_time=datetime.datetime.utcnow().isoformat(),
                                                                      hostname=self.opts.get('tgt', ''),
                                                                      user=self.opts.get('ssh_user', ''),
                                                                      passwd=self.opts.get('ssh_passwd', '')))
                log.info('The host {0} has been added to the roster {1}'.format(self.opts.get('tgt', ''),
                                                                                roster_file))
        else:
            log.error('Unable to update roster {0}: access denied'.format(roster_file))

    def _update_targets(self):
        '''
        Uptade targets in case hostname was directly passed without the roster.
        :return:
        '''

        hostname = self.opts.get('tgt', '')
        if '@' in hostname:
            user, hostname = hostname.split('@', 1)
        else:
            user = self.opts.get('ssh_user')
        if hostname == '*':
            hostname = ''

        if salt.utils.network.is_reachable_host(hostname):
            hostname = salt.utils.network.ip_to_host(hostname)
            self.opts['tgt'] = hostname
            self.targets[hostname] = {
                'passwd': self.opts.get('ssh_passwd', ''),
                'host': hostname,
                'user': user,
            }
            if not self.opts.get('ssh_skip_roster'):
                self._update_roster()

    def get_pubkey(self):
        '''
        Return the key string for the SSH public key
        '''
        if u'__master_opts__' in self.opts and \
                self.opts[u'__master_opts__'].get(u'ssh_use_home_key') and \
                os.path.isfile(os.path.expanduser(u'~/.ssh/id_rsa')):
            priv = os.path.expanduser(u'~/.ssh/id_rsa')
        else:
            priv = self.opts.get(
                    u'ssh_priv',
                    os.path.join(
                        self.opts[u'pki_dir'],
                        u'ssh',
                        u'salt-ssh.rsa'
                        )
                    )
        pub = u'{0}.pub'.format(priv)
        with salt.utils.files.fopen(pub, u'r') as fp_:
            return u'{0} rsa root@master'.format(fp_.read().split()[1])

    def key_deploy(self, host, ret):
        '''
        Deploy the SSH key if the minions don't auth
        '''
        if not isinstance(ret[host], dict) or self.opts.get(u'ssh_key_deploy'):
            target = self.targets[host]
            if target.get(u'passwd', False) or self.opts[u'ssh_passwd']:
                self._key_deploy_run(host, target, False)
            return ret
        if ret[host].get(u'stderr', u'').count(u'Permission denied'):
            target = self.targets[host]
            # permission denied, attempt to auto deploy ssh key
            print((u'Permission denied for host {0}, do you want to deploy '
                   u'the salt-ssh key? (password required):').format(host))
            deploy = input(u'[Y/n] ')
            if deploy.startswith((u'n', u'N')):
                return ret
            target[u'passwd'] = getpass.getpass(
                    u'Password for {0}@{1}: '.format(target[u'user'], host)
                )
            return self._key_deploy_run(host, target, True)
        return ret

    def _key_deploy_run(self, host, target, re_run=True):
        '''
        The ssh-copy-id routine
        '''
        argv = [
            u'ssh.set_auth_key',
            target.get(u'user', u'root'),
            self.get_pubkey(),
        ]

        single = Single(
                self.opts,
                argv,
                host,
                mods=self.mods,
                fsclient=self.fsclient,
                thin=self.thin,
                **target)
        if salt.utils.path.which(u'ssh-copy-id'):
            # we have ssh-copy-id, use it!
            stdout, stderr, retcode = single.shell.copy_id()
        else:
            stdout, stderr, retcode = single.run()
        if re_run:
            target.pop(u'passwd')
            single = Single(
                    self.opts,
                    self.opts[u'argv'],
                    host,
                    mods=self.mods,
                    fsclient=self.fsclient,
                    thin=self.thin,
                    **target)
            stdout, stderr, retcode = single.cmd_block()
            try:
                data = salt.utils.find_json(stdout)
                return {host: data.get(u'local', data)}
            except Exception:
                if stderr:
                    return {host: stderr}
                return {host: u'Bad Return'}
        if salt.defaults.exitcodes.EX_OK != retcode:
            return {host: stderr}
        return {host: stdout}

    def handle_routine(self, que, opts, host, target, mine=False):
        '''
        Run the routine in a "Thread", put a dict on the queue
        '''
        opts = copy.deepcopy(opts)
        single = Single(
                opts,
                opts[u'argv'],
                host,
                mods=self.mods,
                fsclient=self.fsclient,
                thin=self.thin,
                mine=mine,
                **target)
        ret = {u'id': single.id}
        stdout, stderr, retcode = single.run()
        # This job is done, yield
        try:
            data = salt.utils.find_json(stdout)
            if len(data) < 2 and u'local' in data:
                ret[u'ret'] = data[u'local']
            else:
                ret[u'ret'] = {
                    u'stdout': stdout,
                    u'stderr': stderr,
                    u'retcode': retcode,
                }
        except Exception:
            ret[u'ret'] = {
                u'stdout': stdout,
                u'stderr': stderr,
                u'retcode': retcode,
            }
        que.put(ret)

    def handle_ssh(self, mine=False):
        '''
        Spin up the needed threads or processes and execute the subsequent
        routines
        '''
        que = multiprocessing.Queue()
        running = {}
        target_iter = self.targets.__iter__()
        returned = set()
        rets = set()
        init = False
        while True:
            if not self.targets:
                log.error(u'No matching targets found in roster.')
                break
            if len(running) < self.opts.get(u'ssh_max_procs', 25) and not init:
                try:
                    host = next(target_iter)
                except StopIteration:
                    init = True
                    continue
                for default in self.defaults:
                    if default not in self.targets[host]:
                        self.targets[host][default] = self.defaults[default]
                if 'host' not in self.targets[host]:
                    self.targets[host]['host'] = host
                args = (
                        que,
                        self.opts,
                        host,
                        self.targets[host],
                        mine,
                        )
                routine = MultiprocessingProcess(
                                target=self.handle_routine,
                                args=args)
                routine.start()
                running[host] = {u'thread': routine}
                continue
            ret = {}
            try:
                ret = que.get(False)
                if u'id' in ret:
                    returned.add(ret[u'id'])
                    yield {ret[u'id']: ret[u'ret']}
            except Exception:
                # This bare exception is here to catch spurious exceptions
                # thrown by que.get during healthy operation. Please do not
                # worry about this bare exception, it is entirely here to
                # control program flow.
                pass
            for host in running:
                if not running[host][u'thread'].is_alive():
                    if host not in returned:
                        # Try to get any returns that came through since we
                        # last checked
                        try:
                            while True:
                                ret = que.get(False)
                                if u'id' in ret:
                                    returned.add(ret[u'id'])
                                    yield {ret[u'id']: ret[u'ret']}
                        except Exception:
                            pass

                        if host not in returned:
                            error = (u'Target \'{0}\' did not return any data, '
                                     u'probably due to an error.').format(host)
                            ret = {u'id': host,
                                   u'ret': error}
                            log.error(error)
                            yield {ret[u'id']: ret[u'ret']}
                    running[host][u'thread'].join()
                    rets.add(host)
            for host in rets:
                if host in running:
                    running.pop(host)
            if len(rets) >= len(self.targets):
                break
            # Sleep when limit or all threads started
            if len(running) >= self.opts.get(u'ssh_max_procs', 25) or len(self.targets) >= len(running):
                time.sleep(0.1)

    def run_iter(self, mine=False, jid=None):
        '''
        Execute and yield returns as they come in, do not print to the display

        mine
            The Single objects will use mine_functions defined in the roster,
            pillar, or master config (they will be checked in that order) and
            will modify the argv with the arguments from mine_functions
        '''
        fstr = u'{0}.prep_jid'.format(self.opts[u'master_job_cache'])
        jid = self.returners[fstr](passed_jid=jid or self.opts.get(u'jid', None))

        # Save the invocation information
        argv = self.opts[u'argv']

        if self.opts.get(u'raw_shell', False):
            fun = u'ssh._raw'
            args = argv
        else:
            fun = argv[0] if argv else u''
            args = argv[1:]

        job_load = {
            u'jid': jid,
            u'tgt_type': self.tgt_type,
            u'tgt': self.opts[u'tgt'],
            u'user': self.opts[u'user'],
            u'fun': fun,
            u'arg': args,
            }

        # save load to the master job cache
        if self.opts[u'master_job_cache'] == u'local_cache':
            self.returners[u'{0}.save_load'.format(self.opts[u'master_job_cache'])](jid, job_load, minions=self.targets.keys())
        else:
            self.returners[u'{0}.save_load'.format(self.opts[u'master_job_cache'])](jid, job_load)

        for ret in self.handle_ssh(mine=mine):
            host = next(six.iterkeys(ret))
            self.cache_job(jid, host, ret[host], fun)
            if self.event:
                self.event.fire_event(
                        ret,
                        salt.utils.event.tagify(
                            [jid, u'ret', host],
                            u'job'))
            yield ret

    def cache_job(self, jid, id_, ret, fun):
        '''
        Cache the job information
        '''
        self.returners[u'{0}.returner'.format(self.opts[u'master_job_cache'])]({u'jid': jid,
                                                                              u'id': id_,
                                                                              u'return': ret,
                                                                              u'fun': fun})

    def run(self, jid=None):
        '''
        Execute the overall routine, print results via outputters
        '''
        if self.opts['list_hosts']:
            self._get_roster()
            ret = {}
            for roster_file in self.__parsed_rosters:
                if roster_file.startswith('#'):
                    continue
                ret[roster_file] = {}
                for host_id in self.__parsed_rosters[roster_file]:
                    hostname = self.__parsed_rosters[roster_file][host_id]['host']
                    ret[roster_file][host_id] = hostname
            salt.output.display_output(ret, 'nested', self.opts)
            sys.exit()

        fstr = '{0}.prep_jid'.format(self.opts['master_job_cache'])
        jid = self.returners[fstr](passed_jid=jid or self.opts.get('jid', None))

        # Save the invocation information
        argv = self.opts[u'argv']

        if self.opts.get(u'raw_shell', False):
            fun = u'ssh._raw'
            args = argv
        else:
            fun = argv[0] if argv else u''
            args = argv[1:]

        job_load = {
            u'jid': jid,
            u'tgt_type': self.tgt_type,
            u'tgt': self.opts[u'tgt'],
            u'user': self.opts[u'user'],
            u'fun': fun,
            u'arg': args,
            }

        # save load to the master job cache
        try:
            if isinstance(jid, bytes):
                jid = jid.decode(u'utf-8')
            if self.opts[u'master_job_cache'] == u'local_cache':
                self.returners[u'{0}.save_load'.format(self.opts[u'master_job_cache'])](jid, job_load, minions=self.targets.keys())
            else:
                self.returners[u'{0}.save_load'.format(self.opts[u'master_job_cache'])](jid, job_load)
        except Exception as exc:
            log.exception(exc)
            log.error(
                u'Could not save load with returner %s: %s',
                self.opts[u'master_job_cache'], exc
            )

        if self.opts.get(u'verbose'):
            msg = u'Executing job with jid {0}'.format(jid)
            print(msg)
            print(u'-' * len(msg) + u'\n')
            print(u'')
        sret = {}
        outputter = self.opts.get(u'output', u'nested')
        final_exit = 0
        for ret in self.handle_ssh():
            host = next(six.iterkeys(ret))
            if isinstance(ret[host], dict):
                host_ret = ret[host].get(u'retcode', 0)
                if host_ret != 0:
                    final_exit = 1
            else:
                # Error on host
                final_exit = 1

            self.cache_job(jid, host, ret[host], fun)
            ret = self.key_deploy(host, ret)

            if isinstance(ret[host], dict) and ret[host].get(u'stderr', u'').startswith(u'ssh:'):
                ret[host] = ret[host][u'stderr']

            if not isinstance(ret[host], dict):
                p_data = {host: ret[host]}
            elif u'return' not in ret[host]:
                p_data = ret
            else:
                outputter = ret[host].get(u'out', self.opts.get(u'output', u'nested'))
                p_data = {host: ret[host].get(u'return', {})}
            if self.opts.get(u'static'):
                sret.update(p_data)
            else:
                salt.output.display_output(
                        p_data,
                        outputter,
                        self.opts)
            if self.event:
                self.event.fire_event(
                        ret,
                        salt.utils.event.tagify(
                            [jid, u'ret', host],
                            u'job'))
        if self.opts.get(u'static'):
            salt.output.display_output(
                    sret,
                    outputter,
                    self.opts)
        if final_exit:
            sys.exit(salt.defaults.exitcodes.EX_AGGREGATE)


class Single(object):
    '''
    Hold onto a single ssh execution
    '''
    # 1. Get command ready
    # 2. Check if target has salt
    # 3. deploy salt-thin
    # 4. execute requested command via salt-thin
    def __init__(
            self,
            opts,
            argv,
            id_,
            host,
            user=None,
            port=None,
            passwd=None,
            priv=None,
            timeout=30,
            sudo=False,
            tty=False,
            mods=None,
            fsclient=None,
            thin=None,
            mine=False,
            minion_opts=None,
            identities_only=False,
            sudo_user=None,
            remote_port_forwards=None,
            winrm=False,
            ssh_options=None,
            **kwargs):
        # Get mine setting and mine_functions if defined in kwargs (from roster)
        self.mine = mine
        self.mine_functions = kwargs.get(u'mine_functions')
        self.cmd_umask = kwargs.get(u'cmd_umask', None)

        self.winrm = winrm

        self.opts = opts
        self.tty = tty
        if kwargs.get(u'wipe'):
            self.wipe = u'False'
        else:
            self.wipe = u'True' if self.opts.get(u'ssh_wipe') else u'False'
        if kwargs.get(u'thin_dir'):
            self.thin_dir = kwargs[u'thin_dir']
        elif self.winrm:
            saltwinshell.set_winvars(self)
        else:
            if user:
                thin_dir = DEFAULT_THIN_DIR.replace(u'%%USER%%', user)
            else:
                thin_dir = DEFAULT_THIN_DIR.replace(u'%%USER%%', u'root')
            self.thin_dir = thin_dir.replace(
                u'%%FQDNUUID%%',
                uuid.uuid3(uuid.NAMESPACE_DNS,
                           salt.utils.network.get_fqhostname()).hex[:6]
            )
        self.opts[u'thin_dir'] = self.thin_dir
        self.fsclient = fsclient
        self.context = {u'master_opts': self.opts,
                        u'fileclient': self.fsclient}

        if isinstance(argv, six.string_types):
            self.argv = [argv]
        else:
            self.argv = argv

        self.fun, self.args, self.kwargs = self.__arg_comps()
        self.id = id_

        self.mods = mods if isinstance(mods, dict) else {}
        args = {u'host': host,
                u'user': user,
                u'port': port,
                u'passwd': passwd,
                u'priv': priv,
                u'timeout': timeout,
                u'sudo': sudo,
                u'tty': tty,
                u'mods': self.mods,
                u'identities_only': identities_only,
                u'sudo_user': sudo_user,
                u'remote_port_forwards': remote_port_forwards,
                u'winrm': winrm,
                u'ssh_options': ssh_options}
        # Pre apply changeable defaults
        self.minion_opts = {
                    u'grains_cache': True,
                }
        self.minion_opts.update(opts.get(u'ssh_minion_opts', {}))
        if minion_opts is not None:
            self.minion_opts.update(minion_opts)
        # Post apply system needed defaults
        self.minion_opts.update({
                    u'root_dir': os.path.join(self.thin_dir, u'running_data'),
                    u'id': self.id,
                    u'sock_dir': u'/',
                    u'log_file': u'salt-call.log',
                    u'fileserver_list_cache_time': 3,
                })
        self.minion_config = salt.serializers.yaml.serialize(self.minion_opts)
        self.target = kwargs
        self.target.update(args)
        self.serial = salt.payload.Serial(opts)
        self.wfuncs = salt.loader.ssh_wrapper(opts, None, self.context)
        self.shell = salt.client.ssh.shell.gen_shell(opts, **args)
        self.thin = thin if thin else salt.utils.thin.thin_path(opts[u'cachedir'])

    def __arg_comps(self):
        '''
        Return the function name and the arg list
        '''
        fun = self.argv[0] if self.argv else u''
        parsed = salt.utils.args.parse_input(
            self.argv[1:],
            condition=False,
            no_parse=self.opts.get(u'no_parse', []))
        args = parsed[0]
        kws = parsed[1]
        return fun, args, kws

    def _escape_arg(self, arg):
        '''
        Properly escape argument to protect special characters from shell
        interpretation.  This avoids having to do tricky argument quoting.

        Effectively just escape all characters in the argument that are not
        alphanumeric!
        '''
        if self.winrm:
            return arg
        return u''.join([u'\\' + char if re.match(sdecode(r'\W'), char) else char for char in arg])  # future lint: disable=non-unicode-string

    def deploy(self):
        '''
        Deploy salt-thin
        '''
        self.shell.send(
            self.thin,
            os.path.join(self.thin_dir, u'salt-thin.tgz'),
        )
        self.deploy_ext()
        return True

    def deploy_ext(self):
        '''
        Deploy the ext_mods tarball
        '''
        if self.mods.get(u'file'):
            self.shell.send(
                self.mods[u'file'],
                os.path.join(self.thin_dir, u'salt-ext_mods.tgz'),
            )
        return True

    def run(self, deploy_attempted=False):
        '''
        Execute the routine, the routine can be either:
        1. Execute a raw shell command
        2. Execute a wrapper func
        3. Execute a remote Salt command

        If a (re)deploy is needed, then retry the operation after a deploy
        attempt

        Returns tuple of (stdout, stderr, retcode)
        '''
        stdout = stderr = retcode = None

        if self.opts.get(u'raw_shell', False):
            cmd_str = u' '.join([self._escape_arg(arg) for arg in self.argv])
            stdout, stderr, retcode = self.shell.exec_cmd(cmd_str)

        elif self.fun in self.wfuncs or self.mine:
            stdout, retcode = self.run_wfunc()

        else:
            stdout, stderr, retcode = self.cmd_block()

        return stdout, stderr, retcode

    def run_wfunc(self):
        '''
        Execute a wrapper function

        Returns tuple of (json_data, '')
        '''
        # Ensure that opts/grains are up to date
        # Execute routine
        data_cache = False
        data = None
        cdir = os.path.join(self.opts[u'cachedir'], u'minions', self.id)
        if not os.path.isdir(cdir):
            os.makedirs(cdir)
        datap = os.path.join(cdir, u'ssh_data.p')
        refresh = False
        if not os.path.isfile(datap):
            refresh = True
        else:
            passed_time = (time.time() - os.stat(datap).st_mtime) / 60
            if passed_time > self.opts.get(u'cache_life', 60):
                refresh = True

        if self.opts.get(u'refresh_cache'):
            refresh = True
        conf_grains = {}
        # Save conf file grains before they get clobbered
        if u'ssh_grains' in self.opts:
            conf_grains = self.opts[u'ssh_grains']
        if not data_cache:
            refresh = True
        if refresh:
            # Make the datap
            # TODO: Auto expire the datap
            pre_wrapper = salt.client.ssh.wrapper.FunctionWrapper(
                self.opts,
                self.id,
                fsclient=self.fsclient,
                minion_opts=self.minion_opts,
                **self.target)
            opts_pkg = pre_wrapper[u'test.opts_pkg']()  # pylint: disable=E1102
            if u'_error' in opts_pkg:
                #Refresh failed
                retcode = opts_pkg[u'retcode']
                ret = json.dumps({u'local': opts_pkg})
                return ret, retcode

            opts_pkg[u'file_roots'] = self.opts[u'file_roots']
            opts_pkg[u'pillar_roots'] = self.opts[u'pillar_roots']
            opts_pkg[u'ext_pillar'] = self.opts[u'ext_pillar']
            opts_pkg[u'extension_modules'] = self.opts[u'extension_modules']
            opts_pkg[u'_ssh_version'] = self.opts[u'_ssh_version']
            opts_pkg[u'__master_opts__'] = self.context[u'master_opts']
            if u'_caller_cachedir' in self.opts:
                opts_pkg[u'_caller_cachedir'] = self.opts[u'_caller_cachedir']
            else:
                opts_pkg[u'_caller_cachedir'] = self.opts[u'cachedir']
            # Use the ID defined in the roster file
            opts_pkg[u'id'] = self.id

            retcode = 0

            # Restore master grains
            for grain in conf_grains:
                opts_pkg[u'grains'][grain] = conf_grains[grain]
            # Enable roster grains support
            if u'grains' in self.target:
                for grain in self.target[u'grains']:
                    opts_pkg[u'grains'][grain] = self.target[u'grains'][grain]

            popts = {}
            popts.update(opts_pkg[u'__master_opts__'])
            popts.update(opts_pkg)
            pillar = salt.pillar.Pillar(
                    popts,
                    opts_pkg[u'grains'],
                    opts_pkg[u'id'],
                    opts_pkg.get(u'environment', u'base')
                    )
            pillar_data = pillar.compile_pillar()

            # TODO: cache minion opts in datap in master.py
            data = {u'opts': opts_pkg,
                    u'grains': opts_pkg[u'grains'],
                    u'pillar': pillar_data}
            if data_cache:
                with salt.utils.files.fopen(datap, u'w+b') as fp_:
                    fp_.write(
                            self.serial.dumps(data)
                            )
        if not data and data_cache:
            with salt.utils.files.fopen(datap, u'rb') as fp_:
                data = self.serial.load(fp_)
        opts = data.get(u'opts', {})
        opts[u'grains'] = data.get(u'grains')

        # Restore master grains
        for grain in conf_grains:
            opts[u'grains'][grain] = conf_grains[grain]
        # Enable roster grains support
        if u'grains' in self.target:
            for grain in self.target[u'grains']:
                opts[u'grains'][grain] = self.target[u'grains'][grain]

        opts[u'pillar'] = data.get(u'pillar')
        wrapper = salt.client.ssh.wrapper.FunctionWrapper(
            opts,
            self.id,
            fsclient=self.fsclient,
            minion_opts=self.minion_opts,
            **self.target)
        self.wfuncs = salt.loader.ssh_wrapper(opts, wrapper, self.context)
        wrapper.wfuncs = self.wfuncs

        # We're running in the mine, need to fetch the arguments from the
        # roster, pillar, master config (in that order)
        if self.mine:
            mine_args = None
            mine_fun_data = None
            mine_fun = self.fun

            if self.mine_functions and self.fun in self.mine_functions:
                mine_fun_data = self.mine_functions[self.fun]
            elif opts[u'pillar'] and self.fun in opts[u'pillar'].get(u'mine_functions', {}):
                mine_fun_data = opts[u'pillar'][u'mine_functions'][self.fun]
            elif self.fun in self.context[u'master_opts'].get(u'mine_functions', {}):
                mine_fun_data = self.context[u'master_opts'][u'mine_functions'][self.fun]

            if isinstance(mine_fun_data, dict):
                mine_fun = mine_fun_data.pop(u'mine_function', mine_fun)
                mine_args = mine_fun_data
            elif isinstance(mine_fun_data, list):
                for item in mine_fun_data[:]:
                    if isinstance(item, dict) and u'mine_function' in item:
                        mine_fun = item[u'mine_function']
                        mine_fun_data.pop(mine_fun_data.index(item))
                mine_args = mine_fun_data
            else:
                mine_args = mine_fun_data

            # If we found mine_args, replace our command's args
            if isinstance(mine_args, dict):
                self.args = []
                self.kwargs = mine_args
            elif isinstance(mine_args, list):
                self.args = mine_args
                self.kwargs = {}

        try:
            if self.mine:
                result = wrapper[mine_fun](*self.args, **self.kwargs)
            else:
                result = self.wfuncs[self.fun](*self.args, **self.kwargs)
        except TypeError as exc:
            result = u'TypeError encountered executing {0}: {1}'.format(self.fun, exc)
            log.error(result, exc_info_on_loglevel=logging.DEBUG)
            retcode = 1
        except Exception as exc:
            result = u'An Exception occurred while executing {0}: {1}'.format(self.fun, exc)
            log.error(result, exc_info_on_loglevel=logging.DEBUG)
            retcode = 1
        # Mimic the json data-structure that "salt-call --local" will
        # emit (as seen in ssh_py_shim.py)
        if isinstance(result, dict) and u'local' in result:
            ret = json.dumps({u'local': result[u'local']})
        else:
            ret = json.dumps({u'local': {u'return': result}})
        return ret, retcode

    def _cmd_str(self):
        '''
        Prepare the command string
        '''
        sudo = u'sudo' if self.target[u'sudo'] else u''
        sudo_user = self.target[u'sudo_user']
        if u'_caller_cachedir' in self.opts:
            cachedir = self.opts[u'_caller_cachedir']
        else:
            cachedir = self.opts[u'cachedir']
        thin_sum = salt.utils.thin.thin_sum(cachedir, u'sha1')
        debug = u''
        if not self.opts.get(u'log_level'):
            self.opts[u'log_level'] = u'info'
        if salt.log.LOG_LEVELS[u'debug'] >= salt.log.LOG_LEVELS[self.opts.get(u'log_level', u'info')]:
            debug = u'1'
        arg_str = u'''
OPTIONS = OBJ()
OPTIONS.config = \
"""
{0}
"""
OPTIONS.delimiter = u'{1}'
OPTIONS.saltdir = u'{2}'
OPTIONS.checksum = u'{3}'
OPTIONS.hashfunc = u'{4}'
OPTIONS.version = u'{5}'
OPTIONS.ext_mods = u'{6}'
OPTIONS.wipe = {7}
OPTIONS.tty = {8}
OPTIONS.cmd_umask = {9}
ARGS = {10}\n'''.format(self.minion_config,
                         RSTR,
                         self.thin_dir,
                         thin_sum,
                         u'sha1',
                         salt.version.__version__,
                         self.mods.get(u'version', u''),
                         self.wipe,
                         self.tty,
                         self.cmd_umask,
                         self.argv)
        py_code = SSH_PY_SHIM.replace(u'#%%OPTS', arg_str)
        if six.PY2:
            py_code_enc = py_code.encode(u'base64')
        else:
            py_code_enc = base64.encodebytes(py_code.encode(u'utf-8')).decode(u'utf-8')
        if not self.winrm:
            cmd = SSH_SH_SHIM.format(
                DEBUG=debug,
                SUDO=sudo,
                SUDO_USER=sudo_user,
                SSH_PY_CODE=py_code_enc,
                HOST_PY_MAJOR=sys.version_info[0],
            )
        else:
            cmd = saltwinshell.gen_shim(py_code_enc)

        return cmd

    def shim_cmd(self, cmd_str, extension=u'py'):
        '''
        Run a shim command.

        If tty is enabled, we must scp the shim to the target system and
        execute it there
        '''
        if not self.tty and not self.winrm:
            return self.shell.exec_cmd(cmd_str)

        # Write the shim to a temporary file in the default temp directory
        with tempfile.NamedTemporaryFile(mode=u'w+b',
                                         prefix=u'shim_',
                                         delete=False) as shim_tmp_file:
            shim_tmp_file.write(salt.utils.stringutils.to_bytes(cmd_str))

        # Copy shim to target system, under $HOME/.<randomized name>
        target_shim_file = u'.{0}.{1}'.format(binascii.hexlify(os.urandom(6)), extension)
        if self.winrm:
            target_shim_file = saltwinshell.get_target_shim_file(self, target_shim_file)
        self.shell.send(shim_tmp_file.name, target_shim_file, makedirs=True)

        # Remove our shim file
        try:
            os.remove(shim_tmp_file.name)
        except IOError:
            pass

        # Execute shim
        if extension == u'ps1':
            ret = self.shell.exec_cmd(u'"powershell {0}"'.format(target_shim_file))
        else:
            if not self.winrm:
                ret = self.shell.exec_cmd(u'/bin/sh \'$HOME/{0}\''.format(target_shim_file))
            else:
                ret = saltwinshell.call_python(self, target_shim_file)

        # Remove shim from target system
        if not self.winrm:
            self.shell.exec_cmd(u'rm \'$HOME/{0}\''.format(target_shim_file))
        else:
            self.shell.exec_cmd(u'del {0}'.format(target_shim_file))

        return ret

    def cmd_block(self, is_retry=False):
        '''
        Prepare the pre-check command to send to the subsystem

        1. execute SHIM + command
        2. check if SHIM returns a master request or if it completed
        3. handle any master request
        4. re-execute SHIM + command
        5. split SHIM results from command results
        6. return command results
        '''
        self.argv = _convert_args(self.argv)
        log.debug(
            u'Performing shimmed, blocking command as follows:\n%s',
            u' '.join(self.argv)
        )
        cmd_str = self._cmd_str()
        stdout, stderr, retcode = self.shim_cmd(cmd_str)

        log.trace(u'STDOUT %s\n%s', self.target[u'host'], stdout)
        log.trace(u'STDERR %s\n%s', self.target[u'host'], stderr)
        log.debug(u'RETCODE %s: %s', self.target[u'host'], retcode)

        error = self.categorize_shim_errors(stdout, stderr, retcode)
        if error:
            if error == u'Python environment not found on Windows system':
                saltwinshell.deploy_python(self)
                stdout, stderr, retcode = self.shim_cmd(cmd_str)
                while re.search(RSTR_RE, stdout):
                    stdout = re.split(RSTR_RE, stdout, 1)[1].strip()
                while re.search(RSTR_RE, stderr):
                    stderr = re.split(RSTR_RE, stderr, 1)[1].strip()
            elif error == u'Undefined SHIM state':
                self.deploy()
                stdout, stderr, retcode = self.shim_cmd(cmd_str)
                if not re.search(RSTR_RE, stdout) or not re.search(RSTR_RE, stderr):
                    # If RSTR is not seen in both stdout and stderr then there
                    # was a thin deployment problem.
                    return u'ERROR: Failure deploying thin, undefined state: {0}'.format(stdout), stderr, retcode
                while re.search(RSTR_RE, stdout):
                    stdout = re.split(RSTR_RE, stdout, 1)[1].strip()
                while re.search(RSTR_RE, stderr):
                    stderr = re.split(RSTR_RE, stderr, 1)[1].strip()
            else:
                return u'ERROR: {0}'.format(error), stderr, retcode

        # FIXME: this discards output from ssh_shim if the shim succeeds.  It should
        # always save the shim output regardless of shim success or failure.
        while re.search(RSTR_RE, stdout):
            stdout = re.split(RSTR_RE, stdout, 1)[1].strip()

        if re.search(RSTR_RE, stderr):
            # Found RSTR in stderr which means SHIM completed and only
            # and remaining output is only from salt.
            while re.search(RSTR_RE, stderr):
                stderr = re.split(RSTR_RE, stderr, 1)[1].strip()

        else:
            # RSTR was found in stdout but not stderr - which means there
            # is a SHIM command for the master.
            shim_command = re.split(sdecode(r'\r?\n'), stdout, 1)[0].strip()  # future lint: disable=non-unicode-string
            log.debug(u'SHIM retcode(%s) and command: %s', retcode, shim_command)
            if u'deploy' == shim_command and retcode == salt.defaults.exitcodes.EX_THIN_DEPLOY:
                self.deploy()
                stdout, stderr, retcode = self.shim_cmd(cmd_str)
                if not re.search(RSTR_RE, stdout) or not re.search(RSTR_RE, stderr):
                    if not self.tty:
                        # If RSTR is not seen in both stdout and stderr then there
                        # was a thin deployment problem.
                        log.error(u'ERROR: Failure deploying thin, retrying: %s\n%s', stdout, stderr)
                        return self.cmd_block()
                    elif not re.search(RSTR_RE, stdout):
                        # If RSTR is not seen in stdout with tty, then there
                        # was a thin deployment problem.
                        log.error(u'ERROR: Failure deploying thin, retrying: %s\n%s', stdout, stderr)
                while re.search(RSTR_RE, stdout):
                    stdout = re.split(RSTR_RE, stdout, 1)[1].strip()
                if self.tty:
                    stderr = u''
                else:
                    while re.search(RSTR_RE, stderr):
                        stderr = re.split(RSTR_RE, stderr, 1)[1].strip()
            elif u'ext_mods' == shim_command:
                self.deploy_ext()
                stdout, stderr, retcode = self.shim_cmd(cmd_str)
                if not re.search(RSTR_RE, stdout) or not re.search(RSTR_RE, stderr):
                    # If RSTR is not seen in both stdout and stderr then there
                    # was a thin deployment problem.
                    return u'ERROR: Failure deploying ext_mods: {0}'.format(stdout), stderr, retcode
                while re.search(RSTR_RE, stdout):
                    stdout = re.split(RSTR_RE, stdout, 1)[1].strip()
                while re.search(RSTR_RE, stderr):
                    stderr = re.split(RSTR_RE, stderr, 1)[1].strip()

        return stdout, stderr, retcode

    def categorize_shim_errors(self, stdout, stderr, retcode):
        if re.search(RSTR_RE, stdout) and stdout != RSTR+u'\n':
            # RSTR was found in stdout which means that the shim
            # functioned without *errors* . . . but there may be shim
            # commands, unless the only thing we found is RSTR
            return None

        if re.search(RSTR_RE, stderr):
            # Undefined state
            return u'Undefined SHIM state'

        if stderr.startswith(u'Permission denied'):
            # SHIM was not even reached
            return None

        perm_error_fmt = u'Permissions problem, target user may need '\
                         u'to be root or use sudo:\n {0}'

        errors = [
            (
                (),
                u'sudo: no tty present and no askpass program specified',
                u'sudo expected a password, NOPASSWD required'
            ),
            (
                (salt.defaults.exitcodes.EX_THIN_PYTHON_INVALID,),
                u'Python interpreter is too old',
                u'salt requires python 2.6 or newer on target hosts, must have same major version as origin host'
            ),
            (
                (salt.defaults.exitcodes.EX_THIN_CHECKSUM,),
                u'checksum mismatched',
                u'The salt thin transfer was corrupted'
            ),
            (
                (salt.defaults.exitcodes.EX_SCP_NOT_FOUND,),
                u'scp not found',
                u'No scp binary. openssh-clients package required'
            ),
            (
                (salt.defaults.exitcodes.EX_CANTCREAT,),
                u'salt path .* exists but is not a directory',
                u'A necessary path for salt thin unexpectedly exists:\n ' + stderr,
            ),
            (
                (),
                u'sudo: sorry, you must have a tty to run sudo',
                u'sudo is configured with requiretty'
            ),
            (
                (),
                u'Failed to open log file',
                perm_error_fmt.format(stderr)
            ),
            (
                (),
                u'Permission denied:.*/salt',
                perm_error_fmt.format(stderr)
            ),
            (
                (),
                u'Failed to create directory path.*/salt',
                perm_error_fmt.format(stderr)
            ),
            (
                (salt.defaults.exitcodes.EX_SOFTWARE,),
                u'exists but is not',
                u'An internal error occurred with the shim, please investigate:\n ' + stderr,
            ),
            (
                (),
                u'The system cannot find the path specified',
                u'Python environment not found on Windows system',
            ),
            (
                (),
                u'is not recognized',
                u'Python environment not found on Windows system',
            ),
        ]

        for error in errors:
            if retcode in error[0] or re.search(error[1], stderr):
                return error[2]
        return None

    def check_refresh(self, data, ret):
        '''
        Stub out check_refresh
        '''
        return

    def module_refresh(self):
        '''
        Module refresh is not needed, stub it out
        '''
        return


def lowstate_file_refs(chunks):
    '''
    Create a list of file ref objects to reconcile
    '''
    refs = {}
    for chunk in chunks:
        saltenv = u'base'
        crefs = []
        for state in chunk:
            if state == u'__env__':
                saltenv = chunk[state]
            elif state == u'saltenv':
                saltenv = chunk[state]
            elif state.startswith(u'__'):
                continue
            crefs.extend(salt_refs(chunk[state]))
        if crefs:
            if saltenv not in refs:
                refs[saltenv] = []
            refs[saltenv].append(crefs)
    return refs


def salt_refs(data):
    '''
    Pull salt file references out of the states
    '''
    proto = u'salt://'
    ret = []
    if isinstance(data, six.string_types):
        if data.startswith(proto):
            return [data]
    if isinstance(data, list):
        for comp in data:
            if isinstance(comp, six.string_types):
                if comp.startswith(proto):
                    ret.append(comp)
    return ret


def mod_data(fsclient):
    '''
    Generate the module arguments for the shim data
    '''
    # TODO, change out for a fileserver backend
    sync_refs = [
            u'modules',
            u'states',
            u'grains',
            u'renderers',
            u'returners',
            ]
    ret = {}
    envs = fsclient.envs()
    ver_base = u''
    for env in envs:
        files = fsclient.file_list(env)
        for ref in sync_refs:
            mods_data = {}
            pref = u'_{0}'.format(ref)
            for fn_ in sorted(files):
                if fn_.startswith(pref):
                    if fn_.endswith((u'.py', u'.so', u'.pyx')):
                        full = salt.utils.url.create(fn_)
                        mod_path = fsclient.cache_file(full, env)
                        if not os.path.isfile(mod_path):
                            continue
                        mods_data[os.path.basename(fn_)] = mod_path
                        chunk = salt.utils.get_hash(mod_path)
                        ver_base += chunk
            if mods_data:
                if ref in ret:
                    ret[ref].update(mods_data)
                else:
                    ret[ref] = mods_data
    if not ret:
        return {}

    if six.PY3:
        ver_base = salt.utils.stringutils.to_bytes(ver_base)

    ver = hashlib.sha1(ver_base).hexdigest()
    ext_tar_path = os.path.join(
            fsclient.opts[u'cachedir'],
            u'ext_mods.{0}.tgz'.format(ver))
    mods = {u'version': ver,
            u'file': ext_tar_path}
    if os.path.isfile(ext_tar_path):
        return mods
    tfp = tarfile.open(ext_tar_path, u'w:gz')
    verfile = os.path.join(fsclient.opts[u'cachedir'], u'ext_mods.ver')
    with salt.utils.files.fopen(verfile, u'w+') as fp_:
        fp_.write(ver)
    tfp.add(verfile, u'ext_version')
    for ref in ret:
        for fn_ in ret[ref]:
            tfp.add(ret[ref][fn_], os.path.join(ref, fn_))
    tfp.close()
    return mods


def ssh_version():
    '''
    Returns the version of the installed ssh command
    '''
    # This function needs more granular checks and to be validated against
    # older versions of ssh
    ret = subprocess.Popen(
            [u'ssh', u'-V'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE).communicate()
    try:
        version_parts = ret[1].split(b',')[0].split(b'_')[1]  # future lint: disable=non-unicode-string
        parts = []
        for part in version_parts:
            try:
                parts.append(int(part))
            except ValueError:
                return tuple(parts)
        return tuple(parts)
    except IndexError:
        return (2, 0)


def _convert_args(args):
    '''
    Take a list of args, and convert any dicts inside the list to keyword
    args in the form of `key=value`, ready to be passed to salt-ssh
    '''
    converted = []
    for arg in args:
        if isinstance(arg, dict):
            for key in list(arg.keys()):
                if key == u'__kwarg__':
                    continue
                converted.append(u'{0}={1}'.format(key, arg[key]))
        else:
            converted.append(arg)
    return converted
