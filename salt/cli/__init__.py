'''
The management of salt command line utilities are stored in here
'''

# Import python libs
import optparse
import os
import sys

# Import salt components
import salt.cli.caller
import salt.cli.cp
import salt.cli.key
import salt.cli.batch
import salt.client
import salt.output
import salt.runner

from salt.utils.verify import verify_env
from salt import __version__ as VERSION
from salt.exceptions import SaltInvocationError, SaltClientError, \
    SaltException


class SaltCMD(object):
    '''
    The execution of a salt command happens here
    '''
    def __init__(self):
        '''
        Create a SaltCMD object
        '''
        self.opts = self.__parse()

    def __parse(self):
        '''
        Parse the command line
        '''
        usage = "%prog [options] '<target>' <function> [arguments]"
        parser = optparse.OptionParser(version="%%prog %s" % VERSION, usage=usage)

        parser.add_option('-t',
                '--timeout',
                default=None,
                dest='timeout',
                help=('Set the return timeout for batch jobs; '
                      'default=5 seconds'))
        parser.add_option('-s',
                '--static',
                default=False,
                dest='static',
                action='store_true',
                help=('Return the data from minions as a group after they '
                      'all return.'))
        parser.add_option('-v',
                '--verbose',
                default=False,
                dest='verbose',
                action='store_true',
                help=('Turn on command verbosity, display jid and active job '
                     'queries'))
        parser.add_option('-b',
                '--batch',
                '--batch-size',
                default='',
                dest='batch',
                help=('Execute the salt job in batch mode, pass either the '
                      'number of minions to batch at a time, or the '
                      'percentage of minions to have running'))
        parser.add_option('-E',
                '--pcre',
                default=False,
                dest='pcre',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'servers, use pcre regular expressions'))
        parser.add_option('-L',
                '--list',
                default=False,
                dest='list',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'servers, take a comma delimited list of servers.'))
        parser.add_option('-G',
                '--grain',
                default=False,
                dest='grain',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'use a grain value to identify targets, the syntax '
                      'for the target is the grain key followed by a glob'
                      'expression:\n"os:Arch*"'))
        parser.add_option('--grain-pcre',
                default=False,
                dest='grain_pcre',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'use a grain value to identify targets, the syntax '
                      'for the target is the grain key followed by a pcre '
                      'regular expression:\n"os:Arch.*"'))
        parser.add_option('-X',
                '--exsel',
                default=False,
                dest='exsel',
                action='store_true',
                help=('Instead of using shell globs use the return code '
                      'of a function.'))
        parser.add_option('-I',
                '--pillar',
                default=False,
                dest='pillar',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'use a pillar value to identify targets, the syntax '
                      'for the target is the pillar key followed by a glob'
                      'expression:\n"role:production*"'))
        parser.add_option('-N',
                '--nodegroup',
                default=False,
                dest='nodegroup',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'use one of the predefined nodegroups to identify a '
                      'list of targets.'))
        parser.add_option('-R',
                '--range',
                default=False,
                dest='range',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'use a range expression to identify targets. '
                      'Range expressions look like %cluster'))
        parser.add_option('-C',
                '--compound',
                default=False,
                dest='compound',
                action='store_true',
                help=('The compound target option allows for multiple '
                       'target types to be evaluated, allowing for greater '
                       'granularity in target matching. The compound target '
                       'is space delimited, targets other than globs are '
                       'preceted with an identifyer matching the specific '
                       'targets argument type: salt \'G@os:RedHat and '
                       'webser* or E@database.*\''))
        parser.add_option('--return',
                default='',
                dest='return',
                metavar='RETURNER',
                help=('Set an alternative return method. By default salt will '
                      'send the return data from the command back to the '
                      'master, but the return data can be redirected into '
                      'any number of systems, databases or applications.'))
        parser.add_option('-Q',
                '--query',
                dest='query',
                action='store_true',
                help=('This option is deprecated and will be removed in a '
                      'future release, please use salt-run jobs instead\n'
                      'Execute a salt command query, this can be used to find '
                      'the results os a previous function call: -Q test.echo'))
        parser.add_option('-c',
                '--config',
                default='/etc/salt/master',
                dest='conf_file',
                help=('The location of the salt master configuration file, '
                      'the salt master settings are required to know where '
                      'the connections are; default=/etc/salt/master'))
        parser.add_option('--raw-out',
                default=False,
                action='store_true',
                dest='raw_out',
                help=('Print the output from the salt command in raw python '
                      'form, this is suitable for re-reading the output into '
                      'an executing python script with eval.'))
        parser.add_option('--text-out',
                default=False,
                action='store_true',
                dest='txt_out',
                help=('Print the output from the salt command in the same '
                      'form the shell would.'))
        parser.add_option('--yaml-out',
                default=False,
                action='store_true',
                dest='yaml_out',
                help='Print the output from the salt command in yaml.')
        parser.add_option('--json-out',
                default=False,
                action='store_true',
                dest='json_out',
                help='Print the output from the salt command in json.')
        parser.add_option('--no-color',
                default=False,
                action='store_true',
                dest='no_color',
                help='Disable all colored output')

        options, args = parser.parse_args()

        opts = {}

        for k, v in options.__dict__.items():
            if v is not None:
                opts[k] = v

        if not options.timeout is None:
            opts['timeout'] = int(options.timeout)

        if options.query:
            opts['query'] = options.query
            if len(args) < 1:
                err = ('Please pass in a command to query the old salt '
                       'calls for.')
                sys.stderr.write(err + '\n')
                sys.exit('2')
            opts['cmd'] = args[0]
        else:
            # Catch invalid invocations of salt such as: salt run
            if len(args) <= 1:
                parser.print_help()
                parser.exit(1)

            if opts['list']:
                opts['tgt'] = args[0].split(',')
            else:
                opts['tgt'] = args[0]

            # Detect compound command and set up the data for it
            if ',' in args[1]:
                opts['fun'] = args[1].split(',')
                opts['arg'] = []
                for comp in ' '.join(args[2:]).split(','):
                    opts['arg'].append(comp.split())
                if len(opts['fun']) != len(opts['arg']):
                    err = ('Cannot execute compound command without defining '
                           'all arguments.')
                    sys.stderr.write(err + '\n')
                    sys.exit(42)
            else:
                opts['fun'] = args[1]
                opts['arg'] = args[2:]

        return opts

    def run(self):
        '''
        Execute the salt command line
        '''
        try:
            local = salt.client.LocalClient(self.opts['conf_file'])
        except SaltClientError as exc:
            sys.stderr.write('{0}\n'.format(exc))
            sys.exit(2)
            return

        if 'query' in self.opts:
            ret = local.find_cmd(self.opts['cmd'])
            for jid in ret:
                if isinstance(ret, list) or isinstance(ret, dict):
                    # Determine the proper output method and run it
                    get_outputter = salt.output.get_outputter
                    if self.opts['raw_out']:
                        printout = get_outputter('raw')
                    elif self.opts['json_out']:
                        printout = get_outputter('json')
                    elif self.opts['txt_out']:
                        printout = get_outputter('txt')
                    elif self.opts['yaml_out']:
                        printout = get_outputter('yaml')
                    else:
                        printout = get_outputter(None)

                    print('Return data for job {0}:'.format(jid))
                    printout(ret[jid])
                    print('')
        elif self.opts['batch']:
            batch = salt.cli.batch.Batch(self.opts)
            batch.run()
        else:
            if not 'timeout' in self.opts:
                self.opts['timeout'] = local.opts['timeout']
            args = [self.opts['tgt'],
                    self.opts['fun'],
                    self.opts['arg'],
                    self.opts['timeout'],
                    ]
            if self.opts['pcre']:
                args.append('pcre')
            elif self.opts['list']:
                args.append('list')
            elif self.opts['grain']:
                args.append('grain')
            elif self.opts['grain_pcre']:
                args.append('grain_pcre')
            elif self.opts['exsel']:
                args.append('exsel')
            elif self.opts['pillar']:
                args.append('pillar')
            elif self.opts['nodegroup']:
                args.append('nodegroup')
            elif self.opts['range']:
                args.append('range')
            elif self.opts['compound']:
                args.append('compound')
            else:
                args.append('glob')

            if self.opts['return']:
                args.append(self.opts['return'])
            else:
                args.append('')
            try:
                # local will be None when there was an error
                if local:
                    if self.opts['static']:
                        full_ret = local.cmd_full_return(*args)
                        ret, out = self._format_ret(full_ret)
                        self._output_ret(ret, out)
                    elif self.opts['fun'] == 'sys.doc':
                        ret = {}
                        out = ''
                        for full_ret in local.cmd_cli(*args):
                            ret_, out = self._format_ret(full_ret)
                            ret.update(ret_)
                        self._output_ret(ret, out)
                    else:
                        if self.opts['verbose']:
                            args.append(True)
                        for full_ret in local.cmd_cli(*args):
                            ret, out = self._format_ret(full_ret)
                            self._output_ret(ret, out)
            except SaltInvocationError as exc:
                ret = exc
                out = ''

    def _output_ret(self, ret, out):
        '''
        Print the output from a single return to the terminal
        '''
        # Handle special case commands
        if self.opts['fun'] == 'sys.doc':
            self._print_docs(ret)
        else:
            # Determine the proper output method and run it
            get_outputter = salt.output.get_outputter
            if isinstance(ret, list) or isinstance(ret, dict):
                if self.opts['raw_out']:
                    printout = get_outputter('raw')
                elif self.opts['json_out']:
                    printout = get_outputter('json')
                elif self.opts['txt_out']:
                    printout = get_outputter('txt')
                elif self.opts['yaml_out']:
                    printout = get_outputter('yaml')
                elif out:
                    printout = get_outputter(out)
                else:
                    printout = get_outputter(None)
            # Pretty print any salt exceptions
            elif isinstance(ret, SaltException):
                printout = get_outputter("txt")
            color = not bool(self.opts['no_color'])
            printout(ret, color=color)

    def _format_ret(self, full_ret):
        '''
        Take the full return data and format it to simple output
        '''
        ret = {}
        out = ''
        for key, data in full_ret.items():
            ret[key] = data['ret']
            if 'out' in data:
                out = data['out']
        return ret, out

    def _print_docs(self, ret):
        '''
        Print out the docstrings for all of the functions on the minions
        '''
        docs = {}
        if not ret:
            sys.stderr.write('No minions found to gather docs from\n')
        for host in ret:
            for fun in ret[host]:
                if fun not in docs:
                    if ret[host][fun]:
                        docs[fun] = ret[host][fun]
        for fun in sorted(docs):
            print(fun + ':')
            print(docs[fun])
            print('')


