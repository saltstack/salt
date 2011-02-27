'''
Make me some salt!
'''
# Import python libs
import os
import optparse
# Import salt libs
import salt.master
import salt.minion
import salt.utils

class Master(object):
    '''
    Creates a master server
    '''


class Minion(object):
    '''
    Create a minion server
    '''
    def __init__(self):
        self.cli = self.__parse_cli()
        self.opts = salt.utils.minion_config(self.cli)

    def __parse_cli(self):
        '''
        Parse the cli input
        '''
        parser = optparse.OptionParser()
        parser.add_option('-f',
                '--foreground',
                dest='foreground',
                default=False,
                action='store_true',
                help='Run the minion in the foreground')
        parser.add_option('-c',
                '--config',
                dest='config',
                default='/etc/salt/minion',
                help='Pass in an alternative configuration file')
        
        options, args = parser.parse_args()
        cli = {'foreground': options.foreground,
               'config': options.config}

        return cli

    def start(self):
        '''
        Execute this method to start up a minion.
        '''
        minion = salt.Minion(self.opts)
        minion.tune_in()
