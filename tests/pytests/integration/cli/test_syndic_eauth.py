import json
import logging
import time

import pytest

from tests.conftest import CODE_DIR

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.timeout_unless_on_windows(600),
]


def json_output_to_dict(output):
    r"""
    Convert ``salt ... --out=json`` Syndic return to a dictionary. Since the
    --out=json will return several JSON outputs, e.g. {...}\n{...}, we have to
    parse that output individually.
    """
    output = output or ""
    results = {}
    for line in (
        _ for _ in output.replace("\n}", "\n}\x1f").split("\x1f") if _.strip()
    ):
        data = json.loads(line)
        if isinstance(data, dict):
            for minion in data:
                # Filter out syndic minions since they won't show up in the future
                if minion not in ("syndic_a", "syndic_b"):
                    results[minion] = data[minion]
    return results


@pytest.fixture(scope="module")
def syndic_network():
    try:
        client = docker.from_env()
    except docker.errors.DockerException as e:
        # Docker failed, it's gonna be an environment issue, let's just skip
        pytest.skip(f"Docker failed with error {e}")
    pool = docker.types.IPAMPool(
        subnet="172.27.13.0/24",
        gateway="172.27.13.1",
    )
    ipam_config = docker.types.IPAMConfig(
        pool_configs=[pool],
    )
    network = None
    try:
        network = client.networks.create(name="syndic_test_net", ipam=ipam_config)
        yield network.name
    finally:
        if network is not None:
            network.remove()


@pytest.fixture(scope="module")
def container_image_name():
    return "ghcr.io/saltstack/salt-ci-containers/salt:3006"


@pytest.fixture(scope="module")
def container_python_version():
    return "3.10"


