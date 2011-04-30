'''
The management of salt command line utilities are stored in here
'''
# Import python libs
import optparse
import os
import sys
import yaml
JSON = False
try:
    import json
    JSON = True
except:
    pass

# Import salt components
import salt.client
import salt.cli.key
import salt.cli.cp
import salt.cli.caller

class SaltCMD(object):
    '''
    The execution of a salt command happens here
    '''
    def __init__(self):
        '''
        Cretae a SaltCMD object
        '''
        self.opts = self.__parse()

    def __parse(self):
        '''
        Parse the command line
        '''
        parser = optparse.OptionParser()
        
        parser.add_option('-t',
                '--timeout',
                default=5,
                type=int,
                dest='timeout',
                help='Set the return timeout for batch jobs; default=5 seconds')
        parser.add_option('-E',
                '--pcre',
                default=False,
                dest='pcre',
                action='store_true',
                help='Instead of using shell globs to evaluate the target'\
                   + ' servers, use pcre regular expressions')
        parser.add_option('-L',
                '--list',
                default=False,
                dest='list_',
                action='store_true',
                help='Instead of using shell globs to evaluate the target'\
                   + ' servers, take a comma delimited list of servers.')
        parser.add_option('-G',
                '--grain',
                default=False,
                dest='grain',
                action='store_true',
                help='Instead of using shell globs to evaluate the target'\
                   + ' use a grain value to identify targets, the syntax'\
                   + ' for the target is the grain key followed by a pcre'\
                   + ' regular expresion:\n"os:Arch.*"')
        parser.add_option('-X',
                '--exsel',
                default=False,
                dest='exsel',
                action='store_true',
                help='Instead of using shell globs use the return code'\
                   + ' of a function.')
        parser.add_option('--return',
                default='',
                dest='return_',
                help='Set an alternative return method. By default salt will'\
                    + ' send the return data from the command back to the'\
                    + ' master, but the return data can be redirected into'\
                    + ' any number of systems, databases or applications.')
        parser.add_option('-Q',
                '--query',
                dest='query',
                default=False,
                action='store_true',
                help='Execute a salt command query, this can be used to find'\
                    + ' the results os a previous function call: -Q test.echo')
        parser.add_option('-c',
                '--config',
                default='/etc/salt/master',
                dest='conf_file',
                help='The location of the salt master configuration file,'\
                    + ' the salt master settings are required to know where'\
                    + ' the connections are; default=/etc/salt/master')
        parser.add_option('--raw-out',
                default=False,
                action='store_true',
                dest='raw_out',
                help='Print the output from the salt command in raw python'\
                   + ' form, this is suitible for re-reading the output into'\
                   + ' an executing python script with eval.')
        if JSON:
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
        opts['return'] = options.return_
        opts['conf_file'] = options.conf_file
        opts['raw_out'] = options.raw_out
        if JSON:
            opts['json_out'] = options.json_out
        else:
            opts['json_out'] = False

        if opts['return']:
            if opts['timeout'] == 5:
                opts['timeout'] = 0

        if options.query:
            opts['query'] = options.query
            if len(args) < 1:
                err = 'Please pass in a command to query the old salt calls'\
                    + ' for.'
                sys.stderr.write(err, + '\n')
                sys.exit('2')
            opts['cmd'] = args[0]
        else:
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
                    err = 'Cannot execute compound command without defining'\
                        + ' all arguments.'
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
        local = salt.client.LocalClient(self.opts['conf_file'])
        if self.opts.has_key('query'):
            print local.find_cmd(self.opts['cmd'])
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
            else:
                args.append('glob')
        
            if self.opts['return']:
                args.append(self.opts['return'])
            ret = local.cmd(*args)

            # Handle special case commands
            if self.opts['fun'] == 'sys.doc':
                self._print_docs(ret)
            else:
                if type(ret) == type(list()) or type(ret) == type(dict()):
                    if self.opts['raw_out']:
                        print ret
                    elif self.opts['json_out']:
                        print json.dumps(ret)
                    else:
                        print yaml.dump(ret)

    def _print_docs(self, ret):
        '''
        Print out the docstrings for all of the functions on the minions
        '''
        docs = {}
        for host in ret:
            for fun in ret[host]:
                if not docs.has_key(fun):
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
        parser = optparse.OptionParser()
        
        parser.add_option('-t',
                '--timeout',
                default=5,
                type=int,
                dest='timeout',
                help='Set the return timeout for batch jobs; default=5 seconds')
        parser.add_option('-E',
                '--pcre',
                default=False,
                dest='pcre',
                action='store_true',
                help='Instead of using shell globs to evaluate the target'\
                   + ' servers, use pcre regular expressions')
        parser.add_option('-L',
                '--list',
                default=False,
                dest='list_',
                action='store_true',
                help='Instead of using shell globs to evaluate the target'\
                   + ' servers, take a comma delimited list of servers.')
        parser.add_option('-G',
                '--grain',
                default=False,
                dest='grain',
                action='store_true',
                help='Instead of using shell globs to evaluate the target'\
                   + ' use a grain value to identify targets, the syntax'\
                   + ' for the target is the grains key followed by a pcre'\
                   + ' regular expresion:\n"os:Arch.*"')
        parser.add_option('-c',
                '--config',
                default='/etc/salt/master',
                dest='conf_file',
                help='The location of the salt master configuration file,'\
                    + ' the salt master settings are required to know where'\
                    + ' the connections are; default=/etc/salt/master')

        options, args = parser.parse_args()

        opts = {}

        opts['timeout'] = options.timeout
        opts['pcre'] = options.pcre
        opts['list'] = options.list_
        opts['grain'] = options.grain
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
        parser = optparse.OptionParser()

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
        parser = optparse.OptionParser()

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
                help='Specify an additional directories to pull modules from,'\
                    + ' multiple directories can be delimited by commas')
        parser.add_option('-d',
                '--doc',
                dest='doc',
                default=False,
                action='store_true',
                help="Return the documentation for the specified module of'\
                    + ' for all modules if none are specified")

        options, args = parser.parse_args()

        opts = {}

        opts['grains'] = options.grains
        opts['module_dirs'] = options.module_dirs.split(',')
        opts['doc'] = options.doc
        if len(args) >= 1:
            opts['fun'] = args[0]
            opts['arg'] = args[1:]
        else:
            opts['fun'] = ''
            opts['arg'] = []

        return opts

    def run(self):
        '''
        Execute the salt call!
        '''
        caller = salt.cli.caller.Caller(self.opts)
        caller.run()
