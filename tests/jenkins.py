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
import time
import random
import shutil
import hashlib
import optparse
import subprocess

try:
    from salt.utils.nb_popen import NonBlockingPopen
except ImportError:
    # Salt not installed, or nb_popen was not yet shipped with it
    SALT_LIB = os.path.abspath(
        os.path.dirname(os.path.dirname(__file__))
    )
    if SALT_LIB not in sys.path:
        sys.path.insert(0, SALT_LIB)
    try:
        # Let's try using the current checked out code
        from salt.utils.nb_popen import NonBlockingPopen
    except ImportError:
        # Still an ImportError??? Let's use some "brute-force"
        sys.path.insert(
            0,
            os.path.join(SALT_LIB, 'salt', 'utils')
        )
        from nb_popen import NonBlockingPopen


def generate_vm_name(platform):
    '''
    Generate a random enough vm name
    '''
    if 'BUILD_NUMBER' in os.environ:
        random_part = 'BUILD{0:0>6}'.format(os.environ.get('BUILD_NUMBER'))
    else:
        random_part = hashlib.md5(
            str(random.randint(1, 100000000))).hexdigest()[:6]

    return 'ZJENKINS-{0}-{1}'.format(platform, random_part)


def delete_vm(options):
    '''
    Stop a VM
    '''
    cmd = 'salt-cloud -d {0} -y'.format(options.delete_vm)
    print('Running CMD: {0}'.format(cmd))
    sys.stdout.flush()

    proc = NonBlockingPopen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stream_stds=True
    )
    proc.poll_and_read_until_finish()
    proc.communicate()


def echo_parseable_environment(options):
    '''
    Echo NAME=VAL parseable output
    '''
    name = generate_vm_name(options.platform)
    output = (
        'JENKINS_SALTCLOUD_VM_PROVIDER={provider}\n'
        'JENKINS_SALTCLOUD_VM_PLATFORM={platform}\n'
        'JENKINS_SALTCLOUD_VM_NAME={name}\n').format(name=name,
                                                     provider=options.provider,
                                                     platform=options.platform)
    sys.stdout.write(output)
    sys.stdout.flush()


def download_unittest_reports(options):
    print('Downloading remote unittest reports...')
    sys.stdout.flush()

    if os.path.isdir('xml-test-reports'):
        shutil.rmtree('xml-test-reports')

    os.makedirs('xml-test-reports')

    cmds = (
        'salt {0} archive.tar zcvf /tmp/xml-test-reports.tar.gz \'*.xml\' cwd=/tmp/xml-unitests-output/',
        'salt {0} cp.push /tmp/xml-test-reports.tar.gz',
        'mv -f /var/cache/salt/master/minions/{0}/files/tmp/xml-test-reports.tar.gz {1}',
        'tar zxvf {1}/xml-test-reports.tar.gz -C {1}/xml-test-reports',
        'rm -f {1}/xml-test-reports.tar.gz'
    )

    vm_name = options.download_unittest_reports
    workspace = options.workspace
    for cmd in cmds:
        cmd = cmd.format(vm_name, workspace)
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
        if proc.returncode != 0:
            print(
                '\nFailed to execute command. Exit code: {0}'.format(
                    proc.returncode
                )
            )
        time.sleep(0.25)


def download_coverage_report(options):
    print('Downloading remote coverage report...')
    sys.stdout.flush()

    workspace = options.workspace
    vm_name = options.download_coverage_report

    if os.path.isfile(os.path.join(workspace, 'coverage.xml')):
        os.unlink(os.path.join(workspace, 'coverage.xml'))

    cmds = (
        'salt {0} archive.gzip /tmp/coverage.xml',
        'salt {0} cp.push /tmp/coverage.xml.gz',
        'gunzip /var/cache/salt/master/minions/{0}/files/tmp/coverage.xml.gz',
        'mv /var/cache/salt/master/minions/{0}/files/tmp/coverage.xml {1}'
    )

    for cmd in cmds:
        cmd = cmd.format(vm_name, workspace)
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
        if proc.returncode != 0:
            print(
                '\nFailed to execute command. Exit code: {0}'.format(
                    proc.returncode
                )
            )
        time.sleep(0.25)


def download_remote_logs(options):
    print('Downloading remote logs...')
    sys.stdout.flush()

    workspace = options.workspace
    vm_name = options.download_remote_logs

    for fname in ('salt-runtests.log', 'minion.log'):
        if os.path.isfile(os.path.join(workspace, fname)):
            os.unlink(os.path.join(workspace, fname))

    cmds = (
        'salt {0} archive.gzip /tmp/salt-runtests.log',
        'salt {0} archive.gzip /var/log/salt/minion',
        'salt {0} cp.push /tmp/salt-runtests.log.gz',
        'salt {0} cp.push /var/log/salt/minion.gz',
        'gunzip /var/cache/salt/master/minions/{0}/files/tmp/salt-runtests.log.gz',
        'gunzip /var/cache/salt/master/minions/{0}/files/var/log/salt/minion.gz',
        'mv /var/cache/salt/master/minions/{0}/files/tmp/salt-runtests.log {1}/salt-runtests.log',
        'mv /var/cache/salt/master/minions/{0}/files/var/log/salt/minion {1}/minion.log'
    )

    for cmd in cmds:
        cmd = cmd.format(vm_name, workspace)
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
        if proc.returncode != 0:
            print(
                '\nFailed to execute command. Exit code: {0}'.format(
                    proc.returncode
                )
            )
        time.sleep(0.25)