@pytest.fixture(scope="module")
def config(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("eauth")
    master_dir = tmp_path / "master"
    minion_dir = tmp_path / "minion"
    syndic_a_dir = tmp_path / "syndic_a"
    syndic_b_dir = tmp_path / "syndic_b"
    minion_a1_dir = tmp_path / "minion_a1"
    minion_a2_dir = tmp_path / "minion_a2"
    minion_b1_dir = tmp_path / "minion_b1"
    minion_b2_dir = tmp_path / "minion_b2"

    for dir_ in (
        master_dir,
        minion_dir,
        syndic_a_dir,
        syndic_b_dir,
        minion_a1_dir,
        minion_a2_dir,
        minion_b1_dir,
        minion_b2_dir,
    ):
        dir_.mkdir(parents=True, exist_ok=True)
        (dir_ / "master.d").mkdir(exist_ok=True)
        # minion.d is probably needed to prevent errors on tempdir cleanup
        (dir_ / "minion.d").mkdir(exist_ok=True)
        (dir_ / "pki").mkdir(exist_ok=True)
    (master_dir / "master.d").mkdir(exist_ok=True)

    master_config_path = master_dir / "master"
    master_config_path.write_text(
        """
open_mode: True
auth.pam.python: /usr/local/bin/python3
order_masters: True

publisher_acl:
  bob:
    - '*1':
      - test.*
      - file.touch

external_auth:
  pam:
    bob:
      - '*1':
        - test.*
        - file.touch

nodegroups:
  second_string: "minion_*2"
  b_string: "minion_b*"

    """
    )

    minion_config_path = minion_dir / "minion"
    minion_config_path.write_text("id: minion\nmaster: master\nopen_mode: True")

    syndic_a_minion_config_path = syndic_a_dir / "minion"
    syndic_a_minion_config_path.write_text(
        "id: syndic_a\nmaster: master\nopen_mode: True"
    )
    syndic_a_master_config_path = syndic_a_dir / "master"
    syndic_a_master_config_path.write_text(
        """
open_mode: True
auth.pam.python: /usr/local/bin/python3
syndic_master: master
publisher_acl:
  bob:
    - '*1':
      - test.*
      - file.touch

external_auth:
  pam:
    bob:
      - '*1':
        - test.*
        - file.touch
    """
    )

    minion_a1_config_path = minion_a1_dir / "minion"
    minion_a1_config_path.write_text("id: minion_a1\nmaster: syndic_a\nopen_mode: True")
    minion_a2_config_path = minion_a2_dir / "minion"
    minion_a2_config_path.write_text("id: minion_a2\nmaster: syndic_a\nopen_mode: True")

    syndic_b_minion_config_path = syndic_b_dir / "minion"
    syndic_b_minion_config_path.write_text(
        "id: syndic_b\nmaster: master\nopen_mode: True"
    )
    syndic_b_master_config_path = syndic_b_dir / "master"
    syndic_b_master_config_path.write_text("syndic_master: master\nopen_mode: True")

    minion_b1_config_path = minion_b1_dir / "minion"
    minion_b1_config_path.write_text("id: minion_b1\nmaster: syndic_b\nopen_mode: True")
    minion_b2_config_path = minion_b2_dir / "minion"
    minion_b2_config_path.write_text("id: minion_b2\nmaster: syndic_b\nopen_mode: True")

    return {
        "minion_dir": minion_dir,
        "master_dir": master_dir,
        "syndic_a_dir": syndic_a_dir,
        "syndic_b_dir": syndic_b_dir,
        "minion_a1_dir": minion_a1_dir,
        "minion_a2_dir": minion_a2_dir,
        "minion_b1_dir": minion_b1_dir,
        "minion_b2_dir": minion_b2_dir,
    }


@pytest.fixture(scope="module")
def docker_master(
    salt_factories,
    syndic_network,
    config,
    container_image_name,
    container_python_version,
):
    config_dir = str(config["master_dir"])
    container = salt_factories.get_container(
        "master",
        image_name=container_image_name,
        container_run_kwargs={
            # "entrypoint": "salt-master -ldebug",
            "entrypoint": "python -m http.server",
            "network": syndic_network,
            "volumes": {
                config_dir: {"bind": "/etc/salt", "mode": "z"},
                str(CODE_DIR / "salt"): {
                    "bind": f"/usr/local/lib/python{container_python_version}/site-packages/salt/",
                    "mode": "z",
                },
            },
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    # container.container_start_check(confirm_container_started, container)
    with container.started() as factory:
        for user in ("bob", "fnord"):
            ret = container.run(f"adduser {user}")
            assert ret.returncode == 0
            ret = container.run(f"passwd -d {user}")
            assert ret.returncode == 0
        yield factory


@pytest.fixture(scope="module")
def docker_minion(
    salt_factories,
    syndic_network,
    config,
    container_image_name,
    container_python_version,
):
    config_dir = str(config["minion_dir"])
    container = salt_factories.get_container(
        "minion",
        image_name=container_image_name,
        container_run_kwargs={
            # "entrypoint": "salt-minion",
            "entrypoint": "python -m http.server",
            "network": syndic_network,
            "volumes": {
                config_dir: {"bind": "/etc/salt", "mode": "z"},
                str(CODE_DIR / "salt"): {
                    "bind": f"/usr/local/lib/python{container_python_version}/site-packages/salt/",
                    "mode": "z",
                },
            },
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    # container.container_start_check(confirm_container_started, container)
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def docker_syndic_a(
    salt_factories,
    config,
    syndic_network,
    container_image_name,
    container_python_version,
):
    config_dir = str(config["syndic_a_dir"])
    container = salt_factories.get_container(
        "syndic_a",
        image_name=container_image_name,
        container_run_kwargs={
            # "entrypoint": "salt-master -ldebug",
            "entrypoint": "python -m http.server",
            "network": syndic_network,
            "volumes": {
                config_dir: {"bind": "/etc/salt", "mode": "z"},
                str(CODE_DIR / "salt"): {
                    "bind": f"/usr/local/lib/python{container_python_version}/site-packages/salt/",
                    "mode": "z",
                },
            },
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    # container.container_start_check(confirm_container_started, container)
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def docker_syndic_b(
    salt_factories,
    config,
    syndic_network,
    container_image_name,
    container_python_version,
):
    config_dir = str(config["syndic_b_dir"])
    container = salt_factories.get_container(
        "syndic_b",
        image_name=container_image_name,
        container_run_kwargs={
            # "entrypoint": "salt-master -ldebug",
            "entrypoint": "python -m http.server",
            "network": syndic_network,
            "volumes": {
                config_dir: {"bind": "/etc/salt", "mode": "z"},
                str(CODE_DIR / "salt"): {
                    "bind": f"/usr/local/lib/python{container_python_version}/site-packages/salt/",
                    "mode": "z",
                },
            },
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    # container.container_start_check(confirm_container_started, container)
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def docker_minion_a1(
    salt_factories,
    config,
    syndic_network,
    container_image_name,
    container_python_version,
):
    config_dir = str(config["minion_a1_dir"])
    container = salt_factories.get_container(
        "minion_a1",
        image_name=container_image_name,
        container_run_kwargs={
            "network": syndic_network,
            # "entrypoint": "salt-minion -ldebug",
            "entrypoint": "python -m http.server",
            "volumes": {
                config_dir: {"bind": "/etc/salt", "mode": "z"},
                str(CODE_DIR / "salt"): {
                    "bind": f"/usr/local/lib/python{container_python_version}/site-packages/salt/",
                    "mode": "z",
                },
            },
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    # container.container_start_check(confirm_container_started, container)
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def docker_minion_a2(
    salt_factories,
    config,
    syndic_network,
    container_image_name,
    container_python_version,
):
    config_dir = str(config["minion_a2_dir"])
    container = salt_factories.get_container(
        "minion_a2",
        image_name=container_image_name,
        container_run_kwargs={
            "network": syndic_network,
            # "entrypoint": "salt-minion",
            "entrypoint": "python -m http.server",
            "volumes": {
                config_dir: {"bind": "/etc/salt", "mode": "z"},
                str(CODE_DIR / "salt"): {
                    "bind": f"/usr/local/lib/python{container_python_version}/site-packages/salt/",
                    "mode": "z",
                },
            },
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    # container.container_start_check(confirm_container_started, container)
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def docker_minion_b1(
    salt_factories,
    config,
    syndic_network,
    container_image_name,
    container_python_version,
):
    config_dir = str(config["minion_b1_dir"])
    container = salt_factories.get_container(
        "minion_b1",
        image_name=container_image_name,
        container_run_kwargs={
            "network": syndic_network,
            # "entrypoint": "salt-minion",
            "entrypoint": "python -m http.server",
            "volumes": {
                config_dir: {"bind": "/etc/salt", "mode": "z"},
                str(CODE_DIR / "salt"): {
                    "bind": f"/usr/local/lib/python{container_python_version}/site-packages/salt/",
                    "mode": "z",
                },
            },
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    # container.container_start_check(confirm_container_started, container)
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def docker_minion_b2(
    salt_factories,
    config,
    syndic_network,
    container_image_name,
    container_python_version,
):
    config_dir = str(config["minion_b2_dir"])
    container = salt_factories.get_container(
        "minion_b2",
        image_name=container_image_name,
        container_run_kwargs={
            "network": syndic_network,
            # "entrypoint": "salt-minion",
            "entrypoint": "python -m http.server",
            "volumes": {
                config_dir: {"bind": "/etc/salt", "mode": "z"},
                str(CODE_DIR / "salt"): {
                    "bind": f"/usr/local/lib/python{container_python_version}/site-packages/salt/",
                    "mode": "z",
                },
            },
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    # container.container_start_check(confirm_container_started, container)
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module", autouse=True)
def all_the_docker(
    docker_master,
    docker_minion,
    docker_syndic_a,
    docker_syndic_b,
    docker_minion_a1,
    docker_minion_a2,
    docker_minion_b1,
    docker_minion_b2,
):
    try:
        for s in (
            docker_master,
            docker_syndic_a,
            docker_syndic_b,
            docker_minion_a1,
            docker_minion_a2,
            docker_minion_b1,
            docker_minion_b2,
            docker_minion,
        ):
            s.run("python3 -m pip install looseversion packaging")
        # WORKAROUND
        for s in (docker_master, docker_syndic_a, docker_syndic_b):
            s.run("salt-master -d -ldebug")
        for s in (
            docker_minion_a1,
            docker_minion_a2,
            docker_minion_b1,
            docker_minion_b2,
            docker_minion,
        ):
            s.run("salt-minion -d")
        # END WORKAROUND
        for s in (docker_syndic_a, docker_syndic_b):
            s.run("salt-syndic -d")
        failure_time = time.time() + (5 * 60)
        results = None
        while time.time() < failure_time:
            res = docker_master.run(r"salt \* test.ping -t10 --out=json")
            results = json_output_to_dict(res.stdout)
            if set(results).issuperset(
                ["minion", "minion_a1", "minion_a2", "minion_b1", "minion_b2"]
            ):
                break
            time.sleep(5)
        else:
            pytest.skip(f"Missing some minions: {sorted(results)}")

        yield
    finally:
        # looks like we need to do this to actually let the test suite run as non-root.
        for container in (
            docker_minion,
            docker_syndic_a,
            docker_syndic_b,
            docker_minion_a1,
            docker_minion_a2,
            docker_minion_b1,
            docker_minion_b2,
        ):
            try:
                container.run("rm -rfv /etc/salt/")
                # If you need to debug this ^^^^^^^
                # use this vvvvvv
                # res = container.run('rm -rfv /etc/salt/')
                # print(container)
                # print(res.stdout)
            except docker.errors.APIError as exc:
                # if the container isn't running, there's not thing we can do
                # at this point.
                log.info(f"Docker failed removing /etc/salt: %s", exc)


@pytest.fixture(
    params=[
        ("*", ["minion", "minion_a1", "minion_a2", "minion_b1", "minion_b2"]),
        ("minion", ["minion"]),
        ("minion_*", ["minion_a1", "minion_a2", "minion_b1", "minion_b2"]),
        ("minion_a*", ["minion_a1", "minion_a2"]),
        ("minion_b*", ["minion_b1", "minion_b2"]),
        ("*1", ["minion_a1", "minion_b1"]),
        ("*2", ["minion_a2", "minion_b2"]),
    ]
)
def all_the_minions(request):
    yield request.param


@pytest.fixture(
    params=[
        ("minion_a1", ["minion_a1"]),
        ("minion_b1", ["minion_b1"]),
        ("*1", ["minion_a1", "minion_b1"]),
        ("minion*1", ["minion_a1", "minion_b1"]),
    ]
)
def eauth_valid_minions(request):
    yield request.param


@pytest.fixture(
    params=[
        "*",
        "minion",
        "minion_a2",
        "minion_b2",
        "syndic_a",
        "syndic_b",
        "*2",
        "minion*",
        "minion_a*",
        "minion_b*",
    ]
)
def eauth_blocked_minions(request):
    yield request.param


@pytest.fixture
def docker_minions(
    docker_minion,
    docker_minion_a1,
    docker_minion_a2,
    docker_minion_b1,
    docker_minion_b2,
):
    yield [
        docker_minion,
        docker_minion_a1,
        docker_minion_a2,
        docker_minion_b1,
        docker_minion_b2,
    ]


@pytest.fixture(
    params=[
        "test.arg good_argument",
        "test.arg bad_news",
        "test.arg not_allowed",
        "test.echo very_not_good",
        "cmd.run 'touch /tmp/fun.txt'",
        "file.touch /tmp/more_fun.txt",
        "test.arg_repr this_is_whatever",
        "test.arg_repr more whatever",
        "test.arg_repr cool guy",
    ]
)
def all_the_commands(request):
    yield request.param


@pytest.fixture(
    params=[
        "test.arg",
        "test.echo",
    ]
)
def eauth_valid_commands(request):
    yield request.param


@pytest.fixture(
    params=[
        "cmd.run",
        "file.manage_file",
        "test.arg_repr",
    ]
)
def eauth_invalid_commands(request):
    yield request.param


@pytest.fixture(
    params=[
        "good_argument",
        "good_things",
        "good_super_awesome_stuff",
    ]
)
def eauth_valid_arguments(request):
    # TODO: Should these be part of valid commands? I don't know yet! -W. Werner, 2022-12-01
    yield request.param


@pytest.fixture(
    params=[
        "bad_news",
        "not_allowed",
        "very_not_good",
    ]
)
def eauth_invalid_arguments(request):
    yield request.param


@pytest.fixture(
    params=[
        "G@id:minion_a1 and minion_b*",
        "E@minion_[^b]1 and minion_b2",
        "P@id:minion_[^b]. and minion",
        # TODO: Do soemthing better with these. Apparently lists work... weirdly -W. Werner, 2022-12-02
        # "L@minion_* not L@minion_*2 and minion",
        # "I@has_syndic:* not minion_b2 not minion_a2 and minion",
        # "J@has_syndic:syndic_(a|b) not *2 and minion",
        # TODO: I need to figure out a good way to get IPs -W. Werner, 2022-12-02
        # "S@172.13.1.4 and S@172.13.1.5 and minion_*2",
        # TODO:  I don't have any range servers -W. Werner, 2022-12-02
        # "((R@%minion_a1..2 and R@%minion_b1..2) not N@second_string) and minion",
    ]
)
def invalid_comprehensive_minion_targeting(request):
    yield request.param


@pytest.fixture(
    params=[
        (
            "G@id:minion or minion_a1 or E@minion_[^b]2 or L@minion_b1,minion_b2",
            ["minion", "minion_a1", "minion_a2", "minion_b1", "minion_b2"],
        ),
        (
            "minion or E@minion_a[12] or N@b_string",
            ["minion", "minion_a1", "minion_a2", "minion_b1", "minion_b2"],
        ),
        (
            "L@minion,minion_a1 or N@second_string or N@b_string",
            ["minion", "minion_a1", "minion_a2", "minion_b1", "minion_b2"],
        ),
        # TODO: I don't have pillar setup, nor do I know IPs, and also SECO range servers -W. Werner, 2022-12-02
        #        (
        #            "I@my_minion:minion and I@has_syndic:syndic_[^b] and S@172.13.1.4 and S@172.13.1.5",
        #            ["minion", "minion_a1", "minion_a2", "minion_b1", "minion_b2"],
        #        ),
        #        (
        #            "minion and R@%minion_a1..2 and N@b_string",
        #            ["minion", "minion_a1", "minion_a2", "minion_b1", "minion_b2"],
        #        ),
    ]
)
def comprehensive_minion_targeting(request):
    # TODO: include SECO range? -W. Werner, 2022-12-01
    yield request.param


@pytest.fixture(
    params=[
        ("G@id:minion_a1 and minion_b1", ["minion_a1", "minion_b1"]),
        ("E@minion_[^b]1", ["minion_a1"]),
        (
            "P@id:minion_[^b].",
            ["minion_a1", "minion_a2"],
        ),  # should this be this thing? or something different?
        # TODO: Turns out that it doesn't exclude things? Not sure -W. Werner, 2022-12-02
        (
            "L@minion_a1,minion_a2,minion_b1 not minion_*2",
            ["minion_a1", "minion_a2", "minion_b1"],
        ),
        # TODO: I don't have pillar data yet -W. Werner, 2022-12-02
        # ("I@has_syndic:* not minion_b2 not minion_a2", ["minion_a1", "minion_b1"]),
        # ("J@has_syndic:syndic_(a|b) not *2", ["minion_a1", "minion_b1"]),
        # TODO: Need a different way to get IPs -W. Werner, 2022-12-02
        # ( "S@172.13.1.4 and S@172.13.1.5", ["minion_a1", "minion_b1"]),
        # TODO: Need a range server for these tests (see range targeting docs) -W. Werner, 2022-12-02
        # ("(R@%minion_a1..2 and R@%minion_b1..2) not N@second_string", ["minion_a1", "minion_b1"]),
    ]
)
def valid_comprehensive_minion_targeting(request):
    yield request.param


@pytest.fixture(
    params=[
        # TODO: not sure why this doesn't work. Pretty sure it's just the cli part -W. Werner, 2022-12-02
        # ("G@id:minion_a1 and minion_b1", ["minion_a1", "minion_b1"]),
        ("E@minion_[^b]1", ["minion_a1"]),
        (
            "P@id:minion_[^a]1",
            ["minion_b1"],
        ),
        ("L@minion_a1,minion_b1 not minion_*2", ["minion_a1", "minion_b1"]),
        # TODO: need to add pillars -W. Werner, 2022-12-02
        # ("I@has_syndic:* not minion_b2 not minion_a2", ["minion_a1", "minion_b1"]),
        # ("J@has_syndic:syndic_(a|b) not *2", ["minion_a1", "minion_b1"]),
        # TODO: Need a different way to get IPs -W. Werner, 2022-12-02
        # ( "S@172.13.1.4 and S@172.13.1.5", ["minion_a1", "minion_b1"]),
        # TODO: Need a range server for these tests (see range targeting docs) -W. Werner, 2022-12-02
        # ("(R@%minion_a1..2 and R@%minion_b1..2) not N@second_string", ["minion_a1", "minion_b1"]),
    ]
)
def valid_eauth_comprehensive_minion_targeting(request):
    yield request.param


def test_root_user_should_be_able_to_call_any_and_all_minions_with_any_and_all_commands(
    all_the_minions, all_the_commands, docker_master
):
    target, expected_minions = all_the_minions
    res = docker_master.run(
        f"salt {target} {all_the_commands} -t 10 --out=json",
    )
    if "jid does not exist" in (res.stderr or ""):
        # might be flaky, let's retry
        res = docker_master.run(
            f"salt {target} {all_the_commands} -t 10 --out=json",
        )
    results = json_output_to_dict(res.stdout)
    assert sorted(results) == expected_minions, res.stdout


def test_eauth_user_should_be_able_to_target_valid_minions_with_valid_command(
    eauth_valid_minions, eauth_valid_commands, eauth_valid_arguments, docker_master
):
    target, expected_minions = eauth_valid_minions
    res = docker_master.run(
        f"salt -a pam --username bob --password '' {target} {eauth_valid_commands} {eauth_valid_arguments} -t 10 --out=json",
    )
    results = json_output_to_dict(res.stdout)
    assert sorted(results) == expected_minions, res.stdout


def test_eauth_user_should_not_be_able_to_target_invalid_minions(
    eauth_blocked_minions, docker_master, docker_minions
):
    res = docker_master.run(
        f"salt -a pam --username bob --password '' {eauth_blocked_minions} file.touch /tmp/bad_bad_file.txt -t 10 --out=json",
    )
    assert "Authorization error occurred." == res.data or res.data is None
    for minion in docker_minions:
        res = minion.run("test -f /tmp/bad_bad_file.txt")
        file_exists = res.returncode == 0
        assert not file_exists


@pytest.mark.skip(reason="Not sure about blocklist")
def test_eauth_user_should_not_be_able_to_target_valid_minions_with_invalid_commands(
    eauth_valid_minions, eauth_invalid_commands, docker_master
):
    tgt, _ = eauth_valid_minions
    res = docker_master.run(
        f"salt -a pam --username bob --password '' {tgt} {eauth_invalid_commands} -t 10 --out=json",
    )
    results = json_output_to_dict(res.stdout)
    assert "Authorization error occurred" in res.stdout
    assert sorted(results) == []


@pytest.mark.skip(reason="Not sure about blocklist")
def test_eauth_user_should_not_be_able_to_target_valid_minions_with_valid_commands_and_invalid_arguments(
    eauth_valid_minions, eauth_valid_commands, eauth_invalid_arguments, docker_master
):
    tgt, _ = eauth_valid_minions
    res = docker_master.run(
        f"salt -a pam --username bob --password '' -C '{tgt}' {eauth_valid_commands} {eauth_invalid_arguments} -t 10 --out=json",
    )
    results = json_output_to_dict(res.stdout)
    assert "Authorization error occurred" in res.stdout
    assert sorted(results) == []


def test_invalid_eauth_user_should_not_be_able_to_do_anything(
    eauth_valid_minions, eauth_valid_commands, eauth_valid_arguments, docker_master
):
    # TODO: Do we really need to run all of these tests for the invalid user? Maybe not! -W. Werner, 2022-12-01
    tgt, _ = eauth_valid_minions
    res = docker_master.run(
        f"salt -a pam --username badguy --password '' -C '{tgt}' {eauth_valid_commands} {eauth_valid_arguments} -t 10 --out=json",
    )
    results = json_output_to_dict(res.stdout)
    assert sorted(results) == []


def test_root_should_be_able_to_use_comprehensive_targeting(
    comprehensive_minion_targeting, docker_master
):
    tgt, expected_minions = comprehensive_minion_targeting
    res = docker_master.run(
        f"salt -C '{tgt}' test.version -t 10 --out=json",
    )
    results = json_output_to_dict(res.stdout)
    assert sorted(results) == expected_minions


def test_eauth_user_should_be_able_to_target_valid_minions_with_valid_commands_comprehensively(
    valid_eauth_comprehensive_minion_targeting, docker_master
):
    tgt, expected_minions = valid_eauth_comprehensive_minion_targeting
    res = docker_master.run(
        f"salt -a pam --username bob --password '' -C '{tgt}' test.version -t 10 --out=json",
    )
    results = json_output_to_dict(res.stdout)
    assert sorted(results) == expected_minions


def test_eauth_user_with_invalid_comprehensive_targeting_should_auth_failure(
    invalid_comprehensive_minion_targeting, docker_master
):
    res = docker_master.run(
        f"salt -a pam --username fnord --password '' -C '{invalid_comprehensive_minion_targeting}' test.version -t 10 --out=json",
    )
    results = json_output_to_dict(res.stdout)
    assert "Authorization error occurred" in res.stdout
    assert sorted(results) == []