class SaltCP(object):
    '''
    Run the salt-cp command line client
    '''
    def __init__(self):
        self.opts = self.__parse()

    def __parse(self):
        '''
        Parse the command line
        '''
        usage = "%prog [options] '<target>' SOURCE DEST"
        parser = optparse.OptionParser(version="%%prog %s" % VERSION, usage=usage)

        parser.add_option('-t',
                '--timeout',
                default=5,
                type=int,
                dest='timeout',
                help=('Set the return timeout for batch jobs; '
                      'default=5 seconds'))
        parser.add_option('-E',
                '--pcre',
                default=False,
                dest='pcre',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'servers, use pcre regular expressions'))
        parser.add_option('-L',
                '--list',
                default=False,
                dest='list',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'servers, take a comma delimited list of servers.'))
        parser.add_option('-G',
                '--grain',
                default=False,
                dest='grain',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'use a grain value to identify targets, the syntax '
                      'for the target is the grain key followed by a glob'
                      'expression:\n"os:Arch*"'))
        parser.add_option('--grain-pcre',
                default=False,
                dest='grain_pcre',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'use a grain value to identify targets, the syntax '
                      'for the target is the grain key followed by a pcre '
                      'regular expression:\n"os:Arch.*"'))
        parser.add_option('-N',
                '--nodegroup',
                default=False,
                dest='nodegroup',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'use one of the predefined nodegroups to identify a '
                      'list of targets.'))
        parser.add_option('-R',
                '--range',
                default=False,
                dest='range',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'use a range expressions to identify targets. '
                      'Range expressions look like %cluster'))
        parser.add_option('-c',
                '--config',
                default='/etc/salt/master',
                dest='conf_file',
                help=('The location of the salt master configuration file, '
                      'the salt master settings are required to know where '
                      'the connections are; default=/etc/salt/master'))

        options, args = parser.parse_args()

        opts = {}

        for k, v in options.__dict__.items():
            if v is not None:
                opts[k] = v

        # salt-cp needs arguments
        if len(args) <= 1:
            parser.print_help()
            parser.exit(1)

        if opts['list']:
            opts['tgt'] = args[0].split(',')
        else:
            opts['tgt'] = args[0]
        opts['src'] = args[1:-1]
        opts['dest'] = args[-1]

        return opts

    def run(self):
        '''
        Execute salt-cp
        '''
        cp_ = salt.cli.cp.SaltCP(self.opts)
        cp_.run()


