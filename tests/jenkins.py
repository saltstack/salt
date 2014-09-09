# -*- coding: utf-8 -*-

#!/usr/bin/env python
'''
This script is used to test Salt from a Jenkins server, specifically
jenkins.saltstack.com.

This script is intended to be shell-centric!!
'''

# Import python libs
from __future__ import print_function
import os
import re
import sys
import json
import time
import random
import shutil
import hashlib
import optparse
import subprocess

# Import Salt libs
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

# Import 3rd-party libs
import yaml
try:
    import github
    HAS_GITHUB = True
except ImportError:
    HAS_GITHUB = False

SALT_GIT_URL = 'https://github.com/saltstack/salt.git'


def build_pillar_data(options):
    '''
    Build a YAML formatted string to properly pass pillar data
    '''
    pillar = {'test_transport': options.test_transport,
              'cloud_only': options.cloud_only}
    if options.test_git_commit is not None:
        pillar['test_git_commit'] = options.test_git_commit
    if options.test_git_url is not None:
        pillar['test_git_url'] = options.test_git_url
    if options.bootstrap_salt_url is not None:
        pillar['bootstrap_salt_url'] = options.bootstrap_salt_url
    if options.bootstrap_salt_commit is not None:
        pillar['bootstrap_salt_commit'] = options.bootstrap_salt_commit
    if options.pillar:
        pillar.update(dict(options.pillar))
    return yaml.dump(pillar, default_flow_style=True, indent=0, width=sys.maxint).rstrip()


def build_minion_target(options, vm_name):
    target = vm_name
    for grain in options.grain_target:
        target += ' and G@{0}'.format(grain)
    if options.grain_target:
        return '"{0}"'.format(target)
    return target


def generate_vm_name(options):
    '''
    Generate a random enough vm name
    '''
    if 'BUILD_NUMBER' in os.environ:
        random_part = 'BUILD{0:0>6}'.format(os.environ.get('BUILD_NUMBER'))
    else:
        random_part = hashlib.md5(
            str(random.randint(1, 100000000))).hexdigest()[:6]

    return '{0}-{1}-{2}'.format(options.vm_prefix, options.platform, random_part)


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
        stderr=subprocess.PIPE,
        stream_stds=True
    )
    proc.poll_and_read_until_finish()
    proc.communicate()


def echo_parseable_environment(options):
    '''
    Echo NAME=VAL parseable output
    '''
    output = []

    if options.platform:
        name = generate_vm_name(options)
        output.extend([
            'JENKINS_SALTCLOUD_VM_PLATFORM={0}'.format(options.platform),
            'JENKINS_SALTCLOUD_VM_NAME={0}'.format(name)
        ])

    if options.provider:
        output.append(
            'JENKINS_SALTCLOUD_VM_PROVIDER={0}'.format(options.provider)
        )

    if options.pull_request:
        # This is a Jenkins triggered Pull Request
        # We need some more data about the Pull Request available to the
        # environment
        if not HAS_GITHUB:
            print('# The script NEEDS the github python package installed')
            sys.stdout.write('\n'.join(output))
            sys.stdout.flush()
            return

        github_access_token_path = os.path.join(
            os.environ['JENKINS_HOME'], '.github_token'
        )
        if not os.path.isfile(github_access_token_path):
            print(
                '# The github token file({0}) does not exit'.format(
                    github_access_token_path
                )
            )
            sys.stdout.write('\n'.join(output))
            sys.stdout.flush()
            return

        GITHUB = github.Github(open(github_access_token_path).read().strip())
        REPO = GITHUB.get_repo('saltstack/salt')
        try:
            PR = REPO.get_pull(options.pull_request)
            output.extend([
                'SALT_PR_GIT_URL={0}'.format(PR.head.repo.clone_url),
                'SALT_PR_GIT_COMMIT={0}'.format(PR.head.sha)
            ])
            options.test_git_url = PR.head.repo.clone_url
            options.test_git_commit = PR.head.sha
        except ValueError:
            print('# Failed to get the PR id from the environment')

    sys.stdout.write('\n\n{0}\n\n'.format('\n'.join(output)))
    sys.stdout.flush()


