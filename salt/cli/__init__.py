'''
The management of salt command line utilities are stored in here
'''
# Import python libs
import optparse
import os
import sys

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
                help='Set the return timeout for batch jobs')
        parser.add_option('-E',
                '--pcre',
                default=False,
                dest='pcre',
                action='store_true',
                help='Instead of using shell globs to evaluate the target'\
                   + ' servers, use pcre regular expressions')
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
        opts['pcre'] = options.pcre
        if options.query:
            opts['query'] = options.query
            if len(args) < 1:
                err = 'Please pass in a command to query the old salt calls'\
                    + ' for.'
                sys.stderr.write(err, + '\n')
                sys.exit('2')
            opts['cmd'] = args[0]
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
            
            ret = local.cmd(*args)

            # Handle special case commands
            if self.opts['fun'] == 'sys.doc':
                self._print_docs(ret)
            else:
                print ret

    def _print_docs(self, ret):
        '''
        Print out the docstrings for all of the functions on the minions
        '''
        docs = {}
        for host in ret:
            for fun in ret[host]:
                if not docs.has_key(fun):
                    if ret[host][fun]
                        docs[fun] = ret[host][fun]
        for fun in docs:
            print fun
            print docs[fun]

