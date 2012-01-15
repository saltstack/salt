'''
The management of salt command line utilities are stored in here
'''

# Import python libs
import optparse
import os
import sys
import yaml
import json

# Import salt components
import salt.cli.caller
import salt.cli.cp
import salt.cli.key
import salt.client
import salt.output
import salt.runner

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
                dest='list_',
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
                      'for the target is the grain key followed by a pcre '
                      'regular expression:\n"os:Arch.*"'))
        parser.add_option('-X',
                '--exsel',
                default=False,
                dest='exsel',
                action='store_true',
                help=('Instead of using shell globs use the return code '
                      'of a function.'))
        parser.add_option('-N',
                '--nodegroup',
                default=False,
                dest='nodegroup',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'use one of the predefined nodegroups to identify a '
                      'list of targets.'))
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
                dest='return_',
                metavar='RETURNER',
                help=('Set an alternative return method. By default salt will '
                      'send the return data from the command back to the '
                      'master, but the return data can be redirected into '
                      'any number of systems, databases or applications.'))
        parser.add_option('-Q',
                '--query',
                dest='query',
                default=False,
                action='store_true',
                help=('Execute a salt command query, this can be used to find '
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

        options, args = parser.parse_args()

        opts = {}

        opts['timeout'] = options.timeout
        opts['pcre'] = options.pcre
        opts['list'] = options.list_
        opts['grain'] = options.grain
        opts['exsel'] = options.exsel
        opts['nodegroup'] = options.nodegroup
        opts['compound'] = options.compound
        opts['return'] = options.return_
        opts['conf_file'] = options.conf_file
        opts['raw_out'] = options.raw_out
        opts['txt_out'] = options.txt_out
        opts['yaml_out'] = options.yaml_out
        opts['json_out'] = options.json_out

        if opts['return']:
            if opts['timeout'] == 5:
                opts['timeout'] = 0

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
                parser.exit()

            if opts['list']:
                opts['tgt'] = args[0].split(',')
            else:
                opts['tgt'] = args[0]

            if args[1].count(','):
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
            local = None
            ret = exc
            out = ''
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

                    print 'Return data for job {0}:'.format(jid)
                    printout(ret[jid])
                    print ''

        else:
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
            elif self.opts['exsel']:
                args.append('exsel')
            elif self.opts['nodegroup']:
                args.append('nodegroup')
            elif self.opts['compound']:
                args.append('compound')
            else:
                args.append('glob')

            if self.opts['return']:
                args.append(self.opts['return'])
            try:
                # local will be None when there was an error
                if local:
                    full_ret = local.cmd_full_return(*args)
                    ret, out = self._format_ret(full_ret)
            except SaltInvocationError as exc:
                ret = exc
                out = ''

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
                printout(ret)

            # Always exit with a return code of 1 on issues
            if isinstance(ret, Exception):
                sys.exit(1)

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
            print fun + ':'
            print docs[fun]
            print ''


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
        parser = optparse.OptionParser(version="%%prog %s" % VERSION)

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
                dest='list_',
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
                      'for the target is the grains key followed by a pcre '
                      'regular expression:\n"os:Arch.*"'))
        parser.add_option('-N',
                '--nodegroup',
                default=False,
                dest='nodegroup',
                action='store_true',
                help=('Instead of using shell globs to evaluate the target '
                      'use one of the predefined nodegroups to identify a '
                      'list of targets.'))
        parser.add_option('-c',
                '--config',
                default='/etc/salt/master',
                dest='conf_file',
                help=('The location of the salt master configuration file, '
                      'the salt master settings are required to know where '
                      'the connections are; default=/etc/salt/master'))

        options, args = parser.parse_args()

        opts = {}

        opts['timeout'] = options.timeout
        opts['pcre'] = options.pcre
        opts['list'] = options.list_
        opts['grain'] = options.grain
        opts['nodegroup'] = options.nodegroup
        opts['conf_file'] = options.conf_file

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
                dest='list_',
                default=False,
                action='store_true',
                help='List the unaccepted public keys')

        parser.add_option('-L',
                '--list-all',
                dest='list_all',
                default=False,
                action='store_true',
                help='List all public keys')

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

        parser.add_option('-p',
                '--print',
                dest='print_',
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
                dest='config',
                default='/etc/salt/master',
                help='Pass in an alternative configuration file')

        options, args = parser.parse_args()

        opts = {}

        opts['list'] = options.list_
        opts['list_all'] = options.list_all
        opts['accept'] = options.accept
        opts['accept_all'] = options.accept_all
        opts['print'] = options.print_
        opts['print_all'] = options.print_all
        opts['delete'] = options.delete
        opts['gen_keys'] = options.gen_keys
        opts['gen_keys_dir'] = options.gen_keys_dir
        if options.keysize < 2048:
            opts['keysize'] = 2048
        else:
            opts['keysize'] = options.keysize

        opts.update(salt.config.master_config(options.config))

        return opts

    def run(self):
        '''
        Execute saltkey
        '''
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
        parser = optparse.OptionParser(version="%%prog %s" % VERSION)

        parser.add_option('-g',
                '--grains',
                dest='grains',
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
                dest='config',
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

        opts['grains_run'] = options.grains
        opts['module_dirs'] = options.module_dirs.split(',')
        opts['doc'] = options.doc
        opts['raw_out'] = options.raw_out
        opts['txt_out'] = options.txt_out
        opts['yaml_out'] = options.yaml_out
        opts['color'] = not options.no_color
        opts['json_out'] = options.json_out
        opts.update(salt.config.minion_config(options.config))
        opts['log_level'] = options.log_level
        if len(args) >= 1:
            opts['fun'] = args[0]
            opts['arg'] = args[1:]
        else:
            opts['fun'] = ''
            opts['arg'] = []
        salt.verify_env([opts['pki_dir'],
            opts['cachedir'],
            os.path.dirname(opts['log_file']),
            ])

        return opts

    def run(self):
        '''
        Execute the salt call!
        '''
        import salt.log
        salt.log.setup_console_logger(
            self.opts['log_level']
        )
        import logging
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
                dest='config',
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

        opts['config'] = options.config
        opts['doc'] = options.doc

        if len(args) > 0:
            opts['fun'] = args[0]
        else:
            opts['fun'] = ''
        if len(args) > 1:
            opts['arg'] = args[1:]
        else:
            opts['arg'] = []

        opts.update(salt.config.master_config(options.config))

        return opts

    def run(self):
        '''
        Execute the salt call!
        '''
        runner = salt.runner.Runner(self.opts)
        runner.run()