def download_unittest_reports(options):
    print('Downloading remote unittest reports...')
    sys.stdout.flush()

    workspace = options.workspace
    xml_reports_path = os.path.join(workspace, 'xml-test-reports')
    if os.path.isdir(xml_reports_path):
        shutil.rmtree(xml_reports_path)

    os.makedirs(xml_reports_path)

    cmds = (
        'salt {0} archive.tar zcvf /tmp/xml-test-reports.tar.gz \'*.xml\' cwd=/tmp/xml-unitests-output/',
        'salt {0} cp.push /tmp/xml-test-reports.tar.gz',
        'mv -f /var/cache/salt/master/minions/{1}/files/tmp/xml-test-reports.tar.gz {2} && '
        'tar zxvf {2}/xml-test-reports.tar.gz -C {2}/xml-test-reports && '
        'rm -f {2}/xml-test-reports.tar.gz'
    )

    vm_name = options.download_unittest_reports
    for cmd in cmds:
        cmd = cmd.format(build_minion_target(options, vm_name), vm_name, workspace)
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
        'gunzip /var/cache/salt/master/minions/{1}/files/tmp/coverage.xml.gz',
        'mv /var/cache/salt/master/minions/{1}/files/tmp/coverage.xml {2}'
    )

    for cmd in cmds:
        cmd = cmd.format(build_minion_target(options, vm_name), vm_name, workspace)
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

    if not options.remote_log_path:
        options.remote_log_path = [
            '/tmp/salt-runtests.log',
            '/var/log/salt/minion'
        ]

    cmds = []

    for remote_log in options.remote_log_path:
        cmds.extend([
            'salt {{0}} archive.gzip {0}'.format(remote_log),
            'salt {{0}} cp.push {0}.gz'.format(remote_log),
            'gunzip /var/cache/salt/master/minions/{{1}}/files{0}.gz'.format(remote_log),
            'mv /var/cache/salt/master/minions/{{1}}/files{0} {{2}}/{1}'.format(
                remote_log,
                '{0}{1}'.format(
                    os.path.basename(remote_log),
                    '' if remote_log.endswith('.log') else '.log'
                )
            )
        ])

    for cmd in cmds:
        cmd = cmd.format(build_minion_target(options, vm_name), vm_name, workspace)
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
        generate_vm_name(opts)
    )

    if opts.download_remote_reports:
        opts.download_coverage_report = vm_name
        opts.download_unittest_reports = vm_name

    if opts.bootstrap_salt_commit is not None:
        if opts.bootstrap_salt_url is None:
            opts.bootstrap_salt_url = 'https://github.com/saltstack/salt.git'
        cmd = (
            'salt-cloud -l debug'
            ' --script-args "-D -g {bootstrap_salt_url} -n git {1}"'
            ' -p {provider}_{platform} {0}'.format(
                vm_name,
                os.environ.get(
                    'SALT_MINION_BOOTSTRAP_RELEASE',
                    opts.bootstrap_salt_commit
                ),
                **opts.__dict__
            )
        )
    else:
        cmd = (
            'salt-cloud -l debug'
            ' --script-args "-D -n git {1}" -p {provider}_{platform} {0}'.format(
                vm_name,
                os.environ.get(
                    'SALT_MINION_BOOTSTRAP_RELEASE',
                    opts.bootstrap_salt_commit
                ),
                **opts.__dict__
            )
        )
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

    retcode = proc.returncode
    if retcode != 0:
        print('Failed to bootstrap VM. Exit code: {0}'.format(retcode))
        sys.stdout.flush()
        if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
            delete_vm(opts)
        sys.exit(retcode)

    print('VM Bootstrapped. Exit code: {0}'.format(retcode))
    sys.stdout.flush()

    print('Sleeping for 5 seconds to allow the minion to breathe a little')
    sys.stdout.flush()
    time.sleep(5)

    if opts.bootstrap_salt_commit is not None:
        # Let's find out if the installed version matches the passed in pillar
        # information
        print('Grabbing bootstrapped minion version information ... ')
        cmd = 'salt -t 100 {0} --out json test.version'.format(build_minion_target(opts, vm_name))
        print('Running CMD: {0}'.format(cmd))
        sys.stdout.flush()
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _ = proc.communicate()

        retcode = proc.returncode
        if retcode != 0:
            print('Failed to get the bootstrapped minion version. Exit code: {0}'.format(retcode))
            sys.stdout.flush()
            if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

        if not stdout.strip():
            print('Failed to get the bootstrapped minion version(no output). Exit code: {0}'.format(retcode))
            sys.stdout.flush()
            if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

        try:
            version_info = json.loads(stdout.strip())
            bootstrap_minion_version = os.environ.get(
                'SALT_MINION_BOOTSTRAP_RELEASE',
                opts.bootstrap_salt_commit[:7]
            )
            if bootstrap_minion_version not in version_info[vm_name]:
                print('\n\nATTENTION!!!!\n')
                print('The boostrapped minion version commit does not contain the desired commit:')
                print(' {0!r} does not contain {1!r}'.format(version_info[vm_name], bootstrap_minion_version))
                print('\n\n')
                sys.stdout.flush()
                #if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
                #    delete_vm(opts)
                #sys.exit(retcode)
            else:
                print('matches!')
        except ValueError:
            print('Failed to load any JSON from {0!r}'.format(stdout.strip()))

    if opts.cloud_only:
        # Run Cloud Provider tests preparation SLS
        time.sleep(3)
        cmd = (
            'salt -t 900 {target} state.sls {cloud_prep_sls} pillar="{pillar}" '
            '--no-color'.format(
                target=build_minion_target(opts, vm_name),
                cloud_prep_sls='cloud-only',
                pillar=build_pillar_data(opts),
            )
        )
    else:
        # Run standard preparation SLS
        time.sleep(3)
        cmd = (
            'salt -t 1800 {target} state.sls {prep_sls} pillar="{pillar}" '
            '--no-color'.format(
                target=build_minion_target(opts, vm_name),
                prep_sls=opts.prep_sls,
                pillar=build_pillar_data(opts),
            )
        )
    print('Running CMD: {0}'.format(cmd))
    sys.stdout.flush()

    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = proc.communicate()

    if stdout:
        print(stdout)
    sys.stdout.flush()
    if stderr:
        print(stderr)
    sys.stderr.flush()

    retcode = proc.returncode
    if retcode != 0:
        print('Failed to execute the preparation SLS file. Exit code: {0}'.format(retcode))
        sys.stdout.flush()
        if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
            delete_vm(opts)
        sys.exit(retcode)

    if opts.cloud_only:
        time.sleep(3)
        # Run Cloud Provider tests pillar preparation SLS
        cmd = (
            'salt -t 600 {target} state.sls {cloud_prep_sls} pillar="{pillar}" '
            '--no-color'.format(
                target=build_minion_target(opts, vm_name),
                cloud_prep_sls='cloud-test-configs',
                pillar=build_pillar_data(opts),
            )
        )
        print('Running CMD: {0}'.format(cmd))
        sys.stdout.flush()

        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        stdout, stderr = proc.communicate()

        if stdout:
            # DO NOT print the state return here!
            print('Cloud configuration files provisioned via pillar.')
        sys.stdout.flush()
        if stderr:
            print(stderr)
        sys.stderr.flush()

        retcode = proc.returncode
        if retcode != 0:
            print('Failed to execute the preparation SLS file. Exit code: {0}'.format(retcode))
            sys.stdout.flush()
            if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

    if opts.prep_sls_2 is not None:
        time.sleep(3)

        # Run the 2nd preparation SLS
        cmd = (
            'salt -t 30 {target} state.sls {prep_sls_2} pillar="{pillar}" '
            '--no-color'.format(
                prep_sls_2=opts.prep_sls_2,
                pillar=build_pillar_data(opts),
                target=build_minion_target(opts, vm_name),
            )
        )
        print('Running CMD: {0}'.format(cmd))
        sys.stdout.flush()

        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        stdout, stderr = proc.communicate()

        if stdout:
            print(stdout)
        sys.stdout.flush()
        if stderr:
            print(stderr)
        sys.stderr.flush()

        retcode = proc.returncode
        if retcode != 0:
            print('Failed to execute the 2nd preparation SLS file. Exit code: {0}'.format(retcode))
            sys.stdout.flush()
            if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

    # Run remote checks
    if opts.test_git_url is not None:
        time.sleep(1)
        # Let's find out if the cloned repository if checked out from the
        # desired repository
        print('Grabbing the cloned repository remotes information ... ')
        cmd = 'salt -t 100 {0} --out json git.remote_get /testing'.format(build_minion_target(opts, vm_name))
        print('Running CMD: {0}'.format(cmd))
        sys.stdout.flush()
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        proc.communicate()

        retcode = proc.returncode
        if retcode != 0:
            print('Failed to get the cloned repository remote. Exit code: {0}'.format(retcode))
            sys.stdout.flush()
            if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

        if not stdout:
            print('Failed to get the cloned repository remote(no output). Exit code: {0}'.format(retcode))
            sys.stdout.flush()
            if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

        try:
            remotes_info = json.loads(stdout.strip())
            if remotes_info is None or remotes_info[vm_name] is None or opts.test_git_url not in remotes_info[vm_name]:
                print('The cloned repository remote is not the desired one:')
                print(' {0!r} is not in {1}'.format(opts.test_git_url, remotes_info))
                sys.stdout.flush()
                if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
                    delete_vm(opts)
                sys.exit(retcode)
            print('matches!')
        except ValueError:
            print('Failed to load any JSON from {0!r}'.format(stdout.strip()))

    if opts.test_git_commit is not None:
        time.sleep(1)

        # Let's find out if the cloned repository is checked out at the desired
        # commit
        print('Grabbing the cloned repository commit information ... ')
        cmd = 'salt -t 100 {0} --out json git.revision /testing'.format(build_minion_target(opts, vm_name))
        print('Running CMD: {0}'.format(cmd))
        sys.stdout.flush()
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _ = proc.communicate()
        sys.stdout.flush()

        retcode = proc.returncode
        if retcode != 0:
            print('Failed to get the cloned repository revision. Exit code: {0}'.format(retcode))
            sys.stdout.flush()
            if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

        if not stdout:
            print('Failed to get the cloned repository revision(no output). Exit code: {0}'.format(retcode))
            sys.stdout.flush()
            if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

        try:
            revision_info = json.loads(stdout.strip())
            if revision_info[vm_name][7:] != opts.test_git_commit[7:]:
                print('The cloned repository commit is not the desired one:')
                print(' {0!r} != {1!r}'.format(revision_info[vm_name][:7], opts.test_git_commit[:7]))
                sys.stdout.flush()
                if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
                    delete_vm(opts)
                sys.exit(retcode)
            print('matches!')
        except ValueError:
            print('Failed to load any JSON from {0!r}'.format(stdout.strip()))

    # Run tests here
    time.sleep(3)
    cmd = (
        'salt -t 1800 {target} state.sls {sls} pillar="{pillar}" --no-color'.format(
            sls=opts.sls,
            pillar=build_pillar_data(opts),
            target=build_minion_target(opts, vm_name),
        )
    )
    print('Running CMD: {0}'.format(cmd))
    sys.stdout.flush()

    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = proc.communicate()

    if stdout:
        print(stdout)
    sys.stdout.flush()
    if stderr:
        print(stderr)
    sys.stderr.flush()

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
        delete_vm(opts)
    return retcode