class SaltKey(object):
    '''
    Initialize the Salt key manager
    '''
    def __init__(self):
        self.opts = self.__parse()

    def __parse(self):
        '''
        Parse the command line options for the salt key
        '''
        parser = optparse.OptionParser(version="%%prog %s" % VERSION)

        parser.add_option('-l',
                '--list',
                dest='list',
                default='',
                help=('List the public keys. Takes the args: '
                      '"pre", "un", "unaccepted": Unaccepted/unsigned keys '
                      '"acc", "accepted": Accepted/signed keys '
                      '"rej", "rejected": Rejected keys '
                      '"all": all keys'))

        parser.add_option('-L',
                '--list-all',
                dest='list_all',
                default=False,
                action='store_true',
                help='List all public keys.  Deprecated: use "--list all"')

        parser.add_option('-a',
                '--accept',
                dest='accept',
                default='',
                help='Accept the following key')

        parser.add_option('-A',
                '--accept-all',
                dest='accept_all',
                default=False,
                action='store_true',
                help='Accept all pending keys')

        parser.add_option('-r',
                '--reject',
                dest='reject',
                default='',
                help='Reject the specified public key')

        parser.add_option('-R',
                '--reject-all',
                dest='reject_all',
                default=False,
                action='store_true',
                help='Reject all pending keys')

        parser.add_option('-p',
                '--print',
                dest='print',
                default='',
                help='Print the specified public key')

        parser.add_option('-P',
                '--print-all',
                dest='print_all',
                default=False,
                action='store_true',
                help='Print all public keys')

        parser.add_option('-d',
                '--delete',
                dest='delete',
                default='',
                help='Delete the named key')

        parser.add_option('-D',
                '--delete-all',
                dest='delete_all',
                default=False,
                action='store_true',
                help='Delete all keys')

        parser.add_option('-q',
                '--quiet',
                dest='quiet',
                default=False,
                action='store_true',
                help='Supress output')

        parser.add_option('--key-logfile',
                dest='key_logfile',
                help=('Send all output to a file. '
                      'Default is /var/log/salt/key.log'))

        parser.add_option('--gen-keys',
                dest='gen_keys',
                default='',
                help='Set a name to generate a keypair for use with salt')

        parser.add_option('--gen-keys-dir',
                dest='gen_keys_dir',
                default='.',
                help=('Set the direcotry to save the generated keypair, '
                      'only works with "gen_keys_dir" option; default=.'))

        parser.add_option('--keysize',
                dest='keysize',
                default=2048,
                type=int,
                help=('Set the keysize for the generated key, only works with '
                      'the "--gen-keys" option, the key size must be 2048 or '
                      'higher, otherwise it will be rounded up to 2048'
                      '; default=2048'))

        parser.add_option('-c',
                '--config',
                dest='conf_file',
                default='/etc/salt/master',
                help='Pass in an alternative configuration file')

        parser.add_option('--raw-out',
                default=False,
                action='store_true',
                dest='raw_out',
                help=('Print the output from the salt-key command in raw python '
                      'form, this is suitable for re-reading the output into '
                      'an executing python script with eval.'))

        parser.add_option('--yaml-out',
                default=False,
                action='store_true',
                dest='yaml_out',
                help='Print the output from the salt-key command in yaml.')

        parser.add_option('--json-out',
                default=False,
                action='store_true',
                dest='json_out',
                help='Print the output from the salt-key command in json.')

        parser.add_option('--no-color',
                default=False,
                action='store_true',
                dest='no_color',
                help='Disable all colored output')

        options, args = parser.parse_args()

        opts = {}
        opts.update(salt.config.master_config(options.conf_file))

        for k, v in options.__dict__.items():
            if k == 'keysize':
                if v < 2048:
                    opts[k] = v
                else:
                    opts[k] = v
            elif v is not None:
                opts[k] = v
        # I decided to always set this to info, since it really all is info or
        # error.
        opts['loglevel'] = 'info'
        return opts

    def run(self):
        '''
        Execute saltkey
        '''
        verify_env([
            os.path.join(self.opts['pki_dir'], 'minions'),
            os.path.join(self.opts['pki_dir'], 'minions_pre'),
            os.path.join(self.opts['pki_dir'], 'minions_rejected'),
            os.path.dirname(self.opts['log_file']),
            ],
            self.opts['user'])
        import salt.log
        salt.log.setup_logfile_logger(self.opts['key_logfile'],
                                      self.opts['loglevel'])
        key = salt.cli.key.Key(self.opts)
        key.run()


