#!/usr/bin/env python
'''
This script is used to test salt from a jenkins server, specifically
jenkins.satstack.com.

This script is intended to be shell centric!!
'''

# Import python libs
import sys
import subprocess
import hashlib
import random
import optparse


def run(platform, provider, commit, clean):
    '''
    RUN!
    '''
    htag = hashlib.md5(str(random.randint(1, 100000000))).hexdigest()[:6] 
    vm_name = '{0}{1}'.format(platform, htag)
    cmd = 'salt-cloud -p {0}_{1} {2}'.format(provider, platform, vm_name)
    print('Running CMD: {0}'.format(cmd))
    subprocess.call(
            cmd,
            shell=True)
    # Run tests here
    cmd = 'salt {0} state.sls testrun pillar="{{git_commit: {1}}}"'.format(
                vm_name,
                commit),
    print('Running CMD: {0}'.format(cmd))
    subprocess.call(
            cmd,
            shell=True)
    # Clean up the vm
    if clean:
        cmd = 'salt-cloud -d {0} -y'.format(vm_name),
        print('Running CMD: {0}'.format(cmd))
        subprocess.call(
                cmd,
                shell=True)
    return 0


def parse():
    '''
    Parse the cli options
    '''
    parser = optparse.OptionParser()
    parser.add_option('--platform',
            dest='platform',
            help='The target platform, choose from:\ncent6\ncent5\nubuntu12.04')
    parser.add_option('--provider',
            dest='provider',
            help='The vm provider')
    parser.add_option('--commit',
            dest='commit',
            help='The git commit to track')
    parser.add_option('--clean',
            dest='clean',
            default=True,
            action='store_false',
            help='Clean up the built vm')
    options, args = parser.parse_args()
    return options.__dict__

if __name__ == '__main__':
    opts = parse()
    exit_code = run(**opts)
    print('Exit Code: {0}'.format(exit_code))
    sys.exit(exit_code)
