#/usr/bin/env python
'''
The minionswarm script will start a group of salt minions with different ids
on a single system to test scale capabilities
'''

# Import Python Libs
import os
import optparse
import subprocess
import tempfile

# Import third party libs
import yaml

def parse():
    '''
    Parse the cli options
    '''
    parser = optparse.OptionParser()
    parser.add_option('-m',
            '--minions',
            dest='minions',
            default=5,
            type='int',
            help='The number of minions to make')

    options, args = parser.parse_args()
    
    opts = {}

    for key, val in options.__dict__.items():
        opts[key] = val

    return opts


class Swarm(object):
    '''
    Create a swarm of minions
    '''
    def __init__(self, opts):
        self.opts = opts
        self.confs = set()

    def mkconf(self):
        '''
        Create a config file for a single minion
        '''
        fd, path = tempfile.mkstemp()
        os.close(fd)
        data = {'id': os.path.basename(path)}
        yaml.dump(path, data)
        self.confs.add(path)

    def start_minions(self):
        '''
        Iterate over the config files and start up the minions
        '''
        for path in self.confs:
            cmd = 'salt-minion -c {0} --pid-file {1} -d'.format(
                    path,
                    '{0}.pid'.format(path)
                    )
            subprocess.call(cmd)

    def prep_configs(self):
        '''
        Prepare the confs set
        '''
        for ind in xrange(self.opts['minions']):
            self.mkconf()

    def clean_configs(self):
        '''
        Clean up the config files
        '''
        for path in self.confs:
            try:
                os.remove(path)
            except:
                pass

    def start(self):
        '''
        Start the minions!!
        '''
        self.prep_configs()
        self.start_minions()
        self.clean_configs()

if __name__ == '__main__':
    swarm = Swarm(parse())
    swarm.start()
