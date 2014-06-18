#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    jenkins-ng
    ~~~~~~~~~~

    Jenkins execution helper script
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
import argparse
import requests
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
        from nb_popen import NonBlockingPopen  # pylint: disable=F0401

# Import 3rd-party libs
import yaml

SALT_GIT_URL = 'https://github.com/saltstack/salt.git'


class GetPullRequestAction(argparse.Action):
    '''
    Load the required pull request information
    '''

    def __call__(self, parser, namespace, values, option_string=None):
        headers = {}
        url = 'https://api.github.com/repos/saltstack/salt/pulls/{0}'.format(values)

        github_access_token_path = os.path.join(
            os.environ.get('JENKINS_HOME', os.path.expanduser('~')),
            '.github_token'
        )
        if os.path.isfile(github_access_token_path):
            headers = {
                'Authorization': 'token {0}'.format(
                    open(github_access_token_path).read().strip()
                )
            }

        http_req = requests.get(url, headers=headers)
        if http_req.status_code != 200:
            parser.error(
                'Unable to get the pull request: {0[message]}'.format(http_req.json())
            )

        pr_details = http_req.json()
        setattr(namespace, 'pull_request_git_url', pr_details['head']['repo']['clone_url'])
        setattr(namespace, 'pull_request_git_commit', pr_details['head']['sha'])


def generate_vm_name(options):
    '''
    Generate a random enough vm name
    '''
    if 'BUILD_NUMBER' in os.environ:
        random_part = 'BUILD{0:0>6}'.format(os.environ.get('BUILD_NUMBER'))
    else:
        random_part = hashlib.md5(
            str(random.randint(1, 100000000))).hexdigest()[:6]

    return '{0}-{1}-{2}'.format(options.vm_prefix, options.vm_source, random_part)


def get_vm_name(options):
    '''
    Return the VM name
    '''
    return os.environ.get('JENKINS_VM_NAME', generate_vm_name(options))


def get_minion_external_address(options):
    '''
    Get and store the remote minion external IP
    '''
    if 'minion_external_ip' in options:
        return options.minion_external_ip

    sync_minion(options)

    cmd = []
    if options.peer:
        cmd.extend(['salt-call', '--out=json', 'publish.publish'])
    else:
        cmd.extend(['salt', '--out=json'])

    cmd.extend([
        options.vm_name,
        'grains.get',
        'external_ip'
    ])

    cmd = ' '.join(cmd)
    print('Running CMD: {0!r}'.format(cmd))
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
        print('Failed to get the minion external IP. Exit code: {0}'.format(retcode))
        sys.stdout.flush()
        if options.delete_vm:
            delete_vm(options)
        sys.exit(retcode)

    if not stdout.strip():
        print('Failed to get the minion external IP(no output). Exit code: {0}'.format(retcode))
        sys.stdout.flush()
        if options.delete_vm:
            delete_vm(options)
        sys.exit(retcode)

    try:
        external_ip_info = json.loads(stdout.strip())
        if options.peer:
            external_ip = external_ip_info['local']
        else:
            external_ip = external_ip_info[options.vm_name]
    except ValueError:
        print('Failed to load any JSON from {0!r}'.format(stdout.strip()))

    setattr(options, 'minion_external_ip', external_ip)
    return external_ip


def get_minion_python_executable(options):
    '''
    Get and store the remote minion python executable
    '''
    if 'minion_python_executable' in options:
        return options.minion_python_executable

    sync_minion(options)

    cmd = []
    if options.peer:
        cmd.extend(['salt-call', '--out=json', 'publish.publish'])
    else:
        cmd.extend(['salt', '--out=json'])

    cmd.extend([
        options.vm_name,
        'grains.get',
        'pythonexecutable'
    ])

    cmd = ' '.join(cmd)
    print('Running CMD: {0!r}'.format(cmd))

    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout, _ = proc.communicate()

    retcode = proc.returncode
    if retcode != 0:
        print('Failed to get the minion python executable. Exit code: {0}'.format(retcode))
        sys.stdout.flush()
        if options.delete_vm:
            delete_vm(options)
        sys.exit(retcode)

    if not stdout.strip():
        print('Failed to get the minion python executable(no output). Exit code: {0}'.format(retcode))
        sys.stdout.flush()
        if options.delete_vm:
            delete_vm(options)
        sys.exit(retcode)

    try:
        python_executable = json.loads(stdout.strip())
        if options.peer:
            python_executable = python_executable['local']
        else:
            python_executable = python_executable[options.vm_name]
    except ValueError:
        print('Failed to load any JSON from {0!r}'.format(stdout.strip()))

    setattr(options, 'minion_python_executable', python_executable)
    return python_executable


