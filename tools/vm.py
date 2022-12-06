"""
These commands are used to create/destroy VMs, sync the local checkout
to the VM and to run commands on the VM.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import platform
import pprint
import shutil
import subprocess
import sys
import textwrap
import time
from datetime import datetime
from functools import lru_cache
from typing import TYPE_CHECKING, cast

from ptscripts import Context, command_group

try:
    import attr
    import boto3
    from botocore.exceptions import ClientError
    from rich.progress import (
        BarColumn,
        Column,
        Progress,
        TaskProgressColumn,
        TextColumn,
        TimeRemainingColumn,
    )
except ImportError:
    print(
        "\nPlease run 'python -m pip install -r "
        "requirements/static/ci/py{}.{}/tools.txt'\n".format(*sys.version_info),
        file=sys.stderr,
        flush=True,
    )
    raise


if TYPE_CHECKING:
    from boto3.resources.factory.ec2 import Instance

log = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).parent.parent
STATE_DIR = REPO_ROOT / ".vms-state"
with REPO_ROOT.joinpath("cicd", "golden-images.json").open() as rfh:
    AMIS = json.load(rfh)
REPO_CHECKOUT_ID = hashlib.sha256(
    "|".join(list(platform.uname()) + [str(REPO_ROOT)]).encode()
).hexdigest()
AWS_REGION = (
    os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "us-west-2"
)
# Define the command group
vm = command_group(name="vm", help="VM Related Commands", description=__doc__)
vm.add_argument("--region", help="The AWS region.", default=AWS_REGION)


@vm.command(
    arguments={
        "name": {
            "help": "The VM Name",
            "metavar": "VM_NAME",
            "choices": list(AMIS),
        },
        "key_name": {
            "help": "The SSH key name.",
        },
        "instance_type": {
            "help": "The instance type to use.",
        },
        "no_delete": {
            "help": (
                "By default, every VM started will get terminated after a specific "
                "ammount of hours. When true, the started VM get's excluded from that "
                "forced termination."
            ),
        },
        "no_destroy_on_failure": {
            "help": "Do not destroy the instance on failing to create and connect.",
        },
        "retries": {
            "help": "How many times to retry creating and connecting to a vm",
        },
    }
)
def create(
    ctx: Context,
    name: str,
    key_name: str = os.environ.get("RUNNER_NAME"),  # type: ignore[assignment]
    instance_type: str = None,
    no_delete: bool = False,
    no_destroy_on_failure: bool = False,
    retries: int = 0,
):
    """
    Create VM.
    """
    if key_name is None:
        ctx.exit(1, "We need a key name to spin a VM")
    if not retries:
        retries = 1
    attempts = 0
    while True:
        attempts += 1
        vm = VM(ctx=ctx, name=name, region_name=ctx.parser.options.region)
        created = vm.create(
            key_name=key_name, instance_type=instance_type, no_delete=no_delete
        )
        if created is True:
            break

        ctx.error(created)
        if no_destroy_on_failure is False:
            vm.destroy()
        if attempts >= retries:
            ctx.exit(1)

        ctx.info("Retrying in 5 seconds...")
        time.sleep(5)


@vm.command(
    arguments={
        "name": {
            "help": "The VM Name",
            "metavar": "VM_NAME",
        },
    }
)
def destroy(ctx: Context, name: str):
    """
    Destroy VM.
    """
    vm = VM(ctx=ctx, name=name, region_name=ctx.parser.options.region)
    vm.destroy()


@vm.command(
    arguments={
        "name": {
            "help": "The VM Name",
            "metavar": "VM_NAME",
        },
        "command": {
            "help": "Command to run in VM",
            "nargs": "*",
        },
        "sudo": {
            "help": "Run command as sudo",
            "action": "store_true",
        },
    }
)
def ssh(ctx: Context, name: str, command: list[str], sudo: bool = False):
    """
    SSH into the VM, or run 'command' in VM
    """
    vm = VM(ctx=ctx, name=name, region_name=ctx.parser.options.region)
    pseudo_terminal = command == []
    vm.run(command, sudo=sudo, capture=False, pseudo_terminal=pseudo_terminal)


@vm.command(
    arguments={
        "name": {
            "help": "The VM Name",
            "metavar": "VM_NAME",
        },
    }
)
def rsync(ctx: Context, name: str):
    """
    Sync local checkout to VM.
    """
    vm = VM(ctx=ctx, name=name, region_name=ctx.parser.options.region)
    vm.upload_checkout()


@vm.command(
    arguments={
        "name": {
            "help": "The VM Name",
            "metavar": "VM_NAME",
        },
        "nox_session": {
            "flags": [
                "-e",
                "--nox-session",
            ],
            "help": "The nox session name to run in the VM",
        },
        "nox_session_args": {
            "help": "Extra CLI arguments to pass to pytest",
            "nargs": "*",
            "metavar": "NOX_SESSION_ARGS",
        },
        "rerun_failures": {
            "help": "Re-run test failures",
            "action": "store_true",
        },
        "skip_requirements_install": {
            "help": "Skip requirements installation",
            "action": "store_true",
            "flags": [
                "--sri",
                "--skip-requirements-install",
            ],
        },
        "print_tests_selection": {
            "help": "Print the tests selection",
            "action": "store_true",
            "flags": [
                "--pts",
                "--print-tests-selection",
            ],
        },
        "skip_code_coverage": {
            "help": "Skip tracking code coverage",
            "action": "store_true",
            "flags": [
                "--scc",
                "--skip-code-coverage",
            ],
        },
    }
)
def test(
    ctx: Context,
    name: str,
    nox_session_args: list[str] = None,
    nox_session: str = "ci-test-3",
    rerun_failures: bool = False,
    skip_requirements_install: bool = False,
    print_tests_selection: bool = False,
    skip_code_coverage: bool = False,
):
    """
    Run test in the VM.
    """
    vm = VM(ctx=ctx, name=name, region_name=ctx.parser.options.region)
    env = {
        "PRINT_TEST_PLAN_ONLY": "0",
        "SKIP_INITIAL_GH_ACTIONS_FAILURES": "1",
    }
    if rerun_failures:
        env["RERUN_FAILURES"] = "1"
    if print_tests_selection:
        env["PRINT_TEST_SELECTION"] = "1"
    else:
        env["PRINT_TEST_SELECTION"] = "0"
    if skip_code_coverage:
        env["SKIP_CODE_COVERAGE"] = "1"
    else:
        env["SKIP_CODE_COVERAGE"] = "0"
    if (
        skip_requirements_install
        or os.environ.get("SKIP_REQUIREMENTS_INSTALL", "0") == "1"
    ):
        env["SKIP_REQUIREMENTS_INSTALL"] = "1"
    if "photonos" in name:
        skip_known_failures = os.environ.get("SKIP_INITIAL_PHOTONOS_FAILURES", "1")
        env["SKIP_INITIAL_PHOTONOS_FAILURES"] = skip_known_failures
    vm.run_nox(
        nox_session=nox_session,
        session_args=nox_session_args,
        env=env,
    )


@vm.command(
    arguments={
        "name": {
            "help": "The VM Name",
            "metavar": "VM_NAME",
        },
        "nox_session": {
            "flags": [
                "-e",
                "--nox-session",
            ],
            "help": "The nox session name to run in the VM",
        },
        "nox_session_args": {
            "help": "Extra CLI arguments to pass to pytest",
            "nargs": "*",
            "metavar": "NOX_SESSION_ARGS",
        },
        "skip_requirements_install": {
            "help": "Skip requirements installation",
            "action": "store_true",
            "flags": [
                "--sri",
                "--skip-requirements-install",
            ],
        },
    }
)
def testplan(
    ctx: Context,
    name: str,
    nox_session_args: list[str] = None,
    nox_session: str = "ci-test-3",
    skip_requirements_install: bool = False,
):
    """
    Run test in the VM.
    """
    vm = VM(ctx=ctx, name=name, region_name=ctx.parser.options.region)
    env = {
        "PRINT_TEST_SELECTION": "1",
        "PRINT_TEST_PLAN_ONLY": "1",
        "SKIP_CODE_COVERAGE": "1",
        "SKIP_INITIAL_GH_ACTIONS_FAILURES": "1",
    }
    if (
        skip_requirements_install
        or os.environ.get("SKIP_REQUIREMENTS_INSTALL", "0") == "1"
    ):
        env["SKIP_REQUIREMENTS_INSTALL"] = "1"
    if "photonos" in name:
        skip_known_failures = os.environ.get("SKIP_INITIAL_PHOTONOS_FAILURES", "1")
        env["SKIP_INITIAL_PHOTONOS_FAILURES"] = skip_known_failures
    vm.run_nox(
        nox_session=nox_session,
        session_args=nox_session_args,
        env=env,
    )


@vm.command(
    name="install-dependencies",
    arguments={
        "name": {
            "help": "The VM Name",
            "metavar": "VM_NAME",
        },
        "nox_session": {
            "flags": [
                "-e",
                "--nox-session",
            ],
            "help": "The nox environ to run in the VM",
        },
    },
)
def install_dependencies(ctx: Context, name: str, nox_session: str = "ci-test-3"):
    """
    Install test dependencies on VM.
    """
    vm = VM(ctx=ctx, name=name, region_name=ctx.parser.options.region)
    vm.install_dependencies(nox_session)


@vm.command(
    name="compress-dependencies",
    arguments={
        "name": {
            "help": "The VM Name",
            "metavar": "VM_NAME",
        },
    },
)
def compress_dependencies(ctx: Context, name: str):
    """
    Compress the .nox/ directory in the VM.
    """
    vm = VM(ctx=ctx, name=name, region_name=ctx.parser.options.region)
    vm.compress_dependencies()


@vm.command(
    name="decompress-dependencies",
    arguments={
        "name": {
            "help": "The VM Name",
            "metavar": "VM_NAME",
        },
    },
)
def decompress_dependencies(ctx: Context, name: str):
    """
    Decompress a dependencies archive into the .nox/ directory in the VM.
    """
    vm = VM(ctx=ctx, name=name, region_name=ctx.parser.options.region)
    vm.decompress_dependencies()


@vm.command(
    name="download-dependencies",
    arguments={
        "name": {
            "help": "The VM Name",
            "metavar": "VM_NAME",
        },
    },
)
def download_dependencies(ctx: Context, name: str):
    """
    Download a compressed .nox/ directory from VM.
    """
    vm = VM(ctx=ctx, name=name, region_name=ctx.parser.options.region)
    vm.download_dependencies()


@vm.command(
    name="combine-coverage",
    arguments={
        "name": {
            "help": "The VM Name",
            "metavar": "VM_NAME",
        },
    },
)
def combine_coverage(ctx: Context, name: str):
    """
    Combine the several code coverage files into a single one in the VM.
    """
    vm = VM(ctx=ctx, name=name, region_name=ctx.parser.options.region)
    vm.combine_coverage()


@vm.command(
    name="download-artifacts",
    arguments={
        "name": {
            "help": "The VM Name",
            "metavar": "VM_NAME",
        },
    },
)
def download_artifacts(ctx: Context, name: str):
    """
    Download test artifacts from VM.
    """
    vm = VM(ctx=ctx, name=name, region_name=ctx.parser.options.region)
    vm.download_artifacts()


@attr.s(frozen=True, kw_only=True)
class AMIConfig:
    ami: str = attr.ib()
    ssh_username: str = attr.ib()
    create_timeout: int = attr.ib(default=5 * 60)
    connect_timeout: int = attr.ib(default=10 * 60)
    terminate_timeout: int = attr.ib(default=5 * 60)
    upload_path: str = attr.ib(default=None)


@attr.s(slots=True, kw_only=True, hash=True, repr=False)
class VM:
    ctx: Context = attr.ib()
    name: str = attr.ib()
    region_name: str = attr.ib(default=None)
    # Internal
    config: AMIConfig = attr.ib(init=False)
    instance: Instance = attr.ib(init=False, hash=False, default=None)
    state_dir: pathlib.Path = attr.ib(init=False)
    ssh_config_file: pathlib.Path = attr.ib(init=False)

    def __attrs_post_init__(self):
        self.read_state()
        if self.is_running:
            self.write_ssh_config()

    @config.default
    def _config_default(self):
        config = AMIConfig(
            **{
                key: value
                for (key, value) in AMIS[self.name].items()
                if key in AMIConfig.__annotations__
            }
        )
        log.info(f"Loaded VM Configuration:\n{config}")
        return config

    @state_dir.default
    def _state_dir_default(self):
        state_dir = STATE_DIR / self.name
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir

    @ssh_config_file.default
    def _ssh_config_file_default(self):
        return self.state_dir / "ssh-config"

    def read_state(self):
        self.get_ec2_resource.cache_clear()
        instance = None
        ec2_region_path = self.state_dir / "ec2-region"
        if ec2_region_path.exists():
            self.region_name = ec2_region_path.read_text().strip()
        instance_id_path = self.state_dir / "instance-id"
        if instance_id_path.exists():
            instance_id = instance_id_path.read_text().strip()
            _instance = self.ec2.Instance(instance_id)
            try:
                if _instance.state["Name"] == "running":
                    instance = _instance
            except ClientError as exc:
                if "InvalidInstanceID.NotFound" not in str(exc):
                    # This machine no longer exists?!
                    self.ctx.error(str(exc))
                    self.ctx.exit(1)
                instance_id_path.unlink()
        if not instance_id_path.exists():
            filters = [
                {"Name": "tag:vm-name", "Values": [self.name]},
                {"Name": "tag:instance-client-id", "Values": [REPO_CHECKOUT_ID]},
            ]
            log.info(f"Checking existing instance of {self.name}({self.config.ami})...")
            instances = list(
                self.ec2.instances.filter(
                    Filters=filters,
                )
            )
            for _instance in instances:
                if _instance.state["Name"] == "running":
                    instance = _instance
                    break
        if instance:
            self.instance = instance

    def write_state(self):
        ec2_region_path = self.state_dir / "ec2-region"
        if self.region_name:
            ec2_region_path.write_text(self.region_name)
        instance_id_path = self.state_dir / "instance-id"
        if self.id:
            instance_id_path.write_text(self.id)
            self.write_ssh_config()

    def write_ssh_config(self):
        if self.ssh_config_file.exists():
            return
        if os.environ.get("CI") is not None:
            forward_agent = "no"
        else:
            forward_agent = "yes"
        ssh_config = textwrap.dedent(
            f"""\
            Host {self.name}
              Hostname {self.instance.public_ip_address or self.instance.private_ip_address}
              User {self.config.ssh_username}
              ControlMaster=no
              Compression=yes
              LogLevel=FATAL
              StrictHostKeyChecking=no
              UserKnownHostsFile=/dev/null
              ForwardAgent={forward_agent}
            """
        )
        self.ssh_config_file.write_text(ssh_config)

    def create(self, key_name=None, instance_type=None, no_delete=False):
        if self.is_running:
            log.info(f"{self!r} is already running...")
            return True
        self.get_ec2_resource.cache_clear()

        create_timeout = self.config.create_timeout
        create_timeout_progress = 0
        ssh_connection_timeout = self.config.connect_timeout
        ssh_connection_timeout_progress = 0

        started_in_ci = os.environ.get("RUNNER_NAME") is not None
        tags = [
            {"Key": "vm-name", "Value": self.name},
            {"Key": "instance-client-id", "Value": REPO_CHECKOUT_ID},
            {"Key": "started-in-ci", "Value": str(started_in_ci).lower()},
            {"Key": "no-delete", "Value": str(no_delete).lower()},
        ]
        client = boto3.client("ec2", region_name=self.region_name)
        # Let's search for the launch template corresponding to this AMI
        launch_template_name = None
        try:
            response = response = client.describe_launch_templates(
                Filters=[
                    {
                        "Name": "tag:spb:is-golden-image-template",
                        "Values": ["true"],
                    },
                    {
                        "Name": "tag:spb:project",
                        "Values": ["salt-project"],
                    },
                    {
                        "Name": "tag:spb:image-id",
                        "Values": [self.config.ami],
                    },
                ]
            )
            log.debug(
                "Search for launch template response:\n%s", pprint.pformat(response)
            )
            for details in response.get("LaunchTemplates"):
                if launch_template_name is not None:
                    log.info(
                        "Multiple launch templates for the same AMI. This is not "
                        "supposed to happen. Picked the first one listed: %s",
                        response,
                    )
                    break
                launch_template_name = details["LaunchTemplateName"]

            if launch_template_name is None:
                self.ctx.error(f"Could not find a launch template for {self.name!r}")
                self.ctx.exit(1)
        except ClientError as exc:
            self.ctx.error(f"Could not find a launch template for {self.name!r}: {exc}")
            self.ctx.exit(1)

        try:
            data = client.describe_launch_template_versions(
                LaunchTemplateName=launch_template_name
            )
        except ClientError as exc:
            if "InvalidLaunchTemplateName." not in str(exc):
                raise
            self.ctx.error(f"Could not find a launch template for {self.name!r}")
            self.ctx.exit(1)

        # The newest template comes first
        template_data = data["LaunchTemplateVersions"][0]["LaunchTemplateData"]
        security_group_ids = template_data["SecurityGroupIds"]

        vpc = None
        subnets = {}
        for sg_id in security_group_ids:
            sg = self.ec2.SecurityGroup(sg_id)
            vpc = self.ec2.Vpc(sg.vpc_id)
            for subnet in vpc.subnets.all():
                for tag in subnet.tags:
                    if tag["Key"] != "Name":
                        continue
                    if started_in_ci and "-private-" in tag["Value"]:
                        subnets[subnet.id] = subnet.available_ip_address_count
                        break
                    if started_in_ci is False and "-public-" in tag["Value"]:
                        subnets[subnet.id] = subnet.available_ip_address_count
                        break
            if subnets:
                # Let's not process the other security group(s), if any
                break

        chosen_subnet, _ = sorted(subnets.items(), reverse=True)[0]

        network_interfaces = None
        if started_in_ci:
            log.info("Starting CI configured VM")
        else:
            # This is a developer running
            log.info("Starting Developer configured VM")
            # Get the develpers security group
            security_group_filters = [
                {
                    "Name": "vpc-id",
                    "Values": [vpc.id],
                },
                {
                    "Name": "tag:spb:project",
                    "Values": ["salt-project"],
                },
                {
                    "Name": "tag:spb:developer",
                    "Values": ["true"],
                },
            ]
            response = client.describe_security_groups(Filters=security_group_filters)
            if not response.get("SecurityGroups"):
                self.ctx.error(
                    "Could not find the right security group for developers. "
                    f"Filters:\n{pprint.pformat(security_group_filters)}"
                )
                self.ctx.exit(1)
            # Override the launch template network interfaces config
            security_group_ids = [sg["GroupId"] for sg in response["SecurityGroups"]]

        progress = create_progress_bar()
        create_task = progress.add_task(
            f"Starting {self!r} in {self.region_name!r} with ssh key named {key_name!r}...",
            total=create_timeout,
        )
        if os.environ.get("CI") is not None:
            job = os.environ["GITHUB_JOB"]
            ref = os.environ["GITHUB_REF"]
            repo = os.environ["GITHUB_REPOSITORY"]
            actor = (
                os.environ.get("GITHUB_TRIGGERING_ACTOR") or os.environ["GITHUB_ACTOR"]
            )
            if "pull" in ref:
                ref = f"pr-{ref.split('/')[2]}"
            elif "tags" in ref:
                ref = f"tag-{ref.split('/')[-1]}"
            else:
                ref = ref.split("/")[-1]
            tests_chunk = os.environ.get("TESTS_CHUNK")
            if tests_chunk is None:
                tests_chunk = ""
            else:
                tags.append(
                    {
                        "Key": "TESTS_CHUNK",
                        "Value": tests_chunk,
                    }
                )
                tests_chunk = f" - {tests_chunk}"
            name = f"{self.name} - {repo} - {ref} - {job}{tests_chunk} - {actor}"
            for key in os.environ:
                if not key.startswith("GITHUB_"):
                    continue
                if key in (
                    "GITHUB_ACTIONS",
                    "GITHUB_API_URL",
                    "GITHUB_ENV",
                    "GITHUB_EVENT_PATH",
                    "GITHUB_GRAPHQL_URL",
                    "GITHUB_OUTPUT",
                    "GITHUB_PATH",
                    "GITHUB_REPOSITORY_OWNER",
                    "GITHUB_RETENTION_DAYS",
                    "GITHUB_STATE",
                    "GITHUB_STEP_SUMMARY",
                ):
                    continue
                value = os.environ.get(key)
                if not value:
                    continue
                tags.append(
                    {
                        "Key": f"gh:{key}",
                        "Value": value,
                    }
                )
        else:
            name = f"{self.name} started on {datetime.utcnow()}"
        tags.append(
            {
                "Key": "Name",
                "Value": name,
            }
        )
        with progress:
            start = time.time()
            create_kwargs = dict(
                MinCount=1,
                MaxCount=1,
                KeyName=key_name,
                TagSpecifications=[
                    {
                        "ResourceType": "instance",
                        "Tags": tags,
                    }
                ],
                LaunchTemplate={
                    "LaunchTemplateName": launch_template_name,
                },
                SecurityGroupIds=security_group_ids,
                SubnetId=chosen_subnet,
            )
            if instance_type:
                # The user provided a custom instance type
                create_kwargs["InstanceType"] = instance_type
            if network_interfaces is not None:
                # This is a developer configured VM
                create_kwargs["NetworkInterfaces"] = network_interfaces

            # Create the VM
            try:
                response = self.ec2.create_instances(**create_kwargs)
            except ClientError as exc:
                progress.stop()
                self.ctx.exit(1, str(exc))
            for _instance in response:
                self.instance = _instance
            stop = time.time()
            create_timeout_progress += stop - start
            progress.update(
                create_task,
                description=f"{self!r} created...",
                completed=create_timeout_progress,
            )

            # Wait until the VM is running
            while create_timeout_progress <= create_timeout:
                time.sleep(1)
                create_timeout_progress += 1
                if self.is_running:
                    progress.update(
                        create_task,
                        description=f"{self!r} is running.",
                        completed=create_timeout,
                    )
                    self.write_state()
                    break
                progress.update(
                    create_task,
                    description=f"Waiting until {self!r} is running...",
                    completed=create_timeout_progress,
                )
            else:
                error = f"Failed to create {self!r}"
                progress.update(
                    create_task,
                    description=error,
                    completed=create_timeout,
                )
                return error

            # Wait until we can SSH into the VM
            host = self.instance.public_ip_address or self.instance.private_ip_address

        progress = create_progress_bar()
        connect_task = progress.add_task(
            f"Waiting for SSH to become available at {host} ...",
            total=ssh_connection_timeout,
        )
        with progress:
            proc = None
            checks = 0
            last_error = None
            while ssh_connection_timeout_progress <= ssh_connection_timeout:
                start = time.time()
                if proc is None:
                    checks = 0
                    stderr = None
                    proc = subprocess.Popen(
                        self.ssh_command_args(
                            "exit",
                            "0",
                            log_command_level=logging.DEBUG,
                            ssh_options=[
                                "-oLogLevel=INFO",
                                "-oConnectTimeout=5",
                                "-oConnectionAttempts=1",
                            ],
                        ),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                        shell=False,
                    )
                checks += 1
                try:
                    wait_start = time.time()
                    proc.wait(timeout=3)
                    progress.update(
                        connect_task,
                        completed=ssh_connection_timeout_progress,
                        description=f"Waiting for SSH to become available at {host} ...",
                    )
                    if proc.returncode == 0:
                        progress.update(
                            connect_task,
                            description=f"SSH connection to {host} available!",
                            completed=ssh_connection_timeout,
                        )
                        return True
                    proc.wait(timeout=3)
                    stderr = proc.stderr.read().strip()
                    if stderr:
                        stderr = f" Last Error: {stderr}"
                        last_error = stderr
                    proc = None
                    if time.time() - wait_start < 1:
                        # Process exited too fast, sleep a little longer
                        time.sleep(5)
                except KeyboardInterrupt:
                    return
                except subprocess.TimeoutExpired:
                    pass

                ssh_connection_timeout_progress += time.time() - start
                progress.update(
                    connect_task,
                    completed=ssh_connection_timeout_progress,
                    description=f"Waiting for SSH to become available at {host} ...{stderr or ''}",
                )

                if checks >= 10 and proc is not None:
                    proc.kill()
                    proc = None
            else:
                error = f"Failed to establish an ssh connection to {host}"
                if last_error:
                    error += f". {last_error}"
                return error

    def destroy(self):
        try:
            if not self.is_running:
                log.info(f"{self!r} is not running...")
                return
            timeout = self.config.terminate_timeout
            timeout_progress = 0
            progress = create_progress_bar()
            task = progress.add_task(f"Terminatting {self!r}...", total=timeout)
            self.instance.terminate()
            try:
                with progress:
                    while timeout_progress <= timeout:
                        start = time.time()
                        time.sleep(1)
                        if self.state == "terminated":
                            progress.update(
                                task,
                                description=f"{self!r} terminated.",
                                completed=timeout,
                            )
                            break
                        timeout_progress += time.time() - start
                        progress.update(
                            task,
                            description=f"Terminating {self!r}...",
                            completed=timeout_progress,
                        )
                    else:
                        progress.update(
                            task,
                            description=f"Failed to terminate {self!r}.",
                            completed=timeout,
                        )
            except KeyboardInterrupt:
                pass
        finally:
            shutil.rmtree(self.state_dir, ignore_errors=True)
            self.instance = None

    def upload_checkout(self, verbose=True):
        rsync_flags = [
            "--delete",
            "--no-group",
            "--no-owner",
            "--exclude",
            ".nox/",
            "--exclude",
            ".pytest_cache/",
            "--exclude",
            "artifacts/",
            "--exclude",
            f"{STATE_DIR.relative_to(REPO_ROOT)}{os.path.sep}",
            "--exclude",
            "*.py~",
        ]
        if self.is_windows:
            # Symlinks aren't handled properly on windows, just replace the
            # symlink with a copy of what's getting symlinked.
            rsync_flags.append("--copy-links")
        # Local repo path
        source = f"{REPO_ROOT}{os.path.sep}"
        # Remote repo path
        remote_path = self.upload_path.as_posix()
        if self.is_windows:
            for drive in ("c:", "C:"):
                remote_path = remote_path.replace(drive, "/cygdrive/c")
        destination = f"{self.name}:{remote_path}"
        description = "Rsync local checkout to VM..."
        self.rsync(source, destination, description, rsync_flags)

    def write_and_upload_dot_env(self, env: dict[str, str]):
        if not env:
            return
        write_env = {k: str(v) for (k, v) in env.items()}
        write_env_filename = ".ci-env"
        write_env_filepath = REPO_ROOT / ".ci-env"
        write_env_filepath.write_text(json.dumps(write_env))

        # Local path
        source = str(write_env_filepath)
        # Remote repo path
        remote_path = self.upload_path.joinpath(write_env_filename).as_posix()
        if self.is_windows:
            for drive in ("c:", "C:"):
                remote_path = remote_path.replace(drive, "/cygdrive/c")
        destination = f"{self.name}:{remote_path}"
        description = f"Uploading {write_env_filename} ..."
        self.rsync(source, destination, description)
        write_env_filepath.unlink()

    def run(
        self,
        command: list[str],
        check: bool = True,
        sudo: bool = False,
        capture: bool = False,
        pseudo_terminal: bool = False,
        env: list[str] = None,
        log_command_level: int = logging.INFO,
    ):
        if not self.is_running:
            self.ctx.exit(1, message=f"{self!r} is not running")
        if env is None:
            env = []
        env.append("PYTHONUTF8=1")
        self.write_ssh_config()
        try:
            ssh_command = self.ssh_command_args(
                *command,
                sudo=sudo,
                pseudo_terminal=pseudo_terminal,
                env=env,
                log_command_level=log_command_level,
            )
            log.debug(f"Running {ssh_command!r} ...")
            return self.ctx.run(
                *ssh_command,
                check=check,
                capture=capture,
                interactive=pseudo_terminal,
                no_output_timeout_secs=self.ctx.parser.options.no_output_timeout_secs,
            )
        except subprocess.CalledProcessError as exc:
            log.error(str(exc))
            self.ctx.exit(exc.returncode)
        except (KeyboardInterrupt, SystemExit):
            pass

    def run_nox(
        self,
        nox_session: str,
        session_args: list[str] = None,
        nox_args: list[str] = None,
        env: dict[str, str] = None,
    ):
        cmd = [
            "nox",
            "--force-color",
            "-f",
            f"{self.upload_path.joinpath('noxfile.py').as_posix()}",
            "-e",
            nox_session,
        ]
        if nox_args:
            cmd += nox_args
        if session_args:
            cmd += ["--"] + session_args
        if env is None:
            env = {}
        if "CI" in os.environ:
            env["CI"] = os.environ["CI"]
        env["PYTHONUTF8"] = "1"
        env["OUTPUT_COLUMNS"] = str(self.ctx.console.width)
        env["GITHUB_ACTIONS_PIPELINE"] = "1"
        self.write_and_upload_dot_env(env)
        if self.is_windows is False and self.config.ssh_username != "root":
            sudo = True
        else:
            sudo = False
        ret = self.run(
            cmd,
            sudo=sudo,
            check=False,
            capture=False,
            pseudo_terminal=True,
        )
        self.ctx.exit(ret.returncode)

    def combine_coverage(self):
        """
        Combine the code coverage databases
        """
        self.run_nox("combine-coverage", session_args=[self.name])

    def compress_dependencies(self):
        """
        Compress .nox/ into nox.<vm-name>.tar.* in the VM
        """
        self.run_nox("compress-dependencies", session_args=[self.name])

    def decompress_dependencies(self):
        """
        Decompress nox.<vm-name>.tar.* if it exists in the VM
        """
        self.run_nox("decompress-dependencies", session_args=[self.name])

    def download_dependencies(self):
        """
        Download nox.<vm-name>.tar.* from VM
        """
        if self.is_windows:
            dependencies_filename = f"nox.{self.name}.tar.gz"
        else:
            dependencies_filename = f"nox.{self.name}.tar.xz"
        remote_path = self.upload_path.joinpath(dependencies_filename).as_posix()
        if self.is_windows:
            for drive in ("c:", "C:"):
                remote_path = remote_path.replace(drive, "/cygdrive/c")
        source = f"{self.name}:{remote_path}"
        destination = "."
        description = f"Downloading {dependencies_filename} ..."
        self.rsync(source, destination, description)

    def download_artifacts(self):
        """
        Download <upload-path>/artifacts from VM
        """
        remote_path = self.upload_path.joinpath("artifacts").as_posix()
        if self.is_windows:
            for drive in ("c:", "C:"):
                remote_path = remote_path.replace(drive, "/cygdrive/c")
        source = f"{self.name}:{remote_path}/"
        destination = "artifacts/"
        description = f"Downloading {source} ..."
        self.rsync(source, destination, description)

    def rsync(self, source, destination, description, rsync_flags: list[str] = None):
        """
        Rsync source into destination while showing progress.
        """
        rsync = shutil.which("rsync")
        if not rsync:
            self.ctx.exit(1, "Could find the 'rsync' binary")
        if TYPE_CHECKING:
            assert rsync
        cmd: list[str] = [
            rsync,
            "-az",
            "--info=none,progress2",
            "-e",
            " ".join(
                self.ssh_command_args(
                    include_vm_target=False, log_command_level=logging.NOTSET
                )
            ),
        ]
        if rsync_flags:
            cmd.extend(rsync_flags)
        cmd.extend(
            [
                source,
                destination,
            ]
        )
        log.info(f"Running {' '.join(cmd)!r}")  # type: ignore[arg-type]
        progress = create_progress_bar(transient=True)
        task = progress.add_task(description, total=100)
        with progress:
            proc = subprocess.Popen(cmd, bufsize=1, stdout=subprocess.PIPE, text=True)
            completed = 0
            while proc.poll() is None:
                if TYPE_CHECKING:
                    assert proc.stdout
                parts = proc.stdout.readline().strip().split()
                if parts:
                    completed = int(parts[1][:-1])
                    progress.update(task, completed=completed)
            progress.update(task, completed=100)

    def install_dependencies(self, nox_session: str):
        """
        Install test dependencies in VM.
        """
        return self.run_nox(
            nox_session,
            nox_args=["--install-only"],
            env={"PRINT_TEST_SELECTION": "0", "PRINT_SYSTEM_INFO": "0"},
        )

    def __repr__(self):
        return (
            f"VM(name={self.name!r}, ami={self.config.ami!r}, id={self.id!r}, "
            f"region={self.region_name!r} state={self.state!r})"
        )

    def ssh_command_args(
        self,
        *command: str,
        sudo: bool = False,
        include_vm_target: bool = True,
        pseudo_terminal: bool = False,
        env: list[str] = None,
        log_command_level: int = logging.INFO,
        ssh_options: list[str] | None = None,
    ) -> list[str]:
        ssh = shutil.which("ssh")
        if TYPE_CHECKING:
            assert ssh
        _ssh_command_args = [
            ssh,
            "-F",
            str(self.ssh_config_file.relative_to(REPO_ROOT)),
        ]
        if ssh_options:
            _ssh_command_args.extend(ssh_options)
        if pseudo_terminal is True:
            _ssh_command_args.append("-t")
        if include_vm_target:
            _ssh_command_args.append(self.name)
        remote_command = []
        if command:
            remote_command.append("--")
            if sudo:
                remote_command.append("sudo")
            if env:
                remote_command.append("env")
                remote_command.extend(env)
            remote_command.extend(list(command))
            log.log(
                log_command_level,
                f"Running {' '.join(remote_command[1:])!r} in {self.name}",
            )
            _ssh_command_args.extend(remote_command)
        return _ssh_command_args

    @property
    def is_windows(self):
        return "windows" in self.name

    @lru_cache(maxsize=1)
    def get_ec2_resource(self):
        return boto3.resource("ec2", region_name=self.region_name)

    @property
    def ec2(self):
        return self.get_ec2_resource()

    @property
    def id(self) -> str | None:
        if self.is_running:
            return cast(str, self.instance.id)
        return None

    @property
    def is_running(self) -> bool:
        if self.instance is None:
            return False
        running: bool = self.state == "running"
        return running

    @property
    def state(self) -> str | None:
        _state: str | None = None
        if self.instance:
            try:
                self.instance.reload()
                _state = self.instance.state["Name"]
            except ClientError:
                pass
        return _state

    @property
    def tempdir(self):
        return self.get_remote_tempdir()

    @lru_cache(maxsize=1)
    def get_remote_tempdir(self):
        cmd = [
            "-c",
            "import sys,tempfile; sys.stdout.write(tempfile.gettempdir()); sys.stdout.flush();",
        ]
        if self.is_windows is False:
            cmd.insert(0, "python3")
        else:
            cmd.insert(0, "python")
        ret = self.run(cmd, capture=True, check=False)
        if ret.returncode != 0:
            self.ctx.exit(ret.returncode, ret.stderr.strip())
        return ret.stdout.strip()

    @property
    def upload_path(self):
        return self.get_remote_upload_path()

    @lru_cache(maxsize=1)
    def get_remote_upload_path(self):
        if self.config.upload_path:
            return pathlib.Path(self.config.upload_path)
        if self.is_windows:
            return pathlib.PureWindowsPath(r"c:\Windows\Temp\testing")
        return pathlib.Path("/tmp/testing")


def create_progress_bar(**kwargs):
    return Progress(
        TextColumn(
            "[progress.description]{task.description}", table_column=Column(ratio=3)
        ),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        expand=True,
        **kwargs,
    )