class SaltCall(object):
    '''
    Used to locally execute a salt command
    '''
    def __init__(self):
        self.opts = self.__parse()

    def __parse(self):
        '''
        Parse the command line arguments
        '''
        usage = "%prog [options] <function> [arguments]"
        parser = optparse.OptionParser(
                version='salt-call {0}'.format(VERSION),
                usage=usage
                )

        parser.add_option('-g',
                '--grains',
                dest='grains_run',
                default=False,
                action='store_true',
                help='Return the information generated by the salt grains')
        parser.add_option('-m',
                '--module-dirs',
                dest='module_dirs',
                default='',
                help=('Specify an additional directories to pull modules '
                      'from, multiple directories can be delimited by commas'))
        parser.add_option('-c',
                '--config',
                dest='conf_file',
                default='/etc/salt/minion',
                help='Pass in an alternative configuration file')
        parser.add_option('-d',
                '--doc',
                dest='doc',
                default=False,
                action='store_true',
                help=('Return the documentation for the specified module of '
                      'for all modules if none are specified'))
        parser.add_option('-l',
                '--log-level',
                default='info',
                dest='log_level',
                help='Set the output level for salt-call')
        parser.add_option('--raw-out',
                default=False,
                action='store_true',
                dest='raw_out',
                help=('Print the output from the salt command in raw python '
                      'form, this is suitable for re-reading the output into '
                      'an executing python script with eval.'))
        parser.add_option('--text-out',
                default=False,
                action='store_true',
                dest='txt_out',
                help=('Print the output from the salt command in the same '
                      'form the shell would.'))
        parser.add_option('--yaml-out',
                default=False,
                action='store_true',
                dest='yaml_out',
                help='Print the output from the salt command in yaml.')
        parser.add_option('--json-out',
                default=False,
                action='store_true',
                dest='json_out',
                help='Print the output from the salt command in json.')
        parser.add_option('--no-color',
                default=False,
                dest='no_color',
                action='store_true',
                help='Disable all colored output')

        options, args = parser.parse_args()

        opts = {}
        opts.update(salt.config.minion_config(options.conf_file))

        for k, v in options.__dict__.items():
            if k == 'module_dirs':
                opts[k] = v.split(',')
            else:
                opts[k] = v

        if len(args) >= 1:
            opts['fun'] = args[0]
            opts['arg'] = args[1:]
        elif opts['grains_run']:
            pass
        else:
            # salt-call should not ever be called without arguments
            parser.print_help()
            parser.exit(1)

        verify_env([opts['pki_dir'],
                    opts['cachedir'],
                    os.path.dirname(opts['log_file']),
                    ],
                    opts['user'])

        return opts

    def run(self):
        '''
        Execute the salt call!
        '''
        import salt.log
        salt.log.setup_console_logger(
            self.opts['log_level']
        )
        caller = salt.cli.caller.Caller(self.opts)
        caller.run()