def run(opts):
    '''
    RUN!
    '''
    vm_name = os.environ.get(
        'JENKINS_SALTCLOUD_VM_NAME',
        generate_vm_name(opts.platform)
    )

    if opts.download_remote_reports:
        opts.download_coverage_report = vm_name
        opts.download_unittest_reports = vm_name

    cmd = (
        'salt-cloud -l debug --script-args "-D -n git {commit}" -p '
        '{provider}_{platform} {0}'.format(vm_name, **opts.__dict__)
    )
    print('Running CMD: {0}'.format(cmd))
    sys.stdout.flush()

    proc = NonBlockingPopen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stream_stds=True
    )
    proc.poll_and_read_until_finish()
    proc.communicate()

    retcode = proc.returncode
    if retcode != 0:
        print('Failed to bootstrap VM. Exit code: {0}'.format(retcode))
        sys.stdout.flush()
        if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
            delete_vm(vm_name)
        sys.exit(retcode)

    print('VM Bootstrapped. Exit code: {0}'.format(retcode))
    sys.stdout.flush()

    print('Sleeping for 5 seconds to allow the minion to breathe a little')
    sys.stdout.flush()
    time.sleep(5)

    # Run tests here
    cmd = (
        'salt -t 1800 {vm_name} state.sls {sls} pillar="{pillar}" '
        '--no-color'.format(
            sls=opts.sls,
            pillar=opts.pillar.format(commit=opts.commit),
            vm_name=vm_name,
            commit=opts.commit
        )
    )
    print('Running CMD: {0}'.format(cmd))
    sys.stdout.flush()

    #proc = NonBlockingPopen(
    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    #    stream_stds=True
    )
    #proc.poll_and_read_until_finish()
    stdout, stderr = proc.communicate()

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

    if opts.download_remote_reports:
        # Download unittest reports
        download_unittest_reports(opts)
        # Download coverage report
        download_coverage_report(opts)

    if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
        delete_vm(vm_name)
    return retcode


def parse():
    '''
    Parse the CLI options
    '''
    parser = optparse.OptionParser()
    parser.add_option(
        '-w', '--workspace',
        default=os.path.abspath(
            os.environ.get(
                'WORKSPACE',
                os.path.dirname(os.path.dirname(__file__))
            )
        ),
        help='Path the execution workspace'
    )
    parser.add_option(
        '--platform',
        default=os.environ.get('JENKINS_SALTCLOUD_VM_PLATFORM', None),
        help='The target platform, choose from:\ncent6\ncent5\nubuntu12.04')
    parser.add_option(
        '--provider',
        default=os.environ.get('JENKINS_SALTCLOUD_VM_PROVIDER', None),
        help='The vm provider')
    parser.add_option(
        '--commit',
        help='The git commit to track')
    parser.add_option(
        '--sls',
        default='testrun',
        help='The sls file to execute')
    parser.add_option(
        '--pillar',
        default='{{git_commit: {commit}}}',
        help='Pillar values to pass to the sls file')
    parser.add_option(
        '--no-clean',
        dest='clean',
        default=True,
        action='store_false',
        help='Clean up the built vm')
    parser.add_option(
        '--echo-parseable-environment',
        default=False,
        action='store_true',
        help='Print a parseable KEY=VAL output'
    )
    parser.add_option(
        '--delete-vm',
        default=None,
        help='Delete a running VM'
    )
    parser.add_option(
        '--download-remote-reports',
        default=False,
        action='store_true',
        help='Download remote reports when running remote \'testrun\' state'
    )
    parser.add_option(
        '--download-unittest-reports',
        default=None,
        help='Download the XML unittest results'
    )
    parser.add_option(
        '--download-coverage-report',
        default=None,
        help='Download the XML coverage reports'
    )
    parser.add_option(
        '--download-remote-logs',
        default=None,
        help='Download remote minion and runtests log files'
    )

    options, args = parser.parse_args()

    if options.delete_vm is not None and not options.commit:
        delete_vm(options)
        parser.exit(0)

    if options.download_unittest_reports is not None and not options.commit:
        download_unittest_reports(options)
        parser.exit(0)

    if options.download_coverage_report is not None and not options.commit:
        download_coverage_report(options)
        parser.exit(0)

    if options.download_remote_logs is not None and not options.commit:
        download_remote_logs(options)
        parser.exit(0)

    if not options.platform:
        parser.exit('--platform is required')

    if not options.provider:
        parser.exit('--provider is required')

    if options.echo_parseable_environment:
        echo_parseable_environment(options)
        parser.exit(0)

    if not options.commit:
        parser.exit('--commit is required')

    return options

if __name__ == '__main__':
    exit_code = run(parse())
    print('Exit Code: {0}'.format(exit_code))
    sys.exit(exit_code)
