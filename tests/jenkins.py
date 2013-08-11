#!/usr/bin/env python
'''
This script is used to test Salt from a Jenkins server, specifically
jenkins.saltstack.com.

This script is intended to be shell-centric!!
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
    vm_name = 'ZZZ{0}{1}'.format(platform, htag)
    cmd = 'salt-cloud --script-args "git {0}" -p {1}_{2} {3}'.format(
            commit, provider, platform, vm_name)
    print('Running CMD: {0}'.format(cmd))
    subprocess.call(
            cmd,
            shell=True)
    # Run tests here
    cmd = 'salt {0} state.sls testrun pillar="{{git_commit: {1}}}" --no-color'.format(
                vm_name,
                commit),
    print('Running CMD: {0}'.format(cmd))
    out = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE).communicate()[0]
    print(out)
    if 'Result:    False' in out:
        retcode = 1
    else:
        retcode = 0
    # Clean up the vm
    if clean:
        cmd = 'salt-cloud -d {0} -y'.format(vm_name),
        print('Running CMD: {0}'.format(cmd))
        subprocess.call(
                cmd,
                shell=True)
    return retcode


def parse():
    '''
    Parse the CLI options
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
    parser.add_option('--no-clean',
            dest='clean',
            default=True,
            action='store_false',
            help='Clean up the built vm')
    options, args = parser.parse_args()
    if not options.platform:
        parser.exit('--platform is required')
    if not options.provider:
        parser.exit('--provider is required')
    if not options.commit:
        parser.exit('--commit is required')
    return options.__dict__

if __name__ == '__main__':
    opts = parse()
    exit_code = run(**opts)
    print('Exit Code: {0}'.format(exit_code))
    sys.exit(exit_code)
