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
import shutil
import random
import hashlib

# Import salt libs
import salt

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
    parser.add_option('--master',
            dest='master',
            default='salt',
            help='The location of the salt master that this swarm will serve')
    parser.add_option('-k',
            '--keep-modules',
            dest='keep',
            default='',
            help='A comma delimited list of modules to enable')
    parser.add_option('-f',
            '--foreground',
            dest='foreground',
            default=False,
            action='store_true',
            help=('Run the minions with debug output of the swarm going to '
                  'the terminal'))

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
        self.pki = self._pki_dir()
        self.confs = set()

    def _pki_dir(self):
        '''
        Create the shared pki directory
        '''
        path = tempfile.mkdtemp()
        cmd = 'salt-key --gen-keys minion --gen-keys-dir {0}'.format(path)
        print('Creating shared pki keys for the swarm')
        subprocess.call(cmd, shell=True)
        return path

    def mkconf(self):
        '''
        Create a config file for a single minion
        '''
        fd_, path = tempfile.mkstemp()
        path = '{0}{1}'.format(
                path,
                hashlib.md5(str(random.randint(0, 999999))).hexdigest())
        os.close(fd_)
        dpath = '{0}.d'.format(path)
        os.makedirs(dpath)
        data = {'id': os.path.basename(path),
                'pki_dir': self.pki,
                'cachedir': os.path.join(dpath, 'cache'),
                'master': self.opts['master'],
               }
        if self.opts['keep']:
            ignore = set()
            keep = self.opts['keep'].split(',')
            modpath = os.path.join(os.path.dirname(salt.__file__), 'modules')
            for fn_ in os.listdir(modpath):
                if fn_.split('.')[0] in keep:
                    continue
                ignore.add(fn_.split('.')[0])
            data['disable_modules'] = list(ignore)
        with open(path, 'w+') as fp_:
            yaml.dump(data, fp_)
        self.confs.add(path)

    def start_minions(self):
        '''
        Iterate over the config files and start up the minions
        '''
        for path in self.confs:
            cmd = 'salt-minion -c {0} --pid-file {1}'.format(
                    path,
                    '{0}.pid'.format(path)
                    )
            if self.opts['foreground']:
                cmd += ' -l debug &'
            else:
                cmd += ' -d &'
            subprocess.call(cmd, shell=True)

    def prep_configs(self):
        '''
        Prepare the confs set
        '''
        for ind in range(self.opts['minions']):
            self.mkconf()

    def clean_configs(self):
        '''
        Clean up the config files
        '''
        for path in self.confs:
            try:
                os.remove(path)
                os.remove('{0}.pid'.format(path))
                shutil.rmtree('{0}.d'.format(path))
            except (OSError, IOError):
                pass

    def start(self):
        '''
        Start the minions!!
        '''
        self.prep_configs()
        self.start_minions()

if __name__ == '__main__':
    swarm = Swarm(parse())
    swarm.start()
