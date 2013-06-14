'''
Execute puppet routines
'''

# Import salt libs
import salt.utils


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
        self.subcmd_args = []  # eg. /a/b/manifest.pp

        self.kwargs = {'color': 'false'}       # eg. --tags=apache::server
        self.args = []         # eg. --noop

        self.vardir = '/var/lib/puppet'
        self.confdir = '/etc/puppet'
        if 'Enterprise' in __salt__['cmd.run']('puppet --version'):
            self.vardir = '/var/opt/lib/pe-puppet'
            self.confdir = '/etc/puppetlabs/puppet'

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
            ' --{0} {1}'.format(k, v) for k, v in self.kwargs.items()]
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
                'onetime', 'verbose', 'ignorecache', 'no-daemonize',
                'no-usecacheonfailure', 'no-splay', 'show_diff'
            ])

        # finally do this after subcmd has been matched for all remaining args
        self.args = args


def run(*args, **kwargs):
    '''
    Execute a puppet run and return a dict with the stderr, stdout,
    return code, etc. The first positional argument given is checked as a
    subcommand. Following positional arguments should be ordered with arguments
    required by the subcommand first, followed by non-keyvalue pair options.
    Tags are specified by a tag keyword and comma separated list of values. --
    http://projects.puppetlabs.com/projects/1/wiki/Using_Tags

    CLI Examples::

        salt '*' puppet.run

        salt '*' puppet.run tags=basefiles::edit,apache::server

        salt '*' puppet.run debug

        salt '*' puppet.run apply /a/b/manifest.pp modulepath=/a/b/modules tags=basefiles::edit,apache::server
    '''
    _check_puppet()
    puppet = _Puppet()

    if args:
        # based on puppet documentation action must come first. making the same
        # assertion. need to ensure the list of supported cmds here matches
        # those defined in _Puppet.arguments()
        if args[0] in ['agent', 'apply']:
            puppet.subcmd = args[0]
            puppet.arguments(args[1:])
    else:
        # args will exist as an empty list even if none have been provided
        puppet.arguments(args)

    puppet.kwargs.update(salt.utils.clean_kwargs(**kwargs))

    return __salt__['cmd.run_all'](repr(puppet))


def noop(*args, **kwargs):
    '''
    Execute a puppet noop run and return a dict with the stderr, stdout,
    return code, etc. Usage is the same as for puppet.run.

    CLI Example::

        salt '*' puppet.noop

        salt '*' puppet.noop tags=basefiles::edit,apache::server

        salt '*' puppet.noop debug

        salt '*' puppet.noop apply /a/b/manifest.pp modulepath=/a/b/modules tags=basefiles::edit,apache::server
    '''
    args += ('noop',)
    return run(*args, **kwargs)


def facts():
    '''
    Run facter and return the results

    CLI Example::

        salt '*' puppet.facts
    '''
    _check_facter()

    ret = {}
    output = __salt__['cmd.run']('facter')

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


def fact(name):
    '''
    Run facter for a specific fact

    CLI Example::

        salt '*' puppet.fact kernel
    '''
    _check_facter()

    ret = __salt__['cmd.run']('facter {0}'.format(name))
    if not ret:
        return ''
    return ret