def parse():
    '''
    Parse the CLI options
    '''
    parser = optparse.OptionParser()
    parser.add_option(
        '--vm-prefix',
        default=os.environ.get('JENKINS_VM_NAME_PREFIX', 'ZJENKINS'),
        help='The bootstrapped machine name prefix'
    )
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
        '--bootstrap-salt-url',
        default=None,
        help='The salt git repository url used to boostrap a minion')
    parser.add_option(
        '--bootstrap-salt-commit',
        default=None,
        help='The salt git commit used to boostrap a minion')
    parser.add_option(
        '--test-git-url',
        default=None,
        help='The testing git repository url')
    parser.add_option(
        '--test-git-commit',
        default=None,
        help='The testing git commit to track')
    parser.add_option(
        '--test-transport',
        default='zeromq',
        choices=('zeromq', 'raet'),
        help='Set to raet to run integration tests with raet transport. Default: %default')
    parser.add_option(
        '--prep-sls',
        default='git.salt',
        help='The sls file to execute to prepare the system')
    parser.add_option(
        '--prep-sls-2',
        default=None,
        help='An optional 2nd system preparation SLS')
    parser.add_option(
        '--sls',
        default='testrun-no-deps',
        help='The final sls file to execute')
    parser.add_option(
        '--pillar',
        action='append',
        nargs=2,
        help='Pillar (key, value)s to pass to the sls file. '
             'Example: \'--pillar pillar_key pillar_value\'')
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
        '--pull-request',
        type=int,
        help='Include the PR info only'
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
        '--remote-log-path',
        action='append',
        default=[],
        help='Provide additional log paths to download from remote minion'
    )
    parser.add_option(
        '--download-remote-logs',
        default=None,
        help='Download remote minion and runtests log files'
    )
    parser.add_option(
        '--grain-target',
        action='append',
        default=[],
        help='Match minions using compound matchers, the minion ID, plus the passed grain.'
    )
    parser.add_option(
        '--cloud-only',
        default=False,
        action='store_true',
        help='Run the cloud provider tests only.'
    )

    options, args = parser.parse_args()

    if options.delete_vm is not None and not options.test_git_commit:
        delete_vm(options)
        parser.exit(0)

    if options.download_unittest_reports is not None and not options.test_git_commit:
        download_unittest_reports(options)
        parser.exit(0)

    if options.download_coverage_report is not None and not options.test_git_commit:
        download_coverage_report(options)
        parser.exit(0)

    if options.download_remote_logs is not None and not options.test_git_commit:
        download_remote_logs(options)
        parser.exit(0)

    if not options.platform and not options.pull_request:
        parser.exit('--platform or --pull-request is required')

    if not options.provider and not options.pull_request:
        parser.exit('--provider or --pull-request is required')

    if options.echo_parseable_environment:
        echo_parseable_environment(options)
        parser.exit(0)

    if not options.test_git_commit and not options.pull_request:
        parser.exit('--commit or --pull-request is required')

    return options

if __name__ == '__main__':
    exit_code = run(parse())
    print('Exit Code: {0}'.format(exit_code))
    sys.exit(exit_code)