def sync_minion(options):
    if 'salt_minion_synced' not in options:
        cmd = []
        if options.peer:
            cmd.extend(['salt-call', 'publish.runner'])
        else:
            cmd.append('salt')

        cmd.extend([
            build_minion_target(options),
            'saltutil.sync_all'
        ])
        print('Running CMD: {0!r}'.format(' '.join(cmd)))
        sys.stdout.flush()

        proc = NonBlockingPopen(
            ' '.join(cmd),
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
            sys.exit(proc.returncode)

        setattr(options, 'salt_minion_synced', 'yes')


def to_cli_yaml(data):
    '''
    Return a YAML string for CLI usage
    '''
    return yaml.dump(data, default_flow_style=True, indent=0, width=sys.maxint).rstrip()


def build_pillar_data(options):
    '''
    Build a YAML formatted string to properly pass pillar data
    '''
    pillar = {'test_transport': options.test_transport}
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
    return to_cli_yaml(pillar)


def build_minion_target(options):
    '''
    Build the minion target string
    '''
    target = options.vm_name
    for grain in options.grain_target:
        target += ' and G@{0}'.format(grain)
    if options.grain_target and not options.peer:
        target = '-C "{0}"'.format(target)
    return target


def delete_vm(options):
    '''
    Stop a VM
    '''
    cmd = []
    if options.peer:
        cmd.extend(['salt-call', 'publish.runner'])
    else:
        cmd.append('salt-run')
    if options.lxc:
        cmd.append('lxc.purge')
    else:
        cmd.append('cloud.destroy')

    cmd.append(options.vm_name)
    print('Running CMD: {0!r}'.format(' '.join(cmd)))
    sys.stdout.flush()

    proc = NonBlockingPopen(
        ' '.join(cmd),
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stream_stds=True
    )
    proc.poll_and_read_until_finish()
    proc.communicate()


def download_unittest_reports(options):
    '''
    Download the generated unit test reports from minion
    '''
    print('Downloading remote unittest reports...')
    sys.stdout.flush()

    xml_reports_path = os.path.join(options.workspace, 'xml-test-reports')
    if os.path.isdir(xml_reports_path):
        shutil.rmtree(xml_reports_path)

    if options.scp:
        cmds = (
            ' '.join(build_scp_command(options,
                                       '-r',
                                       'root@{0}:/tmp/xml-unitests-output/*'.format(
                                           get_minion_external_address(options)
                                       ),
                                       os.path.join(options.workspace, 'xml-test-reports'))),
        )
    else:
        os.makedirs(xml_reports_path)
        cmds = (
            '{0} {1} archive.tar zcvf /tmp/xml-test-reports.tar.gz \'*.xml\' cwd=/tmp/xml-unitests-output/',
            '{0} {1} cp.push /tmp/xml-test-reports.tar.gz',
            'mv -f /var/cache/salt/master/minions/{2}/files/tmp/xml-test-reports.tar.gz {3} && '
            'tar zxvf {3}/xml-test-reports.tar.gz -C {3}/xml-test-reports && '
            'rm -f {3}/xml-test-reports.tar.gz'
        )

    for cmd in cmds:
        cmd = cmd.format(
            'salt-call publish.publish' if options.lxc else 'salt',
            build_minion_target(options),
            options.vm_name,
            options.workspace
        )
        print('Running CMD: {0!r}'.format(cmd))
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
    '''
    Download the generated coverage report from minion
    '''
    print('Downloading remote coverage report...')
    sys.stdout.flush()

    if os.path.isfile(os.path.join(options.workspace, 'coverage.xml')):
        os.unlink(os.path.join(options.workspace, 'coverage.xml'))

    if options.scp:
        cmds = (
            ' '.join(build_scp_command(options,
                                       'root@{0}:/tmp/coverage.xml'.format(
                                           get_minion_external_address(options)
                                       ),
                                       os.path.join(options.workspace, 'coverage.xml'))),
        )
    else:
        cmds = (
            '{0} {1} archive.gzip /tmp/coverage.xml',
            '{0} {1} cp.push /tmp/coverage.xml.gz',
            'gunzip /var/cache/salt/master/minions/{2}/files/tmp/coverage.xml.gz',
            'mv /var/cache/salt/master/minions/{2}/files/tmp/coverage.xml {3}'
        )

    for cmd in cmds:
        cmd = cmd.format(
            'salt-call publish.publish' if options.lxc else 'salt',
            build_minion_target(options),
            options.vm_name,
            options.workspace
        )
        print('Running CMD: {0!r}'.format(cmd))
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
    '''
    Download the generated logs from minion
    '''
    print('Downloading remote logs...')
    sys.stdout.flush()

    for fname in ('salt-runtests.log', 'minion.log'):
        if os.path.isfile(os.path.join(options.workspace, fname)):
            os.unlink(os.path.join(options.workspace, fname))

    if not options.remote_log_path:
        options.remote_log_path = [
            '/tmp/salt-runtests.log',
            '/var/log/salt/minion'
        ]

    cmds = []

    if options.scp:
        for remote_log in options.remote_log_path:
            cmds.append(
                ' '.join(build_scp_command(options,
                                           '-r',
                                           'root@{0}:{1}'.format(
                                               get_minion_external_address(options),
                                               remote_log
                                           ),
                                           os.path.join(
                                               options.workspace,
                                               '{0}{1}'.format(
                                                   os.path.basename(remote_log),
                                                   '' if remote_log.endswith('.log') else '.log'
                                                )
                                           )))
            )
    else:
        for remote_log in options.remote_log_path:
            cmds.extend([
                '{{0}} {{1}} archive.gzip {0}'.format(remote_log),
                '{{0}} {{1}} cp.push {0}.gz'.format(remote_log),
                'gunzip /var/cache/salt/master/minions/{{2}}/files{0}.gz'.format(remote_log),
                'mv /var/cache/salt/master/minions/{{2}}/files{0} {{3}}/{1}'.format(
                    remote_log,
                    '{0}{1}'.format(
                        os.path.basename(remote_log),
                        '' if remote_log.endswith('.log') else '.log'
                    )
                )
            ])

    for cmd in cmds:
        cmd = cmd.format(
            'salt-call publish.publish' if options.lxc else 'salt',
            build_minion_target(options),
            options.vm_name,
            options.workspace
        )
        print('Running CMD: {0!r}'.format(cmd))
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


def echo_parseable_environment(options):
    '''
    Echo NAME=VAL parseable output
    '''
    output = [
        'JENKINS_VM_NAME={0}'.format(options.vm_name),
        'JENKINS_VM_SOURCE={0}'.format(options.vm_source),
    ]
    if 'pull_request_git_url' in options and 'pull_request_git_commit' in options:
        output.extend([
            'SALT_PR_GIT_URL={0}'.format(options.pull_request_git_url),
            'SALT_PR_GIT_COMMIT={0}'.format(options.pull_request_git_commit)
        ])

    sys.stdout.write('\n\n{0}\n\n'.format('\n'.join(output)))
    sys.stdout.flush()


def prepare_ssh_access(options):
    '''
    Generate a temporary SSH key, valid for one hour, and set it as an
    authorized key in the minion's root user account on the remote system.
    '''
    print('Generating temporary SSH Key')
    ssh_key_path = os.path.join(options.workspace, 'jenkins_ssh_key_test')
    subprocess.call(
        'ssh-keygen -t ecdsa -b 521 -C "$(whoami)@$(hostname)-$(date --rfc-3339=seconds)" '
        '-f {0} -N \'\' -V -10m:+1h'.format(ssh_key_path),
        shell=True,
    )
    cmd = []
    if options.peer:
        cmd.extend(['salt-call', 'publish.publish'])
    else:
        cmd.append('salt')
    pub_key_contents = open('{0}.pub'.format(ssh_key_path)).read().strip()
    enc, key, comment = pub_key_contents.split(' ', 2)
    cmd.extend([
        build_minion_target(options),
        'ssh.set_auth_key',
        'root',
        '{0!r}'.format(key),
        'enc={0}'.format(enc),
        'comment={0!r}'.format(comment)
    ])

    cmd = ' '.join(cmd)
    print('Running CMD: {0!r}'.format(cmd))
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


def build_scp_command(options, *arguments):
    '''
    Build the SCP command with the required options
    '''
    return [
        'scp',
        '-i',
        os.path.join(options.workspace, 'jenkins_ssh_key_test'),
        # Don't add new hosts to the host key database
        '-oStrictHostKeyChecking=no',
        # Set hosts key database path to /dev/null, ie, non-existing
        '-oUserKnownHostsFile=/dev/null',
        # Don't re-use the SSH connection. Less failures.
        '-oControlPath=none',
    ] + list(arguments)


def main():
    '''
    Main script execution
    '''
    parser = argparse.ArgumentParser(
        description='Jenkins execution helper'
    )
    parser.add_argument(
        '-w', '--workspace',
        default=os.path.abspath(os.environ.get('WORKSPACE', os.getcwd())),
        help='Path to the execution workspace'
    )

    # Output Options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        '--no-color',
        '--no-colour',
        action='store_true',
        default=False,
        help='Don\'t use colors'
    )
    output_group.add_argument(
        '--echo-parseable-output',
        action='store_true',
        default=False,
        help='Print Jenkins related environment variables and exit'
    )
    output_group.add_argument(
        '--pull-request',
        type=int,
        action=GetPullRequestAction,
        default=None,
        help='Include the Pull Request information in parseable output'
    )

    # Deployment Selection
    deployment_group = parser.add_argument_group('Deployment Selection')
    deployment_group.add_argument(
        '--pre-mortem',
        action='store_true',
        default=False,
        help='Don\'t try to deploy an new VM. Consider a VM deployed and only '
             'execute post test suite execution commands. Right before killing the VM'
    )
    deployment_group_mutually_exclusive = deployment_group.add_mutually_exclusive_group()
    deployment_group_mutually_exclusive.add_argument(
        '--cloud',
        action='store_true',
        default=True,
        help='Salt Cloud Deployment'
    )
    deployment_group_mutually_exclusive.add_argument(
        '--lxc',
        action='store_true',
        default=False,
        help='Salt LXC Deployment'
    )
    deployment_group.add_argument(
        '--lxc-host',
        default=None,
        help='The host where to deploy the LXC VM'
    )

    # Execution Selections
    execution_group = parser.add_argument_group('Execution Selection')
    execution_group.add_argument(
        '--peer', action='store_true', default=False, help='Run salt commands through the peer system'
    )
    execution_group.add_argument(
        '--scp', action='store_true', default=False,
        help='Download logs and reports using SCP'
    )

    bootstrap_script_options = parser.add_argument_group(
        'Bootstrap Script Options',
        'In case there\'s a need to provide the bootstrap script from an alternate URL and/or from a specific commit.'
    )
    bootstrap_script_options.add_argument(
        '--bootstrap-salt-url',
        default=None,
        help='The salt git repository url used to bootstrap a minion'
    )
    bootstrap_script_options.add_argument(
        '--bootstrap-salt-commit',
        default=None,
        help='The salt git commit used to bootstrap a minion'
    )

    vm_options_group = parser.add_argument_group('VM Options')
    vm_options_group.add_argument('vm_name', nargs='?', help='Virtual machine name')
    vm_options_group.add_argument(
        '--vm-prefix',
        default=os.environ.get('JENKINS_VM_NAME_PREFIX', 'ZJENKINS'),
        help='The bootstrapped machine name prefix. Default: %(default)r'
    )
    vm_options_group.add_argument(
        '--vm-source',
        default=os.environ.get('JENKINS_VM_SOURCE', None),
        help='The VM source. In case of --cloud usage, the could profile name. In case of --lxc usage, the image name.'
    )
    vm_options_group.add_argument(
        '--grain-target',
        action='append',
        default=[],
        help='Match minions using compound matchers, the minion ID, plus the passed grain.'
    )

    vm_preparation_group = parser.add_argument_group(
        'VM Preparation Options',
        'Salt SLS selection to prepare the VM. The defaults are based on the salt-jenkins repository. See '
        'https://github.com/saltstack/salt-jenkins'
    )
    vm_preparation_group.add_argument(
        '--prep-sls',
        default='git.salt',
        help='The sls file to execute to prepare the system. Default: %(default)r'
    )
    vm_preparation_group.add_argument(
        '--prep-sls-2',
        default=None,
        help='An optional 2nd system preparation SLS'
    )
    vm_preparation_group.add_argument(
        '--sls',
        default='testrun-no-deps',
        help='The final sls file to execute.'
    )
    vm_preparation_group.add_argument(
        '--pillar',
        action='append',
        nargs=2,
        help='Pillar (key, value)s to pass to the sls file. Example: \'--pillar pillar_key pillar_value\''
    )

    vm_actions = parser.add_argument_group(
        'VM Actions',
        'Action to execute on a running VM'
    )
    vm_actions.add_argument(
        '--delete-vm',
        action='store_true',
        default=False,
        help='Delete a running VM'
    )
    vm_actions.add_argument(
        '--download-remote-reports',
        default=False,
        action='store_true',
        help='Download remote reports when running remote \'testrun\' state'
    )
    vm_actions.add_argument(
        '--download-unittest-reports',
        default=False,
        action='store_true',
        help='Download the XML unittest results'
    )
    vm_actions.add_argument(
        '--download-coverage-report',
        default=False,
        action='store_true',
        help='Download the XML coverage reports'
    )
    vm_actions.add_argument(
        '--download-remote-logs',
        default=False,
        action='store_true',
        help='Download remote minion and runtests log files'
    )

    vm_actions.add_argument(
        '--remote-log-path',
        action='append',
        default=[],
        help='Provide additional log paths to download from remote minion'
    )

    testing_source_options = parser.add_argument_group(
        'Testing Options',
        'In case there\'s a need to provide a different repository and/or commit from which the tests suite should be '
        'executed on'
    )
    testing_source_options.add_argument(
        '--test-transport',
        default='zeromq',
        choices=('zeromq', 'raet'),
        help='Set to raet to run integration tests with raet transport. Default: %default')
    testing_source_options.add_argument(
        '--test-git-url',
        default=None,
        help='The testing git repository url')
    testing_source_options.add_argument(
        '--test-git-commit',
        default=None,
        help='The testing git commit to track')

    options = parser.parse_args()

    if not options.vm_source and not options.vm_name:
        parser.error('Unable to get VM name from environ nor generate it without --vm-source')

    if options.lxc:
        if not options.lxc_host:
            parser.error('Need to provide where to deploy the LXC VM by passing it to --lxc-host')
        options.cloud = False

    if not options.vm_name:
        options.vm_name = get_vm_name(options)

    if options.echo_parseable_output:
        echo_parseable_environment(options)
        parser.exit()

    if options.lxc:
        options.cloud = False

    if options.pre_mortem:
        # Run any actions supposed to be executed right before killing the VM
        if options.download_remote_reports:
            # Download unittest reports
            download_unittest_reports(options)
            # Download coverage report
            download_coverage_report(options)
        else:
            if options.download_unittest_reports:
                download_unittest_reports(options)
            if options.download_coverage_report:
                download_coverage_report(options)

        if options.download_remote_logs:
            download_remote_logs(options)

        if options.delete_vm:
            delete_vm(options)

        parser.exit()

    # RUN IT!!!
    cmd = []
    minion_target = build_minion_target(options)

    if options.peer:
        cmd.extend(['salt-call', 'publish.runner'])
    else:
        cmd.append('salt-run')

    if options.lxc:
        cmd.append('lxc.init')
        if options.peer:
            cmd.append(
                'arg="{0}"'.format(
                    to_cli_yaml([
                        options.vm_name,
                        'host={0}'.format(options.lxc_host),
                        'image={0}'.format(options.vm_source)
                    ])
                )
            )
        else:
            cmd.extend([options.vm_name,
                        'host={0}'.format(options.lxc_host),
                        'image={0}'.format(options.vm_source)])
    else:
        cmd.append('cloud.profile')
        if options.peer:
            cmd.append(
                'arg="{0}"'.format(
                    to_cli_yaml([options.vm_source, options.vm_name])
                )
            )
        else:
            cmd.extend([options.vm_source, options.vm_name])

    if options.cloud:
        if options.bootstrap_salt_commit is not None:
            if options.bootstrap_salt_url is None:
                options.bootstrap_salt_url = 'https://github.com/saltstack/salt.git'
            cmd.append(
                'script_args="-D -g {bootstrap_salt_url} -n git {bootstrap_salt_commit}"'
            )
        else:
            cmd.append('script-args="-D"')

    cmd = ' '.join(cmd).format(**options.__dict__)

    print('Running CMD: {0!r}'.format(cmd))
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
        if options.delete_vm:
            delete_vm(options)
        sys.exit(retcode)

    print('VM Bootstrapped. Exit code: {0}'.format(retcode))
    sys.stdout.flush()

    print('Sleeping for 5 seconds to allow the minion to breathe a little')
    sys.stdout.flush()
    time.sleep(5)

    if options.scp:
        prepare_ssh_access(options)

    if options.cloud:
        if options.bootstrap_salt_commit is not None:
            # Let's find out if the installed version matches the passed in pillar
            # information
            print('Grabbing bootstrapped minion version information ... ')
            cmd = []
            if options.peer:
                cmd.extend(['salt-call', '--out=json', 'publish.publish'])
            else:
                cmd.extend(['salt', '-t', '100', '--out=json'])
            cmd.extend([minion_target, 'test.version'])

            if options.peer and ' ' in minion_target:
                cmd.append('expr_form="compound"')

            cmd = ' '.join(cmd)
            print('Running CMD: {0!r}'.format(cmd))
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
                if options.delete_vm:
                    delete_vm(options)
                sys.exit(retcode)

            if not stdout.strip():
                print('Failed to get the bootstrapped minion version(no output). Exit code: {0}'.format(retcode))
                sys.stdout.flush()
                if options.delete_vm:
                    delete_vm(options)
                sys.exit(retcode)

            try:
                version_info = json.loads(stdout.strip())
                if options.peer:
                    version_info = version_info['local']
                else:
                    version_info = version_info[options.vm_name]

                bootstrap_salt_commit = options.bootstrap_salt_commit
                if re.match('v[0-9]+', bootstrap_salt_commit):
                    # We've been passed a tag
                    bootstrap_salt_commit = bootstrap_salt_commit[1:]
                else:
                    # Most likely a git SHA
                    bootstrap_salt_commit = bootstrap_salt_commit[:7]

                if bootstrap_salt_commit not in version_info:
                    print('\n\nATTENTION!!!!\n')
                    print('The boostrapped minion version commit does not contain the desired commit:')
                    print(' {0!r} does not contain {1!r}'.format(version_info, bootstrap_salt_commit))
                    print('\n\n')
                    sys.stdout.flush()
                    #if options.delete_vm:
                    #    delete_vm(options)
                    #sys.exit(retcode)
                else:
                    print('matches!')
            except ValueError:
                print('Failed to load any JSON from {0!r}'.format(stdout.strip()))

    # Run preparation SLS
    time.sleep(3)
    cmd = []
    if options.peer:
        cmd.append('salt-call')
        if options.no_color:
            cmd.append('--no-color')
        cmd.append('publish.publish')
    else:
        cmd.extend(['salt', '-t', '1800'])
        if options.no_color:
            cmd.append('--no-color')

    cmd.extend([
        minion_target, 'state.sls', options.prep_sls, 'pillar="{0}"'.format(build_pillar_data(options))
    ])

    if options.peer and ' ' in minion_target:
        cmd.append('expr_form="compound"')

    cmd = ' '.join(cmd)
    print('Running CMD: {0!r}'.format(cmd))
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
        print('Failed to execute the preparation SLS file. Exit code: {0}'.format(proc.returncode))
        sys.stdout.flush()
        if options.delete_vm:
            delete_vm(options)
        sys.exit(proc.returncode)

    if options.prep_sls_2 is not None:
        time.sleep(3)

        # Run the 2nd preparation SLS
        cmd = []
        if options.peer:
            cmd.append('salt-call')
            if options.no_color:
                cmd.append('--no-color')
            if options.peer:
                cmd.append('publish.publish')
        else:
            cmd.extend(['salt', '-t', '1800'])
            if options.no_color:
                cmd.append('--no-color')

        cmd.extend([
            minion_target, 'state.sls', options.prep_sls_2, 'pillar="{0}"'.format(build_pillar_data(options))
        ])

        if options.peer and ' ' in minion_target:
            cmd.append('expr_form="compound"')

        cmd = ' '.join(cmd)
        print('Running CMD: {0!r}'.format(cmd))
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
            print('Failed to execute the 2nd preparation SLS file. Exit code: {0}'.format(proc.returncode))
            sys.stdout.flush()
            if options.delete_vm:
                delete_vm(options)
            sys.exit(proc.returncode)

    # Run remote checks
    if options.test_git_url is not None:
        time.sleep(1)
        # Let's find out if the cloned repository if checked out from the
        # desired repository
        print('Grabbing the cloned repository remotes information ... ')
        cmd = []
        if options.peer:
            cmd.extend(['salt-call', '--out=json', 'publish.publish'])
        else:
            cmd.extend(['salt', '-t', '100', '--out=json'])

        cmd.extend([minion_target, 'git.remote_get', '/testing'])

        if options.peer and ' ' in minion_target:
            cmd.append('expr_form="compound"')

        print('Running CMD: {0!r}'.format(cmd))

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
            print('Failed to get the cloned repository remote. Exit code: {0}'.format(retcode))
            sys.stdout.flush()
            if options.delete_vm:
                delete_vm(options)
            sys.exit(retcode)

        if not stdout:
            print('Failed to get the cloned repository remote(no output). Exit code: {0}'.format(retcode))
            sys.stdout.flush()
            if options.delete_vm:
                delete_vm(options)
            sys.exit(retcode)

        try:
            remotes_info = json.loads(stdout.strip())
            if remotes_info is not None:
                if options.peer:
                    remotes_info = remotes_info['local']
                else:
                    remotes_info = remotes_info[options.vm_name]

            if remotes_info is None or options.test_git_url not in remotes_info:
                print('The cloned repository remote is not the desired one:')
                print(' {0!r} is not in {1}'.format(options.test_git_url, remotes_info))
                sys.stdout.flush()
                if options.delete_vm:
                    delete_vm(options)
                sys.exit(retcode)
            print('matches!')
        except ValueError:
            print('Failed to load any JSON from {0!r}'.format(stdout.strip()))

    if options.test_git_commit is not None:
        time.sleep(1)

        # Let's find out if the cloned repository is checked out at the desired
        # commit
        print('Grabbing the cloned repository commit information ... ')
        cmd = []
        if options.peer:
            cmd.extend(['salt-call', '--out=json', 'publish.publish'])
        else:
            cmd.extend(['salt', '-t', '100', '--out=json'])

        cmd.extend([minion_target, 'git.revision', '/testing'])

        if options.peer and ' ' in minion_target:
            cmd.append('expr_form="compound"')

        cmd = ' '.join(cmd)

        print('Running CMD: {0!r}'.format(cmd))
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
            if options.delete_vm:
                delete_vm(options)
            sys.exit(retcode)

        if not stdout:
            print('Failed to get the cloned repository revision(no output). Exit code: {0}'.format(retcode))
            sys.stdout.flush()
            if options.delete_vm:
                delete_vm(options)
            sys.exit(retcode)

        try:
            revision_info = json.loads(stdout.strip())
            if options.peer:
                revision_info = revision_info['local']
            else:
                revision_info = revision_info[options.vm_name]

            if revision_info[:7] != options.test_git_commit[:7]:
                print('The cloned repository commit is not the desired one:')
                print(' {0!r} != {1!r}'.format(revision_info[:7], options.test_git_commit[:7]))
                sys.stdout.flush()
                if options.delete_vm:
                    delete_vm(options)
                sys.exit(retcode)
            print('matches!')
        except ValueError:
            print('Failed to load any JSON from {0!r}'.format(stdout.strip()))

    # Run tests here

    time.sleep(3)
    cmd = []
    if options.peer:
        cmd.append('salt-call')
        if options.no_color:
            cmd.append('--no-color')
        cmd.append('publish.publish')
    else:
        cmd.extend(['salt', '-t', '1800'])
        if options.no_color:
            cmd.append('--no-color')

    cmd.extend([
        minion_target,
        'state.sls',
        options.sls,
        'pillar="{0}"'.format(build_pillar_data(options))
    ])

    if options.peer and ' ' in minion_target:
        cmd.append('expr_form="compound"')

    cmd = ' '.join(cmd)

    print('Running CMD: {0!r}'.format(cmd))
    sys.stdout.flush()

    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, _ = proc.communicate()

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

    if options.download_remote_reports:
        # Download unittest reports
        download_unittest_reports(options)
        # Download coverage report
        download_coverage_report(options)

    if options.download_remote_logs:
        download_remote_logs(options)

    if options.delete_vm:
        delete_vm(options)
    parser.exit(proc.returncode)


if __name__ == '__main__':
    main()
