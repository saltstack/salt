import shutil
import textwrap
import time

import attr
import pytest

from tests.conftest import FIPS_TESTRUN


@attr.s
class BlackoutPillar:
    pillar_state_tree = attr.ib(repr=False)
    salt_cli = attr.ib(repr=False)
    top_file = attr.ib(init=False)
    minion_1_id = attr.ib(repr=False)
    minion_1_pillar = attr.ib(init=False)
    minion_2_id = attr.ib(repr=False)
    minion_2_pillar = attr.ib(init=False)
    in_blackout = attr.ib(default=False)

    def __attrs_post_init__(self):
        self.top_file = self.pillar_state_tree / "top.sls"
        top_file_contents = textwrap.dedent(
            """\
        base:
          {}:
            - minion-1-pillar
          {}:
            - minion-2-pillar
        """.format(
                self.minion_1_id, self.minion_2_id
            )
        )
        self.top_file.write_text(top_file_contents)
        self.minion_1_pillar = self.pillar_state_tree / "minion-1-pillar.sls"
        self.minion_2_pillar = self.pillar_state_tree / "minion-2-pillar.sls"
        self.minion_1_pillar.write_text("minion_blackout: false")
        self.minion_2_pillar.write_text("minion_blackout: false")
        self.refresh_pillar()

    def enter_blackout(self, pillar_contents=None):
        if pillar_contents is None:
            pillar_contents = "minion_blackout: false"
        if pillar_contents.startswith("\n"):
            pillar_contents = pillar_contents[1:]
        pillar_contents = textwrap.dedent(pillar_contents)
        self.minion_1_pillar.write_text(pillar_contents)
        self.refresh_pillar(exiting_blackout=False)
        self.in_blackout = True
        return self.__enter__()  # pylint: disable=unnecessary-dunder-call

    def exit_blackout(self):
        if self.in_blackout:
            self.minion_1_pillar.write_text("minion_blackout: false")
            self.refresh_pillar(exiting_blackout=True)
            self.in_blackout = False

    def refresh_pillar(self, timeout=60, sleep=0.5, exiting_blackout=None):
        ret = self.salt_cli.run("saltutil.refresh_pillar", wait=True, minion_tgt="*")
        assert ret.returncode == 0
        assert self.minion_1_id in ret.data
        assert self.minion_2_id in ret.data
        stop_at = time.time() + timeout
        while True:
            if time.time() > stop_at:
                if exiting_blackout is True:
                    pytest.fail(
                        "Minion did not exit blackout mode after {} seconds".format(
                            timeout
                        )
                    )
                elif exiting_blackout is False:
                    pytest.fail(
                        "Minion did not enter blackout mode after {} seconds".format(
                            timeout
                        )
                    )
                else:
                    pytest.fail(
                        f"Minion did not refresh pillar after {timeout} seconds"
                    )

            time.sleep(sleep)

            ret = self.salt_cli.run("pillar.get", "minion_blackout", minion_tgt="*")
            if not ret.data:
                # Something is wrong here. Try again
                continue
            assert self.minion_1_id in ret.data
            assert self.minion_2_id in ret.data
            if ret.data[self.minion_1_id] == "" or ret.data[self.minion_2_id] == "":
                # Pillar not found
                continue

            # Minion 2 must NEVER enter blackout
            assert ret.data[self.minion_2_id] is False

            if exiting_blackout is True and ret.data[self.minion_1_id] is not False:
                continue
            elif (
                exiting_blackout is False
                and "Minion in blackout mode" not in ret.data[self.minion_1_id]
            ):
                continue
            # We got the pillar we're after, break out of the loop
            break

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.exit_blackout()


@pytest.fixture(scope="package")
def pillar_state_tree(tmp_path_factory):
    _pillar_state_tree = tmp_path_factory.mktemp("pillar")
    try:
        yield _pillar_state_tree
    finally:
        shutil.rmtree(str(_pillar_state_tree), ignore_errors=True)


@pytest.fixture(scope="package")
def salt_master(salt_factories, pillar_state_tree):
    config_defaults = {
        "pillar_roots": {"base": [str(pillar_state_tree)]},
        "open_mode": True,
    }
    config_overrides = {
        "interface": "127.0.0.1",
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        "blackout-master",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="package")
def salt_minion_1(salt_master):
    factory = salt_master.salt_minion_daemon(
        "blackout-minion-1",
        defaults={"open_mode": True},
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        },
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="package")
def salt_minion_2(salt_master):
    factory = salt_master.salt_minion_daemon(
        "blackout-minion-2",
        defaults={"open_mode": True},
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        },
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="package")
def salt_cli(salt_master):
    return salt_master.salt_cli()


@pytest.fixture(scope="package")
def blackout_pillar(salt_cli, pillar_state_tree, salt_minion_1, salt_minion_2):
    return BlackoutPillar(
        pillar_state_tree=pillar_state_tree,
        salt_cli=salt_cli,
        minion_1_id=salt_minion_1.id,
        minion_2_id=salt_minion_2.id,
    )


@pytest.fixture
def blackout(blackout_pillar):
    try:
        yield blackout_pillar
    finally:
        blackout_pillar.exit_blackout()
