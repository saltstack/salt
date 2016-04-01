#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
The minionswarm script will start a group of salt minions with different ids
on a single system to test scale capabilities
'''

# Import Python Libs
from __future__ import absolute_import, print_function
import os
import pwd
import time
import signal
import optparse
import subprocess
import tempfile
import shutil
import sys

# Import salt libs
import salt

# Import third party libs
import yaml
import salt.ext.six as six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin


def parse():
    '''
    Parse the cli options
    '''
    parser = optparse.OptionParser()
    parser.add_option(
        '-m',
        '--minions',
        dest='minions',
        default=5,
        type='int',
        help='The number of minions to make')
    parser.add_option(
        '-M',
        action='store_true',
        dest='master_too',
        default=False,
        help='Run a local master and tell the minions to connect to it')
    parser.add_option(
        '--master',
        dest='master',
        default='salt',
        help='The location of the salt master that this swarm will serve')
    parser.add_option(
        '--name',
        '-n',
        dest='name',
        default='ms',
        help=('Give the minions an alternative id prefix, this is used '
              'when minions from many systems are being aggregated onto '
              'a single master'))
    parser.add_option(
        '-k',
        '--keep-modules',
        dest='keep',
        default='',
        help='A comma delimited list of modules to enable')
    parser.add_option(
        '-f',
        '--foreground',
        dest='foreground',
        default=False,
        action='store_true',
        help=('Run the minions with debug output of the swarm going to '
              'the terminal'))
    parser.add_option(
        '--no-clean',
        action='store_true',
        default=False,
        help='Don\'t cleanup temporary files/directories')
    parser.add_option(
        '--root-dir',
        dest='root_dir',
        default=None,
        help='Override the minion root_dir config')
    parser.add_option(
        '--transport',
        dest='transport',
        default='zeromq',
        help='Declare which transport to use, default is zeromq')
    parser.add_option(
        '-c', '--config-dir', default='/etc/salt',
        help=('Pass in an alternative configuration directory. Default: '
              '%default')
        )
    parser.add_option('-u', '--user', default=pwd.getpwuid(os.getuid()).pw_name)

    options, _args = parser.parse_args()

    opts = {}

    for key, val in six.iteritems(options.__dict__):
        opts[key] = val

    return opts


class Swarm(object):
    '''
    Create a swarm of minions
    '''
    def __init__(self, opts):
        self.opts = opts
        self.raet_port = 4550

        # If given a root_dir, keep the tmp files there as well
        if opts['root_dir']:
            tmpdir = os.path.join(opts['root_dir'], 'tmp')
        else:
            tmpdir = opts['root_dir']

        self.swarm_root = tempfile.mkdtemp(
            prefix='mswarm-root', suffix='.d',
            dir=tmpdir)

        if self.opts['transport'] == 'zeromq':
            self.pki = self._pki_dir()
        self.zfill = len(str(self.opts['minions']))

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
            '--log-file {1} --user {2}'.format(
                path, os.path.join(path, 'keys.log'), self.opts['user'],
            ), shell=True
        )
        print('Keys generated')
        return path

    def start(self):
        '''
        Start the magic!!
        '''
        if self.opts['master_too']:
            master_swarm = MasterSwarm(self.opts)
            master_swarm.start()
        minions = MinionSwarm(self.opts)
        minions.start_minions()
        print('Starting minions...')
        #self.start_minions()
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
        '''
        Tear it all down
        '''
        print('Killing any remaining running minions')
        subprocess.call(
            'pkill -KILL -f "python.*salt-minion"',
            shell=True
        )
        if self.opts['master_too']:
            print('Killing any remaining masters')
            subprocess.call(
                    'pkill -KILL -f "python.*salt-master"',
                    shell=True
            )
        if not self.opts['no_clean']:
            print('Remove ALL related temp files/directories')
            shutil.rmtree(self.swarm_root)
        print('Done')

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


class MinionSwarm(Swarm):
    '''
    Create minions
    '''
    def __init__(self, opts):
        super(MinionSwarm, self).__init__(opts)

    def start_minions(self):
        '''
        Iterate over the config files and start up the minions
        '''
        self.prep_configs()
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

    def mkconf(self, idx):
        '''
        Create a config file for a single minion
        '''
        minion_id = '{0}-{1}'.format(
                self.opts['name'],
                str(idx).zfill(self.zfill)
                )

        dpath = os.path.join(self.swarm_root, minion_id)
        os.makedirs(dpath)

        data = {
            'id': minion_id,
            'user': self.opts['user'],
            'cachedir': os.path.join(dpath, 'cache'),
            'master': self.opts['master'],
            'log_file': os.path.join(dpath, 'minion.log')
        }

        if self.opts['transport'] == 'zeromq':
            minion_pkidir = os.path.join(dpath, 'pki')
            os.makedirs(minion_pkidir)
            minion_pem = os.path.join(self.pki, 'minion.pem')
            minion_pub = os.path.join(self.pki, 'minion.pub')
            shutil.copy(minion_pem, minion_pkidir)
            shutil.copy(minion_pub, minion_pkidir)
            data['pki_dir'] = minion_pkidir
        elif self.opts['transport'] == 'raet':
            data['transport'] = 'raet'
            data['sock_dir'] = os.path.join(dpath, 'sock')
            data['raet_port'] = self.raet_port
            data['pki_dir'] = os.path.join(dpath, 'pki')
            self.raet_port += 1
        elif self.opts['transport'] == 'tcp':
            data['transport'] = 'tcp'

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

    def prep_configs(self):
        '''
        Prepare the confs set
        '''
        for idx in range(self.opts['minions']):
            self.mkconf(idx)


class MasterSwarm(Swarm):
    '''
    Create one or more masters
    '''
    def __init__(self, opts):
        super(MasterSwarm, self).__init__(opts)
        self.conf = os.path.join(self.swarm_root, 'master')

    def start(self):
        '''
        Prep the master start and fire it off
        '''
        # sys.stdout for no newline
        sys.stdout.write('Generating master config...')
        self.mkconf()
        print('done')

        sys.stdout.write('Starting master...')
        self.start_master()
        print('done')

    def start_master(self):
        '''
        Do the master start
        '''
        cmd = 'salt-master -c {0} --pid-file {1}'.format(
                self.conf,
                '{0}.pid'.format(self.conf)
                )
        if self.opts['foreground']:
            cmd += ' -l debug &'
        else:
            cmd += ' -d &'
        subprocess.call(cmd, shell=True)

    def mkconf(self):  # pylint: disable=W0221
        '''
        Make a master config and write it'
        '''
        data = {
            'log_file': os.path.join(self.conf, 'master.log'),
            'open_mode': True  # TODO Pre-seed keys
        }

        os.makedirs(self.conf)
        path = os.path.join(self.conf, 'master')

        with open(path, 'w+') as fp_:
            yaml.dump(data, fp_)

    def shutdown(self):
        print('Killing master')
        subprocess.call(
                'pkill -KILL -f "python.*salt-master"',
                shell=True
        )
        print('Master killed')

# pylint: disable=C0103
if __name__ == '__main__':
    swarm = Swarm(parse())
    try:
        swarm.start()
    finally:
        swarm.shutdown()
