#!/usr/bin/env python
'''
Test interacting with the wheel system. This script is useful when testing
wheel modules
'''

# Import Python libs
import optparse

# Import Salt Libs
import salt.config
import salt.wheel
import salt.auth


def parse():
    '''
    Parse the command line options
    '''
    parser = optparse.OptionParser()
    parser.add_option('-f',
            '--fun',
            '--function',
            dest='fun',
            help='The wheel function to execute')
    parser.add_option('-auth',
            '-a',
            dest='eauth',
            help='The external authentication mechanism to use')

    options, args = parser.parse_opts()




class Wheeler(object):
    '''
    Set up communication with the wheel interface
    '''
    def __init__(self, cli):
        self.opts = salt.config.master_config('/etc/salt')
        self.wheel = salt.wheel.Wheel(self.opts)

    def _eauth(self):
        '''
        Fill in the blanks for the eauth system
        '''
        if self.options.eauth:
        resolver = salt.auth.Resolver(self.config)
        res = resolver.cli(self.options.eauth)
        if self.options.mktoken and res:
            tok = resolver.token_cli(
                    self.options.eauth,
                    res
                    )
            if tok:
                kwargs['token'] = tok.get('token', '')
        if not res:
            sys.exit(2)
        kwargs.update(res)
        kwargs['eauth'] = self.options.eauth


print wheel.master_call('key.list_all', username='thatch', eauth='pam', password='idfsuhgsklfdn')
