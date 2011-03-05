'''
Make me some salt!
'''
# Import python libs
import os
import optparse
# Import salt libs
import salt.master
import salt.minion
import salt.config
import salt.utils

def verify_env(dirs):
    '''
    Verify that the named direcotries are in place and that the environment
    can shake the salt
    '''
    for dir_ in dirs:
        if not os.path.isdir(dir_):
            os.makedirs(dir_)

class Master(object):
    '''
    Creates a master server
    '''
    def __init__(self):
        self.cli = self.__parse_cli()
        self.opts = salt.config.master_config(self.cli['config'])

    def __parse_cli(self):
        '''
        Parse the cli for options passed to a master daemon
        '''
        parser = optparse.OptionParser()
        parser.add_option('-d',
                '--daemon',
                dest='daemon',
                default=False,
                action='store_true',
                help='Run the master in a daemon')
        parser.add_option('-c',
                '--config',
                dest='config',
                default='/etc/salt/master',
                help='Pass in an alternative configuration file')
        
        options, args = parser.parse_args()
        cli = {'daemon': options.daemon,
               'config': options.config}

        return cli

    def start(self):
        '''
        Run the sequence to start a salt master server
        '''
        verify_env([os.path.join(self.opts['pki_dir'], 'minions'),
                    self.opts['cachedir']])
        master = salt.master.Master(self.opts)
        if self.cli['daemon']:
            salt.utils.daemonize()
        master.start()


class Minion(object):
    '''
    Create a minion server
    '''
    def __init__(self):
        self.cli = self.__parse_cli()
        self.opts = salt.config.minion_config(self.cli['config'])

    def __parse_cli(self):
        '''
        Parse the cli input
        '''
        parser = optparse.OptionParser()
        parser.add_option('-d',
                '--daemon',
                dest='daemon',
                default=False,
                action='store_true',
                help='Run the minion as a daemon')
        parser.add_option('-c',
                '--config',
                dest='config',
                default='/etc/salt/minion',
                help='Pass in an alternative configuration file')
        
        options, args = parser.parse_args()
        cli = {'daemon': options.daemon,
               'config': options.config}

        return cli

    def start(self):
        '''
        Execute this method to start up a minion.
        '''
        verify_env([self.opts['pki_dir'], self.opts['cachedir']])
        minion = salt.minion.Minion(self.opts)
        if self.cli['daemon']:
            salt.utils.daemonize()
        minion.tune_in()
