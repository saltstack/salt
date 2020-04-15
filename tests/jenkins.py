#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This script is used to test Salt from a Jenkins server, specifically
jenkins.saltstack.com.

This script is intended to be shell-centric!!
"""

# Import python libs
from __future__ import absolute_import, print_function

import glob
import optparse
import os
import random
import re
import shutil
import subprocess
import sys
import time

# Import Salt libs
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
import salt.utils.yaml

try:
    from salt.utils.nb_popen import NonBlockingPopen
except ImportError:
    # Salt not installed, or nb_popen was not yet shipped with it
    SALT_LIB = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    if SALT_LIB not in sys.path:
        sys.path.insert(0, SALT_LIB)
    try:
        # Let's try using the current checked out code
        from salt.utils.nb_popen import NonBlockingPopen
    except ImportError:
        # Still an ImportError??? Let's use some "brute-force"
        sys.path.insert(0, os.path.join(SALT_LIB, "salt", "utils"))
        from nb_popen import NonBlockingPopen

# Import 3rd-party libs
try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

SALT_GIT_URL = "https://github.com/saltstack/salt.git"


def build_pillar_data(options):
    """
    Build a YAML formatted string to properly pass pillar data
    """
    pillar = {
        "test_transport": options.test_transport,
        "cloud_only": options.cloud_only,
        "with_coverage": options.test_without_coverage is False,
    }
    if options.test_git_commit is not None:
        pillar["test_git_commit"] = options.test_git_commit
    if options.test_git_url is not None:
        pillar["test_git_url"] = options.test_git_url
    if options.bootstrap_salt_url is not None:
        pillar["bootstrap_salt_url"] = options.bootstrap_salt_url
    if options.bootstrap_salt_commit is not None:
        pillar["bootstrap_salt_commit"] = options.bootstrap_salt_commit
    if options.package_source_dir:
        pillar["package_source_dir"] = options.package_source_dir
    if options.package_build_dir:
        pillar["package_build_dir"] = options.package_build_dir
    if options.package_artifact_dir:
        pillar["package_artifact_dir"] = options.package_artifact_dir
    if options.pillar:
        pillar.update(dict(options.pillar))
    return salt.utils.yaml.safe_dump(
        pillar, default_flow_style=True, indent=0, width=sys.maxint
    ).rstrip()


def build_minion_target(options, vm_name):
    target = vm_name
    for grain in options.grain_target:
        target += " and G@{0}".format(grain)
    if options.grain_target:
        return '"{0}"'.format(target)
    return target


def generate_vm_name(options):
    """
    Generate a random enough vm name
    """
    if "BUILD_NUMBER" in os.environ:
        random_part = "BUILD{0:0>6}".format(os.environ.get("BUILD_NUMBER"))
    else:
        random_part = os.urandom(3).encode("hex")

    return "{0}-{1}-{2}".format(options.vm_prefix, options.platform, random_part)


def delete_vm(options):
    """
    Stop a VM
    """
    cmd = "salt-cloud -d {0} -y".format(options.delete_vm)
    print("Running CMD: {0}".format(cmd))
    sys.stdout.flush()

    proc = NonBlockingPopen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stream_stds=True,
    )
    proc.poll_and_read_until_finish(interval=0.5)
    proc.communicate()


def echo_parseable_environment(options, parser):
    """
    Echo NAME=VAL parseable output
    """
    output = []

    if options.platform:
        name = generate_vm_name(options)
        output.extend(
            [
                "JENKINS_SALTCLOUD_VM_PLATFORM={0}".format(options.platform),
                "JENKINS_SALTCLOUD_VM_NAME={0}".format(name),
            ]
        )

    if options.provider:
        output.append("JENKINS_SALTCLOUD_VM_PROVIDER={0}".format(options.provider))

    if options.pull_request:
        # This is a Jenkins triggered Pull Request
        # We need some more data about the Pull Request available to the
        # environment
        if HAS_REQUESTS is False:
            parser.error("The python 'requests' library needs to be installed")

        headers = {}
        url = "https://api.github.com/repos/saltstack/salt/pulls/{0}".format(
            options.pull_request
        )

        github_access_token_path = os.path.join(
            os.environ.get("JENKINS_HOME", os.path.expanduser("~")), ".github_token"
        )
        if os.path.isfile(github_access_token_path):
            with salt.utils.files.fopen(github_access_token_path) as rfh:
                headers = {"Authorization": "token {0}".format(rfh.read().strip())}

        http_req = requests.get(url, headers=headers)
        if http_req.status_code != 200:
            parser.error(
                "Unable to get the pull request: {0[message]}".format(http_req.json())
            )

        pr_details = http_req.json()
        output.extend(
            [
                "SALT_PR_GIT_URL={0}".format(pr_details["head"]["repo"]["clone_url"]),
                "SALT_PR_GIT_BRANCH={0}".format(pr_details["head"]["ref"]),
                "SALT_PR_GIT_COMMIT={0}".format(pr_details["head"]["sha"]),
                "SALT_PR_GIT_BASE_BRANCH={0}".format(pr_details["base"]["ref"]),
            ]
        )

    sys.stdout.write("\n\n{0}\n\n".format("\n".join(output)))
    sys.stdout.flush()


def download_unittest_reports(options):
    print("Downloading remote unittest reports...")
    sys.stdout.flush()

    workspace = options.workspace
    xml_reports_path = os.path.join(workspace, "xml-test-reports")
    if os.path.isdir(xml_reports_path):
        shutil.rmtree(xml_reports_path)

    os.makedirs(xml_reports_path)

    cmds = (
        "salt {0} archive.tar zcvf /tmp/xml-test-reports.tar.gz '*.xml' cwd=/tmp/xml-unittests-output/",
        "salt {0} cp.push /tmp/xml-test-reports.tar.gz",
        "mv -f /var/cache/salt/master/minions/{1}/files/tmp/xml-test-reports.tar.gz {2} && "
        "tar zxvf {2}/xml-test-reports.tar.gz -C {2}/xml-test-reports && "
        "rm -f {2}/xml-test-reports.tar.gz",
    )

    vm_name = options.download_unittest_reports
    for cmd in cmds:
        cmd = cmd.format(build_minion_target(options, vm_name), vm_name, workspace)
        print("Running CMD: {0}".format(cmd))
        sys.stdout.flush()

        proc = NonBlockingPopen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stream_stds=True,
        )
        proc.poll_and_read_until_finish(interval=0.5)
        proc.communicate()
        if proc.returncode != 0:
            print("\nFailed to execute command. Exit code: {0}".format(proc.returncode))
        time.sleep(0.25)


def download_coverage_report(options):
    print("Downloading remote coverage report...")
    sys.stdout.flush()

    workspace = options.workspace
    vm_name = options.download_coverage_report

    if os.path.isfile(os.path.join(workspace, "coverage.xml")):
        os.unlink(os.path.join(workspace, "coverage.xml"))

    cmds = (
        "salt {0} archive.gzip /tmp/coverage.xml",
        "salt {0} cp.push /tmp/coverage.xml.gz",
        "gunzip /var/cache/salt/master/minions/{1}/files/tmp/coverage.xml.gz",
        "mv /var/cache/salt/master/minions/{1}/files/tmp/coverage.xml {2}",
    )

    for cmd in cmds:
        cmd = cmd.format(build_minion_target(options, vm_name), vm_name, workspace)
        print("Running CMD: {0}".format(cmd))
        sys.stdout.flush()

        proc = NonBlockingPopen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stream_stds=True,
        )
        proc.poll_and_read_until_finish(interval=0.5)
        proc.communicate()
        if proc.returncode != 0:
            print("\nFailed to execute command. Exit code: {0}".format(proc.returncode))
        time.sleep(0.25)


def download_remote_logs(options):
    print("Downloading remote logs...")
    sys.stdout.flush()

    workspace = options.workspace
    vm_name = options.download_remote_logs

    for fname in ("salt-runtests.log", "minion.log"):
        if os.path.isfile(os.path.join(workspace, fname)):
            os.unlink(os.path.join(workspace, fname))

    if not options.remote_log_path:
        options.remote_log_path = ["/tmp/salt-runtests.log", "/var/log/salt/minion"]

    cmds = []

    for remote_log in options.remote_log_path:
        cmds.extend(
            [
                "salt {{0}} archive.gzip {0}".format(remote_log),
                "salt {{0}} cp.push {0}.gz".format(remote_log),
                "gunzip /var/cache/salt/master/minions/{{1}}/files{0}.gz".format(
                    remote_log
                ),
                "mv /var/cache/salt/master/minions/{{1}}/files{0} {{2}}/{1}".format(
                    remote_log,
                    "{0}{1}".format(
                        os.path.basename(remote_log),
                        "" if remote_log.endswith(".log") else ".log",
                    ),
                ),
            ]
        )

    for cmd in cmds:
        cmd = cmd.format(build_minion_target(options, vm_name), vm_name, workspace)
        print("Running CMD: {0}".format(cmd))
        sys.stdout.flush()

        proc = NonBlockingPopen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stream_stds=True,
        )
        proc.poll_and_read_until_finish(interval=0.5)
        proc.communicate()
        if proc.returncode != 0:
            print("\nFailed to execute command. Exit code: {0}".format(proc.returncode))
        time.sleep(0.25)


def download_packages(options):
    print("Downloading packages...")
    sys.stdout.flush()

    workspace = options.workspace
    vm_name = options.download_packages

    for fglob in ("salt-*.rpm", "salt-*.deb", "salt-*.pkg.xz", "salt-buildpackage.log"):
        for fname in glob.glob(os.path.join(workspace, fglob)):
            if os.path.isfile(fname):
                os.unlink(fname)

    cmds = [
        (
            "salt {{0}} archive.tar czf {0}.tar.gz sources='*.*' cwd={0}".format(
                options.package_artifact_dir
            )
        ),
        "salt {{0}} cp.push {0}.tar.gz".format(options.package_artifact_dir),
        (
            "tar -C {{2}} -xzf /var/cache/salt/master/minions/{{1}}/files{0}.tar.gz".format(
                options.package_artifact_dir
            )
        ),
    ]

    for cmd in cmds:
        cmd = cmd.format(build_minion_target(options, vm_name), vm_name, workspace)
        print("Running CMD: {0}".format(cmd))
        sys.stdout.flush()

        proc = NonBlockingPopen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stream_stds=True,
        )
        proc.poll_and_read_until_finish(interval=0.5)
        proc.communicate()
        if proc.returncode != 0:
            print("\nFailed to execute command. Exit code: {0}".format(proc.returncode))
        time.sleep(0.25)


def run(opts):
    """
    RUN!
    """
    vm_name = os.environ.get("JENKINS_SALTCLOUD_VM_NAME", generate_vm_name(opts))

    if opts.download_remote_reports:
        if opts.test_without_coverage is False:
            opts.download_coverage_report = vm_name
        opts.download_unittest_reports = vm_name
        opts.download_packages = vm_name

    if opts.bootstrap_salt_commit is not None:
        if opts.bootstrap_salt_url is None:
            opts.bootstrap_salt_url = "https://github.com/saltstack/salt.git"
        cmd = (
            "salt-cloud -l debug"
            ' --script-args "-D -g {bootstrap_salt_url} -n git {1}"'
            " -p {provider}_{platform} {0}".format(
                vm_name,
                os.environ.get(
                    "SALT_MINION_BOOTSTRAP_RELEASE", opts.bootstrap_salt_commit
                ),
                **opts.__dict__
            )
        )
    else:
        cmd = (
            "salt-cloud -l debug"
            ' --script-args "-D -n git {1}" -p {provider}_{platform} {0}'.format(
                vm_name,
                os.environ.get(
                    "SALT_MINION_BOOTSTRAP_RELEASE", opts.bootstrap_salt_commit
                ),
                **opts.__dict__
            )
        )
    if opts.splay is not None:
        # Sleep a random number of seconds
        cloud_downtime = random.randint(0, opts.splay)
        print(
            "Sleeping random period before calling salt-cloud: {0}".format(
                cloud_downtime
            )
        )
        time.sleep(cloud_downtime)
    print("Running CMD: {0}".format(cmd))
    sys.stdout.flush()

    proc = NonBlockingPopen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stream_stds=True,
    )
    proc.poll_and_read_until_finish(interval=0.5)
    proc.communicate()

    retcode = proc.returncode
    if retcode != 0:
        print("Failed to bootstrap VM. Exit code: {0}".format(retcode))
        sys.stdout.flush()
        if opts.clean and "JENKINS_SALTCLOUD_VM_NAME" not in os.environ:
            delete_vm(opts)
        sys.exit(retcode)

    print("VM Bootstrapped. Exit code: {0}".format(retcode))
    sys.stdout.flush()

    # Sleep a random number of seconds
    bootstrap_downtime = random.randint(0, opts.splay)
    print(
        "Sleeping for {0} seconds to allow the minion to breathe a little".format(
            bootstrap_downtime
        )
    )
    sys.stdout.flush()
    time.sleep(bootstrap_downtime)

    if opts.bootstrap_salt_commit is not None:
        # Let's find out if the installed version matches the passed in pillar
        # information
        print("Grabbing bootstrapped minion version information ... ")
        cmd = "salt -t 100 {0} --out json test.version".format(
            build_minion_target(opts, vm_name)
        )
        print("Running CMD: {0}".format(cmd))
        sys.stdout.flush()
        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        stdout, _ = proc.communicate()

        retcode = proc.returncode
        if retcode != 0:
            print(
                "Failed to get the bootstrapped minion version. Exit code: {0}".format(
                    retcode
                )
            )
            sys.stdout.flush()
            if opts.clean and "JENKINS_SALTCLOUD_VM_NAME" not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

        outstr = salt.utils.stringutils.to_str(stdout).strip()
        if not outstr:
            print(
                "Failed to get the bootstrapped minion version(no output). Exit code: {0}".format(
                    retcode
                )
            )
            sys.stdout.flush()
            if opts.clean and "JENKINS_SALTCLOUD_VM_NAME" not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

        try:
            version_info = salt.utils.json.loads(outstr)
            bootstrap_minion_version = os.environ.get(
                "SALT_MINION_BOOTSTRAP_RELEASE", opts.bootstrap_salt_commit[:7]
            )
            print("Minion reported salt version: {0}".format(version_info))
            if bootstrap_minion_version not in version_info[vm_name]:
                print("\n\nATTENTION!!!!\n")
                print(
                    "The boostrapped minion version commit does not contain the desired commit:"
                )
                print(
                    " '{0}' does not contain '{1}'".format(
                        version_info[vm_name], bootstrap_minion_version
                    )
                )
                print("\n\n")
                sys.stdout.flush()
                # if opts.clean and 'JENKINS_SALTCLOUD_VM_NAME' not in os.environ:
                #    delete_vm(opts)
                # sys.exit(retcode)
            else:
                print("matches!")
        except ValueError:
            print("Failed to load any JSON from '{0}'".format(outstr))

    if opts.cloud_only:
        # Run Cloud Provider tests preparation SLS
        cloud_provider_downtime = random.randint(3, opts.splay)
        time.sleep(cloud_provider_downtime)
        cmd = (
            'salt -t 900 {target} state.sls {cloud_prep_sls} pillar="{pillar}" '
            "--no-color".format(
                target=build_minion_target(opts, vm_name),
                cloud_prep_sls="cloud-only",
                pillar=build_pillar_data(opts),
            )
        )
    else:
        # Run standard preparation SLS
        standard_sls_downtime = random.randint(3, opts.splay)
        time.sleep(standard_sls_downtime)
        cmd = (
            'salt -t 1800 {target} state.sls {prep_sls} pillar="{pillar}" '
            "--no-color".format(
                target=build_minion_target(opts, vm_name),
                prep_sls=opts.prep_sls,
                pillar=build_pillar_data(opts),
            )
        )
    print("Running CMD: {0}".format(cmd))
    sys.stdout.flush()

    proc = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    stdout, stderr = proc.communicate()

    if stdout:
        print(salt.utils.stringutils.to_str(stdout))
    if stderr:
        print(salt.utils.stringutils.to_str(stderr))
    sys.stdout.flush()

    retcode = proc.returncode
    if retcode != 0:
        print(
            "Failed to execute the preparation SLS file. Exit code: {0}".format(retcode)
        )
        sys.stdout.flush()
        if opts.clean and "JENKINS_SALTCLOUD_VM_NAME" not in os.environ:
            delete_vm(opts)
        sys.exit(retcode)

    if opts.cloud_only:
        cloud_provider_pillar = random.randint(3, opts.splay)
        time.sleep(cloud_provider_pillar)
        # Run Cloud Provider tests pillar preparation SLS
        cmd = (
            'salt -t 600 {target} state.sls {cloud_prep_sls} pillar="{pillar}" '
            "--no-color".format(
                target=build_minion_target(opts, vm_name),
                cloud_prep_sls="cloud-test-configs",
                pillar=build_pillar_data(opts),
            )
        )
        print("Running CMD: {0}".format(cmd))
        sys.stdout.flush()

        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        stdout, stderr = proc.communicate()

        if stdout:
            # DO NOT print the state return here!
            print("Cloud configuration files provisioned via pillar.")
        if stderr:
            print(salt.utils.stringutils.to_str(stderr))
        sys.stdout.flush()

        retcode = proc.returncode
        if retcode != 0:
            print(
                "Failed to execute the preparation SLS file. Exit code: {0}".format(
                    retcode
                )
            )
            sys.stdout.flush()
            if opts.clean and "JENKINS_SALTCLOUD_VM_NAME" not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

    if opts.prep_sls_2 is not None:
        sls_2_downtime = random.randint(3, opts.splay)
        time.sleep(sls_2_downtime)

        # Run the 2nd preparation SLS
        cmd = (
            'salt -t 30 {target} state.sls {prep_sls_2} pillar="{pillar}" '
            "--no-color".format(
                prep_sls_2=opts.prep_sls_2,
                pillar=build_pillar_data(opts),
                target=build_minion_target(opts, vm_name),
            )
        )
        print("Running CMD: {0}".format(cmd))
        sys.stdout.flush()

        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        stdout, stderr = proc.communicate()

        if stdout:
            print(salt.utils.stringutils.to_str(stdout))
        if stderr:
            print(salt.utils.stringutils.to_str(stderr))
        sys.stdout.flush()

        retcode = proc.returncode
        if retcode != 0:
            print(
                "Failed to execute the 2nd preparation SLS file. Exit code: {0}".format(
                    retcode
                )
            )
            sys.stdout.flush()
            if opts.clean and "JENKINS_SALTCLOUD_VM_NAME" not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

    # Run remote checks
    if opts.test_git_url is not None:
        test_git_downtime = random.randint(1, opts.splay)
        time.sleep(test_git_downtime)
        # Let's find out if the cloned repository if checked out from the
        # desired repository
        print("Grabbing the cloned repository remotes information ... ")
        cmd = "salt -t 100 {0} --out json git.remote_get /testing".format(
            build_minion_target(opts, vm_name)
        )
        print("Running CMD: {0}".format(cmd))
        sys.stdout.flush()
        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

        stdout, _ = proc.communicate()

        retcode = proc.returncode
        if retcode != 0:
            print(
                "Failed to get the cloned repository remote. Exit code: {0}".format(
                    retcode
                )
            )
            sys.stdout.flush()
            if opts.clean and "JENKINS_SALTCLOUD_VM_NAME" not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

        if not stdout:
            print(
                "Failed to get the cloned repository remote(no output). Exit code: {0}".format(
                    retcode
                )
            )
            sys.stdout.flush()
            if opts.clean and "JENKINS_SALTCLOUD_VM_NAME" not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

        try:
            remotes_info = salt.utils.json.loads(stdout.strip())
            if (
                remotes_info is None
                or remotes_info[vm_name] is None
                or opts.test_git_url not in remotes_info[vm_name]
            ):
                print("The cloned repository remote is not the desired one:")
                print(" '{0}' is not in {1}".format(opts.test_git_url, remotes_info))
                sys.stdout.flush()
                if opts.clean and "JENKINS_SALTCLOUD_VM_NAME" not in os.environ:
                    delete_vm(opts)
                sys.exit(retcode)
            print("matches!")
        except ValueError:
            print(
                "Failed to load any JSON from '{0}'".format(
                    salt.utils.stringutils.to_str(stdout).strip()
                )
            )

    if opts.test_git_commit is not None:
        test_git_commit_downtime = random.randint(1, opts.splay)
        time.sleep(test_git_commit_downtime)

        # Let's find out if the cloned repository is checked out at the desired
        # commit
        print("Grabbing the cloned repository commit information ... ")
        cmd = "salt -t 100 {0} --out json git.revision /testing".format(
            build_minion_target(opts, vm_name)
        )
        print("Running CMD: {0}".format(cmd))
        sys.stdout.flush()
        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        stdout, _ = proc.communicate()
        sys.stdout.flush()

        retcode = proc.returncode
        if retcode != 0:
            print(
                "Failed to get the cloned repository revision. Exit code: {0}".format(
                    retcode
                )
            )
            sys.stdout.flush()
            if opts.clean and "JENKINS_SALTCLOUD_VM_NAME" not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

        if not stdout:
            print(
                "Failed to get the cloned repository revision(no output). Exit code: {0}".format(
                    retcode
                )
            )
            sys.stdout.flush()
            if opts.clean and "JENKINS_SALTCLOUD_VM_NAME" not in os.environ:
                delete_vm(opts)
            sys.exit(retcode)

        try:
            revision_info = salt.utils.json.loads(stdout.strip())
            if revision_info[vm_name][7:] != opts.test_git_commit[7:]:
                print("The cloned repository commit is not the desired one:")
                print(
                    " '{0}' != '{1}'".format(
                        revision_info[vm_name][:7], opts.test_git_commit[:7]
                    )
                )
                sys.stdout.flush()
                if opts.clean and "JENKINS_SALTCLOUD_VM_NAME" not in os.environ:
                    delete_vm(opts)
                sys.exit(retcode)
            print("matches!")
        except ValueError:
            print(
                "Failed to load any JSON from '{0}'".format(
                    salt.utils.stringutils.to_str(stdout).strip()
                )
            )

    # Run tests here
    test_begin_downtime = random.randint(3, opts.splay)
    time.sleep(test_begin_downtime)
    cmd = 'salt -t 1800 {target} state.sls {sls} pillar="{pillar}" --no-color'.format(
        sls=opts.sls,
        pillar=build_pillar_data(opts),
        target=build_minion_target(opts, vm_name),
    )
    print("Running CMD: {0}".format(cmd))
    sys.stdout.flush()

    proc = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    stdout, stderr = proc.communicate()

    outstr = salt.utils.stringutils.to_str(stdout)
    if outstr:
        print(outstr)
    if stderr:
        print(salt.utils.stringutils.to_str(stderr))
    sys.stdout.flush()

    try:
        match = re.search(r"Test Suite Exit Code: (?P<exitcode>[\d]+)", outstr)
        retcode = int(match.group("exitcode"))
    except AttributeError:
        # No regex matching
        retcode = 1
    except ValueError:
        # Not a number!?
        retcode = 1
    except TypeError:
        # No output!?
        retcode = 1
        if outstr:
            # Anything else, raise the exception
            raise

    if retcode == 0:
        # Build packages
        time.sleep(3)
        cmd = 'salt -t 1800 {target} state.sls buildpackage pillar="{pillar}" --no-color'.format(
            pillar=build_pillar_data(opts), target=build_minion_target(opts, vm_name),
        )
        print("Running CMD: {0}".format(cmd))
        sys.stdout.flush()

        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate()

        if stdout:
            print(salt.utils.stringutils.to_str(stdout))
        if stderr:
            print(salt.utils.stringutils.to_str(stderr))
        sys.stdout.flush()

        # Grab packages and log file (or just log file if build failed)
        download_packages(opts)

    if opts.download_remote_reports:
        # Download unittest reports
        download_unittest_reports(opts)
        # Download coverage report
        if opts.test_without_coverage is False:
            download_coverage_report(opts)

    if opts.clean and "JENKINS_SALTCLOUD_VM_NAME" not in os.environ:
        delete_vm(opts)
    return retcode


def parse():
    """
    Parse the CLI options
    """
    parser = optparse.OptionParser()
    parser.add_option(
        "--vm-prefix",
        default=os.environ.get("JENKINS_VM_NAME_PREFIX", "ZJENKINS"),
        help="The bootstrapped machine name prefix",
    )
    parser.add_option(
        "-w",
        "--workspace",
        default=os.path.abspath(
            os.environ.get("WORKSPACE", os.path.dirname(os.path.dirname(__file__)))
        ),
        help="Path the execution workspace",
    )
    parser.add_option(
        "--platform",
        default=os.environ.get("JENKINS_SALTCLOUD_VM_PLATFORM", None),
        help="The target platform, choose from:\ncent6\ncent5\nubuntu12.04",
    )
    parser.add_option(
        "--provider",
        default=os.environ.get("JENKINS_SALTCLOUD_VM_PROVIDER", None),
        help="The vm provider",
    )
    parser.add_option(
        "--bootstrap-salt-url",
        default=None,
        help="The salt git repository url used to boostrap a minion",
    )
    parser.add_option(
        "--bootstrap-salt-commit",
        default=None,
        help="The salt git commit used to boostrap a minion",
    )
    parser.add_option(
        "--test-git-url", default=None, help="The testing git repository url"
    )
    parser.add_option(
        "--test-git-commit", default=None, help="The testing git commit to track"
    )
    parser.add_option(
        "--test-transport",
        default="zeromq",
        choices=("zeromq", "tcp"),
        help=(
            "Select which transport to run the integration tests with, "
            "zeromq or tcp. Default: %default"
        ),
    )
    parser.add_option(
        "--test-without-coverage",
        default=False,
        action="store_true",
        help="Do not generate coverage reports",
    )
    parser.add_option(
        "--prep-sls",
        default="git.salt",
        help="The sls file to execute to prepare the system",
    )
    parser.add_option(
        "--prep-sls-2", default=None, help="An optional 2nd system preparation SLS"
    )
    parser.add_option(
        "--sls", default="testrun-no-deps", help="The final sls file to execute"
    )
    parser.add_option(
        "--pillar",
        action="append",
        nargs=2,
        help="Pillar (key, value)s to pass to the sls file. "
        "Example: '--pillar pillar_key pillar_value'",
    )
    parser.add_option(
        "--no-clean",
        dest="clean",
        default=True,
        action="store_false",
        help="Clean up the built vm",
    )
    parser.add_option(
        "--echo-parseable-environment",
        default=False,
        action="store_true",
        help="Print a parseable KEY=VAL output",
    )
    parser.add_option("--pull-request", type=int, help="Include the PR info only")
    parser.add_option("--delete-vm", default=None, help="Delete a running VM")
    parser.add_option(
        "--download-remote-reports",
        default=False,
        action="store_true",
        help="Download remote reports when running remote 'testrun' state",
    )
    parser.add_option(
        "--download-unittest-reports",
        default=None,
        help="Download the XML unittest results",
    )
    parser.add_option(
        "--download-coverage-report",
        default=None,
        help="Download the XML coverage reports",
    )
    parser.add_option(
        "--remote-log-path",
        action="append",
        default=[],
        help="Provide additional log paths to download from remote minion",
    )
    parser.add_option(
        "--download-remote-logs",
        default=None,
        help="Download remote minion and runtests log files",
    )
    parser.add_option(
        "--grain-target",
        action="append",
        default=[],
        help="Match minions using compound matchers, the minion ID, plus the passed grain.",
    )
    parser.add_option(
        "--cloud-only",
        default=False,
        action="store_true",
        help="Run the cloud provider tests only.",
    )
    parser.add_option(
        "--build-packages",
        default=True,
        action="store_true",
        help="Run buildpackage.py to create packages off of the git build.",
    )
    # These next three options are ignored if --build-packages is False
    parser.add_option(
        "--package-source-dir",
        default="/testing",
        help="Directory where the salt source code checkout is found "
        "(default: %default)",
    )
    parser.add_option(
        "--package-build-dir",
        default="/tmp/salt-buildpackage",
        help="Build root for automated package builds (default: %default)",
    )
    parser.add_option(
        "--package-artifact-dir",
        default="/tmp/salt-packages",
        help="Location on the minion from which packages should be "
        "retrieved (default: %default)",
    )
    parser.add_option(
        "--splay",
        default="10",
        help="The number of seconds across which calls to provisioning components should be made",
    )

    options, args = parser.parse_args()

    if options.delete_vm is not None and not options.test_git_commit:
        delete_vm(options)
        parser.exit(0)

    if options.download_unittest_reports is not None and not options.test_git_commit:
        download_unittest_reports(options)
        parser.exit(0)

    if options.test_without_coverage is False:
        if options.download_coverage_report is not None and not options.test_git_commit:
            download_coverage_report(options)
            parser.exit(0)

    if options.download_remote_logs is not None and not options.test_git_commit:
        download_remote_logs(options)
        parser.exit(0)

    if not options.platform and not options.pull_request:
        parser.exit("--platform or --pull-request is required")

    if not options.provider and not options.pull_request:
        parser.exit("--provider or --pull-request is required")

    if options.echo_parseable_environment:
        echo_parseable_environment(options, parser)
        parser.exit(0)

    if not options.test_git_commit and not options.pull_request:
        parser.exit("--commit or --pull-request is required")

    return options


if __name__ == "__main__":
    exit_code = run(parse())
    print("Exit Code: {0}".format(exit_code))
    sys.exit(exit_code)
