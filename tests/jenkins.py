#!/usr/bin/env python
'''
This script is used to test Salt from a Jenkins server, specifically
jenkins.saltstack.com.

This script is intended to be shell-centric!!
'''

# Import python libs
import os
import re
import sys
import subprocess
import hashlib
import random
import optparse

try:
    from salt.utils.nb_popen import NonBlockingPopen
except ImportError:
    # Salt not installed, or nb_popen was not yet shipped with it
    salt_lib = os.path.abspath(
        os.path.dirname(os.path.dirname(__file__))
    )
    if salt_lib not in sys.path:
        sys.path.insert(0, salt_lib)
    try:
        # Let's try using the current checked out code
        from salt.utils.nb_popen import NonBlockingPopen
    except ImportError:
        # Still an ImportError??? Let's use some "brute-force"
        sys.path.insert(
            0,
            os.path.join(salt_lib, 'salt', 'utils')
        )
        from nb_popen import NonBlockingPopen



def run(platform, provider, commit, clean):
    '''
    RUN!
    '''
    htag = hashlib.md5(str(random.randint(1, 100000000))).hexdigest()[:6]
    vm_name = 'ZZZ{0}{1}'.format(platform, htag)
    cmd = 'salt-cloud -l debug --script-args "-D -n git {0}" -p {1}_{2} {3}'.format(
            commit, provider, platform, vm_name)
    print('Running CMD: {0}'.format(cmd))
    sys.stdout.flush()

    proc = NonBlockingPopen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stream_stds=True
    )
    proc.poll_and_read_until_finish()
    proc.communicate()
    if proc.returncode > 0:
        print('Failed to bootstrap VM. Exit code: {0}'.format(proc.returncode))
        sys.stdout.flush()
        sys.exit(proc.returncode)

    print('VM Bootstrapped. Exit code: {0}'.format(proc.returncode))
    sys.stdout.flush()

    # Run tests here
    cmd = 'salt -t 1800 {0} state.sls testrun pillar="{{git_commit: {1}}}" --no-color'.format(
                vm_name,
                commit)
    print('Running CMD: {0}'.format(cmd))
    sys.stdout.flush()

    proc = NonBlockingPopen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stream_stds=True
    )
    proc.poll_and_read_until_finish()
    stdout, stderr = proc.communicate()

    if stderr:
        print(stderr)
    if stdout:
        print(stdout)

    sys.stdout.flush()

    try:
        match = re.search(r'Test Suite Exit Code: (?P<exitcode>[\d]+)', stdout)
        retcode = int(match.group('exitcode'))
    except AttributeError:
        # No regex matching
        retcode = 1
    except ValueError:
        # Not a number!?
        retcode = 1
    except TypeError:
        # No output!?
        retcode = 1
        if stdout:
            # Anything else, raise the exception
            raise

    # Clean up the vm
    if clean:
        cmd = 'salt-cloud -d {0} -y'.format(vm_name)
        print('Running CMD: {0}'.format(cmd))
        sys.stdout.flush()

        proc = NonBlockingPopen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stream_stds=True
        )
        proc.poll_and_read_until_finish()
        proc.communicate()
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
