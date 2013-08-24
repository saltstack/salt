#/usr/bin/env python
'''
The minionswarm script will start a group of salt minions with different ids
on a single system to test scale capabilities
'''

# Import Python Libs
import os
import pwd
import time
import signal
import optparse
import subprocess
import tempfile
import shutil

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
    parser.add_option('--name',
            '-n',
            dest='name',
            default='ms',
            help=('Give the minions an alternative id prefix, this is used '
                  'when minions from many systems are being aggregated onto '
                  'a single master'))
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
    parser.add_option('--no-clean',
            action='store_true',
            default=False,
            help='Don\'t cleanup temporary files/directories')
    parser.add_option('--root-dir',
            dest='root_dir',
            default=None,
            help='Override the minion root_dir config')

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

        # If given a root_dir, keep the tmp files there as well
        if opts['root_dir']:
            tmpdir = os.path.join(opts['root_dir'], 'tmp')
        else:
            tmpdir = opts['root_dir']

        self.swarm_root = tempfile.mkdtemp(prefix='mswarm-root', suffix='.d',
            dir=tmpdir)

        self.pki = self._pki_dir()
        self.__zfill = len(str(self.opts['minions']))

        self.confs = set()

    def _pki_dir(self):
        '''
        Create the shared pki directory
        '''
        path = os.path.join(self.swarm_root, 'pki')
        os.makedirs(path)

        print('Creating shared pki keys for the swarm on: {0}'.format(path))
        subprocess.call(
            'salt-key -c {0} --gen-keys minion --gen-keys-dir {0} '
            '--log-file {1}'.format(
                path, os.path.join(path, 'keys.log')
            ), shell=True
        )
        print('Keys generated')
        return path

    def mkconf(self, idx):
        '''
        Create a config file for a single minion
        '''
        minion_id = '{0}-{1}'.format(
                self.opts['name'],
                str(idx).zfill(self.__zfill)
                )

        dpath = os.path.join(self.swarm_root, minion_id)
        os.makedirs(dpath)

        minion_pkidir = os.path.join(dpath, 'pki')
        os.makedirs(minion_pkidir)
        minion_pem = os.path.join(self.pki, 'minion.pem')
        minion_pub = os.path.join(self.pki, 'minion.pub')
        shutil.copy(minion_pem, minion_pkidir)
        shutil.copy(minion_pub, minion_pkidir)

        data = {
            'id': minion_id,
            'user': pwd.getpwuid(os.getuid()).pw_name,
            'pki_dir': minion_pkidir,
            'cachedir': os.path.join(dpath, 'cache'),
            'master': self.opts['master'],
            'log_file': os.path.join(dpath, 'minion.log')
        }

        if self.opts['root_dir']:
            data['root_dir'] = self.opts['root_dir']

        path = os.path.join(dpath, 'minion')

        if self.opts['keep']:
            keep = self.opts['keep'].split(',')
            modpath = os.path.join(os.path.dirname(salt.__file__), 'modules')
            fn_prefixes = (fn_.partition('.')[0] for fn_ in os.listdir(modpath))
            ignore = [fn_prefix for fn_prefix in fn_prefixes if fn_prefix not in keep]
            data['disable_modules'] = ignore

        with open(path, 'w+') as fp_:
            yaml.dump(data, fp_)
        self.confs.add(dpath)

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
        for idx in range(self.opts['minions']):
            self.mkconf(idx)

    def clean_configs(self):
        '''
        Clean up the config files
        '''
        for path in self.confs:
            pidfile = '{0}.pid'.format(path)
            try:
                try:
                    pid = int(open(pidfile).read().strip())
                    os.kill(pid, signal.SIGTERM)
                except ValueError:
                    pass
                if os.path.exists(pidfile):
                    os.remove(pidfile)
                if not self.opts['no_clean']:
                    shutil.rmtree(path)
            except (OSError, IOError):
                pass

    def start(self):
        '''
        Start the minions!!
        '''
        print('Starting minions...')
        self.prep_configs()
        self.start_minions()
        print('All {0} minions have started.'.format(self.opts['minions']))
        print('Waiting for CTRL-C to properly shutdown minions...')
        while True:
            try:
                time.sleep(5)
            except KeyboardInterrupt:
                print('\nShutting down minions')
                self.clean_configs()
                break

    def shutdown(self):
        print('Killing any remaining running minions')
        subprocess.call(
            'kill -KILL $(ps aux | grep python | grep "salt-minion" '
            '| awk \'{print $2}\')',
            shell=True
        )
        if not self.opts['no_clean']:
            print('Remove ALL related temp files/directories')
            shutil.rmtree(self.swarm_root)
        print('Done')

if __name__ == '__main__':
    swarm = Swarm(parse())
    try:
        swarm.start()
    finally:
        swarm.shutdown()
