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
                action='store_true'
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
        parser.add_option('-c',
                '--cmd',
                dest='cmd',
                default='',
                help='Used with the Query option, pass in the command to get'\
                    + ' results from.')

        options, args = parser.parse_args()

        opts = {}

        opts['timeout'] = options.timeout
        opts['pcre'] = options.pcre
        if options.query:
            opts['query'] = options.query
            opts['cmd'] = options.cmd
        else:
            opts['tgt'] = args[0]
            opts['fun'] = args[1]
            opts['arg'] = args[2:]

        return opts

    def run(self):
        '''
        Execute the salt command line
        '''
        if opts['query']:
            cli = 
        local = salt.client.LocalClient()
        args = [self.opts['tgt'],
                self.opts['fun'],
                self.opts['arg'],
                self.opts['timeout'],
                ]
        if self.opts['pcre']:
            args.append('pcre')
        print local.cmd(*args)

