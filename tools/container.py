import os
import pathlib
import platform
import tempfile

from ptscripts import Context, command_group

cmd = command_group(name="container", help="Container Commands", description=__doc__)


architecture = platform.machine().lower()


def has_network(ctx, name):
    p = ctx.run("docker", "network", "ls", capture=True)
    return name in p.stdout.decode()


def create_network(ctx, name):
    p = ctx.run(
        "docker",
        "network",
        "create",
        "-o",
        "com.docker.network.driver.mtu=1500",
        "--ipv6",
        "--subnet",
        "2001:db8::/64",
        name,
    )
    if p.returncode != 0:
        raise RuntimeError(f"docker network create returned {p.returncode}")


@cmd.command(
    name="create",
    arguments={
        "image": {"help": "Name the container image to use."},
        "name": {"help": "Name the container being created.", "default": ""},
        "platform": {"help": "The platform to run tests as,", "default": ""},
    },
)
def create(ctx: Context, image: str, name: str = "", platform: str = ""):
    onci = "GITHUB_WORKFLOW" in os.environ
    workdir = "/salt"
    home = "/root"
    network = "ip6net"
    tmpdir = tempfile.mkdtemp(prefix="salt-test-container")
    if not onci and not has_network(ctx, network):
        ctx.info(f"Creating docker network: {network}")
        create_network(ctx, network)
    if onci:
        cwdname = pathlib.Path().resolve().name
        workdir = f"/__w/{cwdname}/{cwdname}"
        home = "/github/home"
    env = {
        "HOME": home,
        "SKIP_REQUIREMENTS_INSTALL": "1",
        "PRINT_TEST_SELECTION": "0",
        "PRINT_TEST_PLAN_ONLY": "0",
        "PRINT_SYSTEM_INFO": "0",
        "RERUN_FAILURES": "0",
        "SKIP_INITIAL_ONEDIR_FAILURES": "1",
        "SKIP_INITIAL_GH_ACTIONS_FAILURES": "1",
        "RAISE_DEPRECATIONS_RUNTIME_ERRORS": "1",
        "LANG": "en_US.UTF-8",
        "SHELL": "/bin/bash",
    }
    for var in [
        "PIP_INDEX_URL",
        "PIP_EXTRA_INDEX_URL",
        "PIP_TRUSTED_HOST",
        "PIP_DISABLE_PIP_VERSION_CHECK",
        "SALT_TRANSPORT",
        # Are both of these really needed?
        "GITHUB_ACTIONS",
        "GITHUB_ACTIONS_PIPELINE",
        "CI",
        "SKIP_CODE_COVERAGE",
        "COVERAGE_CONTEXT",
        "RERUN_FAILURES",
        "COLUMNS",
    ]:
        if var in os.environ:
            env[var] = os.environ[var]

    pathlib.Path("/tmp/docker-var").mkdir(exist_ok=True)

    cmd = [
        "/usr/bin/docker",
        "create",
        f"--name={name}",
        "--privileged",
        f"--workdir={workdir}",
        "-v",
        f"{tmpdir}:/var/lib/docker",
    ]
    if platform:
        if platform == "aarch64" or platform == "arm64":
            if architecture == "x86_64":
                cmd.extend(["--platform", "linux/arm64/v8"])
        elif platform == "x86_64":
            if "arm" in architecture or "aarch64" in architecture:
                cmd.extend(["--platform", "linux/amd64"])
    if "--platform" in cmd:
        proc = ctx.run(*["docker", "image", "ls"], capture=True, check=True)
        if "multiarch/qemu-user-static" not in proc.stdout.decode():
            ctx.info(
                "Installing multiarch/qemu-user-static image for emulation support"
            )
            ctx.run(
                *[
                    "docker",
                    "run",
                    "--rm",
                    "--privileged",
                    "multiarch/qemu-user-static",
                    "--reset",
                    "-p",
                    "yes",
                ],
                capture=True,
                check=True,
            )
    for key in env:
        cmd.extend(["-e", f"{key}={env[key]}"])
    if onci:
        cmd.extend(["-v", "/home/runner/work:/__w"])
    else:
        cmd.extend(["-v", f"{os.getcwd()}:/salt"])
        cmd.extend(["--network", network])
    if name:
        cmd.extend(["--name", name])
    cmd.extend(
        [
            "--entrypoint",
            "/usr/lib/systemd/systemd",
            image,
            "--systemd",
            "--unit",
            "rescue.target",
        ],
    )
    ctx.info(f"command is: {cmd}")
    ret = ctx.run(*cmd, capture=True, check=False)
    if ret.returncode != 0:
        ctx.warn(ret.stderr.decode())
