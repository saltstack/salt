# -*- coding: utf-8 -*-
'''
Execute puppet routines
'''

# Import python libs
from __future__ import absolute_import
import logging
import os
import datetime

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
import yaml
import salt.ext.six as six
from salt.ext.six.moves import range
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if puppet is installed
    '''
    if salt.utils.which('facter'):
        return 'puppet'
    return False


def _check_puppet():
    '''
    Checks if puppet is installed
    '''
    # I thought about making this a virtual module, but then I realized that I
    # would require the minion to restart if puppet was installed after the
    # minion was started, and that would be rubbish
    salt.utils.check_or_die('puppet')


def _check_facter():
    '''
    Checks if facter is installed
    '''
    salt.utils.check_or_die('facter')


def _format_fact(output):
    try:
        fact, value = output.split(' => ', 1)
        value = value.strip()
    except ValueError:
        fact = None
        value = None
    return (fact, value)


class _Puppet(object):
    '''
    Puppet helper class. Used to format command for execution.
    '''
    def __init__(self):
        '''
        Setup a puppet instance, based on the premis that default usage is to
        run 'puppet agent --test'. Configuration and run states are stored in
        the default locations.
        '''
        self.subcmd = 'agent'
        self.subcmd_args = []  # e.g. /a/b/manifest.pp

        self.kwargs = {'color': 'false'}       # e.g. --tags=apache::server
        self.args = []         # e.g. --noop

        if salt.utils.is_windows():
            self.vardir = 'C:\\ProgramData\\PuppetLabs\\puppet\\var'
            self.rundir = 'C:\\ProgramData\\PuppetLabs\\puppet\\run'
            self.confdir = 'C:\\ProgramData\\PuppetLabs\\puppet\\etc'
        else:
            if 'Enterprise' in __salt__['cmd.run']('puppet --version'):
                self.vardir = '/var/opt/lib/pe-puppet'
                self.rundir = '/var/opt/run/pe-puppet'
                self.confdir = '/etc/puppetlabs/puppet'
            else:
                self.vardir = '/var/lib/puppet'
                self.rundir = '/var/run/puppet'
                self.confdir = '/etc/puppet'

        self.disabled_lockfile = self.vardir + '/state/agent_disabled.lock'
        self.run_lockfile = self.vardir + '/state/agent_catalog_run.lock'
        self.agent_pidfile = self.rundir + '/agent.pid'
        self.lastrunfile = self.vardir + '/state/last_run_summary.yaml'

    def __repr__(self):
        '''
        Format the command string to executed using cmd.run_all.
        '''

        cmd = 'puppet {subcmd} --vardir {vardir} --confdir {confdir}'.format(
            **self.__dict__
        )

        args = ' '.join(self.subcmd_args)
        args += ''.join(
            [' --{0}'.format(k) for k in self.args]  # single spaces
        )
        args += ''.join([
            ' --{0} {1}'.format(k, v) for k, v in six.iteritems(self.kwargs)]
        )

        return '{0} {1}'.format(cmd, args)

    def arguments(self, args=None):
        '''
        Read in arguments for the current subcommand. These are added to the
        cmd line without '--' appended. Any others are redirected as standard
        options with the double hyphen prefixed.
        '''
        # permits deleting elements rather than using slices
        args = args and list(args) or []

        # match against all known/supported subcmds
        if self.subcmd == 'apply':
            # apply subcommand requires a manifest file to execute
            self.subcmd_args = [args[0]]
            del args[0]

        if self.subcmd == 'agent':
            # no arguments are required
            args.extend([
                'test'
            ])

        # finally do this after subcmd has been matched for all remaining args
        self.args = args


def run(*args, **kwargs):
    '''
    Execute a puppet run and return a dict with the stderr, stdout,
    return code, etc. The first positional argument given is checked as a
    subcommand. Following positional arguments should be ordered with arguments
    required by the subcommand first, followed by non-keyword arguments.
    Tags are specified by a tag keyword and comma separated list of values. --
    http://docs.puppetlabs.com/puppet/latest/reference/lang_tags.html

    CLI Examples:

    .. code-block:: bash

        salt '*' puppet.run
        salt '*' puppet.run tags=basefiles::edit,apache::server
        salt '*' puppet.run agent onetime no-daemonize no-usecacheonfailure no-splay ignorecache
        salt '*' puppet.run debug
        salt '*' puppet.run apply /a/b/manifest.pp modulepath=/a/b/modules tags=basefiles::edit,apache::server
    '''
    _check_puppet()
    puppet = _Puppet()

    # new args tuple to filter out agent/apply for _Puppet.arguments()
    buildargs = ()
    for arg in range(len(args)):
        # based on puppet documentation action must come first. making the same
        # assertion. need to ensure the list of supported cmds here matches
        # those defined in _Puppet.arguments()
        if args[arg] in ['agent', 'apply']:
            puppet.subcmd = args[arg]
        else:
            buildargs += (args[arg],)
    # args will exist as an empty list even if none have been provided
    puppet.arguments(buildargs)

    puppet.kwargs.update(salt.utils.clean_kwargs(**kwargs))

    ret = __salt__['cmd.run_all'](repr(puppet), python_shell=False)
    if ret['retcode'] in [0, 2]:
        ret['retcode'] = 0
    else:
        ret['retcode'] = 1

    return ret


def noop(*args, **kwargs):
    '''
    Execute a puppet noop run and return a dict with the stderr, stdout,
    return code, etc. Usage is the same as for puppet.run.

    CLI Example:

    .. code-block:: bash

        salt '*' puppet.noop
        salt '*' puppet.noop tags=basefiles::edit,apache::server
        salt '*' puppet.noop debug
        salt '*' puppet.noop apply /a/b/manifest.pp modulepath=/a/b/modules tags=basefiles::edit,apache::server
    '''
    args += ('noop',)
    return run(*args, **kwargs)


def enable():
    '''
    .. versionadded:: 2014.7.0

    Enable the puppet agent

    CLI Example:

    .. code-block:: bash

        salt '*' puppet.enable
    '''

    _check_puppet()
    puppet = _Puppet()

    if os.path.isfile(puppet.disabled_lockfile):
        try:
            os.remove(puppet.disabled_lockfile)
        except (IOError, OSError) as exc:
            msg = 'Failed to enable: {0}'.format(exc)
            log.error(msg)
            raise CommandExecutionError(msg)
        else:
            return True
    return False


def disable(message=None):
    '''
    .. versionadded:: 2014.7.0

    Disable the puppet agent

    message
        .. versionadded:: 2015.5.2

        Disable message to send to puppet

    CLI Example:

    .. code-block:: bash

        salt '*' puppet.disable
        salt '*' puppet.disable 'Disabled, contact XYZ before enabling'
    '''

    _check_puppet()
    puppet = _Puppet()

    if os.path.isfile(puppet.disabled_lockfile):
        return False
    else:
        with salt.utils.fopen(puppet.disabled_lockfile, 'w') as lockfile:
            try:
                # Puppet chokes when no valid json is found
                str = '{{"disabled_message":"{0}"}}'.format(message) if message is not None else '{}'
                lockfile.write(str)
                lockfile.close()
                return True
            except (IOError, OSError) as exc:
                msg = 'Failed to disable: {0}'.format(exc)
                log.error(msg)
                raise CommandExecutionError(msg)


def status():
    '''
    .. versionadded:: 2014.7.0

    Display puppet agent status

    CLI Example:

    .. code-block:: bash

        salt '*' puppet.status
    '''
    _check_puppet()
    puppet = _Puppet()

    if os.path.isfile(puppet.disabled_lockfile):
        return 'Administratively disabled'

    if os.path.isfile(puppet.run_lockfile):
        try:
            with salt.utils.fopen(puppet.run_lockfile, 'r') as fp_:
                pid = int(fp_.read())
                os.kill(pid, 0)  # raise an OSError if process doesn't exist
        except (OSError, ValueError):
            return 'Stale lockfile'
        else:
            return 'Applying a catalog'

    if os.path.isfile(puppet.agent_pidfile):
        try:
            with salt.utils.fopen(puppet.agent_pidfile, 'r') as fp_:
                pid = int(fp_.read())
                os.kill(pid, 0)  # raise an OSError if process doesn't exist
        except (OSError, ValueError):
            return 'Stale pidfile'
        else:
            return 'Idle daemon'

    return 'Stopped'


def summary():
    '''
    .. versionadded:: 2014.7.0

    Show a summary of the last puppet agent run

    CLI Example:

    .. code-block:: bash

        salt '*' puppet.summary
    '''

    _check_puppet()
    puppet = _Puppet()

    try:
        with salt.utils.fopen(puppet.lastrunfile, 'r') as fp_:
            report = yaml.safe_load(fp_.read())
        result = {}

        if 'time' in report:
            try:
                result['last_run'] = datetime.datetime.fromtimestamp(
                    int(report['time']['last_run'])).isoformat()
            except (TypeError, ValueError, KeyError):
                result['last_run'] = 'invalid or missing timestamp'

            result['time'] = {}
            for key in ('total', 'config_retrieval'):
                if key in report['time']:
                    result['time'][key] = report['time'][key]

        if 'resources' in report:
            result['resources'] = report['resources']

    except yaml.YAMLError as exc:
        raise CommandExecutionError(
            'YAML error parsing puppet run summary: {0}'.format(exc)
        )
    except IOError as exc:
        raise CommandExecutionError(
            'Unable to read puppet run summary: {0}'.format(exc)
        )

    return result


def plugin_sync():
    '''
    Runs a plugin synch between the puppet master and agent

    CLI Example:
    .. code-block:: bash

        salt '*' puppet.plugin_sync
    '''

    _check_puppet()

    ret = __salt__['cmd.run']('puppet plugin download')

    if not ret:
        return ''
    return ret


def facts(puppet=False):
    '''
    Run facter and return the results

    CLI Example:

    .. code-block:: bash

        salt '*' puppet.facts
    '''
    _check_facter()

    ret = {}
    opt_puppet = '--puppet' if puppet else ''
    output = __salt__['cmd.run']('facter {0}'.format(opt_puppet))

    # Loop over the facter output and  properly
    # parse it into a nice dictionary for using
    # elsewhere
    for line in output.splitlines():
        if not line:
            continue
        fact, value = _format_fact(line)
        if not fact:
            continue
        ret[fact] = value
    return ret


def fact(name, puppet=False):
    '''
    Run facter for a specific fact

    CLI Example:

    .. code-block:: bash

        salt '*' puppet.fact kernel
    '''
    _check_facter()

    opt_puppet = '--puppet' if puppet else ''
    ret = __salt__['cmd.run'](
            'facter {0} {1}'.format(opt_puppet, name),
            python_shell=False)
    if not ret:
        return ''
    return ret