class SaltRun(object):
    '''
    Used to execute salt convenience functions
    '''
    def __init__(self):
        self.opts = self.__parse()

    def __parse(self):
        '''
        Parse the command line arguments
        '''
        parser = optparse.OptionParser(version="%%prog %s" % VERSION)

        parser.add_option('-c',
                '--config',
                dest='conf_file',
                default='/etc/salt/master',
                help=('Change the location of the master configuration; '
                      'default=/etc/salt/master'))

        parser.add_option('-d',
                '--doc',
                '--documentation',
                dest='doc',
                default=False,
                action='store_true',
                help=('Display documentation for runners, pass a module or '
                      'a runner to see documentation on only that '
                      'module/runner.'))

        options, args = parser.parse_args()

        opts = {}
        opts.update(salt.config.master_config(options.conf_file))
        opts['conf_file'] = options.conf_file
        opts['doc'] = options.doc
        if len(args) > 0:
            opts['fun'] = args[0]
        else:
            opts['fun'] = ''
        if len(args) > 1:
            opts['arg'] = args[1:]
        else:
            opts['arg'] = []

        return opts

    def run(self):
        '''
        Execute salt-run
        '''
        runner = salt.runner.Runner(self.opts)
        # Run this here so SystemExit isn't raised
        # anywhere else when someone tries to  use
        # the runners via the python api
        try:
            runner.run()
        except SaltClientError as exc:
            raise SystemExit(str(exc))
