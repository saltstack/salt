'''
The management of salt command line utilities are stored in here
'''
# Import python libs
import optparse
import os
import sys
import yaml

# Import salt components
import salt.client

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
        parser.add_option('-g',
                '--global-timeout',
                default=10,
                type=int,
                dest='global_timeout',
                help='How long to wait if no minions reply; default=10 seconds')
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
        parser.add_option('-F',
                '--facter',
                default=False,
                dest='facter',
                action='store_true',
                help='Instead of using shell globs to evaluate the target'\
                   + ' use a facter value to identify targets, the syntax'\
                   + ' for the target is the facter key followed by a pcre'\
                   + ' regular expresion:\n"operatingsystem:Arch.*"')
        parser.add_option('-Q',
                '--query',
                dest='query',
                default=False,
                action='store_true',
                help='Execute a salt command query, this can be used to find'\
                    + ' previous function calls, of to look up a call that'\
                    + ' occured at a specific time.')

        options, args = parser.parse_args()

        opts = {}

        opts['timeout'] = options.timeout
        opts['global_timeout'] = options.global_timeout
        opts['pcre'] = options.pcre
        opts['list'] = options.list_
        opts['facter'] = options.facter
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
            opts['fun'] = args[1]
            opts['arg'] = args[2:]

        return opts

    def run(self):
        '''
        Execute the salt command line
        '''
        local = salt.client.LocalClient()
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
            elif self.opts['facter']:
                args.append('facter')
            
            ret = local.cmd(*args)

            # Handle special case commands
            if self.opts['fun'] == 'sys.doc':
                self._print_docs(ret)
            else:
                if type(ret) == type(list()) or type(ret) == type(dict()):
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

