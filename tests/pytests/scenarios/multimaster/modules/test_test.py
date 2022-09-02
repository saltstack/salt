import pytest

import salt.config
import salt.version

pytestmark = [
    pytest.mark.slow_test,
]


def test_ping(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.ping
    """
    ret = mm_master_1_salt_cli.run("test.ping", minion_tgt=salt_mm_minion_1.id)
    assert ret.returncode == 0
    assert ret.data is True

    ret = mm_master_2_salt_cli.run("test.ping", minion_tgt=salt_mm_minion_1.id)
    assert ret.returncode == 0
    assert ret.data is True

    ret = mm_master_1_salt_cli.run("test.ping", minion_tgt=salt_mm_minion_2.id)
    assert ret.returncode == 0
    assert ret.data is True

    ret = mm_master_2_salt_cli.run("test.ping", minion_tgt=salt_mm_minion_2.id)
    assert ret.returncode == 0
    assert ret.data is True


def test_echo(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.echo
    """
    ret = mm_master_1_salt_cli.run("test.echo", "text", minion_tgt=salt_mm_minion_1.id)
    assert ret.returncode == 0
    assert ret.data == "text"

    ret = mm_master_2_salt_cli.run("test.echo", "text", minion_tgt=salt_mm_minion_1.id)
    assert ret.returncode == 0
    assert ret.data == "text"

    ret = mm_master_1_salt_cli.run("test.echo", "text", minion_tgt=salt_mm_minion_2.id)
    assert ret.returncode == 0
    assert ret.data == "text"

    ret = mm_master_2_salt_cli.run("test.echo", "text", minion_tgt=salt_mm_minion_2.id)
    assert ret.returncode == 0
    assert ret.data == "text"


def test_version(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.version
    """
    ret = mm_master_1_salt_cli.run("test.version", minion_tgt=salt_mm_minion_1.id)
    assert ret.returncode == 0
    assert ret.data == salt.version.__saltstack_version__.string

    ret = mm_master_2_salt_cli.run("test.version", minion_tgt=salt_mm_minion_1.id)
    assert ret.returncode == 0
    assert ret.data == salt.version.__saltstack_version__.string

    ret = mm_master_1_salt_cli.run("test.version", minion_tgt=salt_mm_minion_2.id)
    assert ret.returncode == 0
    assert ret.data == salt.version.__saltstack_version__.string

    ret = mm_master_2_salt_cli.run("test.version", minion_tgt=salt_mm_minion_2.id)
    assert ret.returncode == 0
    assert ret.data == salt.version.__saltstack_version__.string


def test_conf_test(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.conf_text
    """
    ret = mm_master_1_salt_cli.run("test.conf_test", minion_tgt=salt_mm_minion_1.id)
    assert ret.returncode == 0
    assert ret.data == "baz"

    ret = mm_master_2_salt_cli.run("test.conf_test", minion_tgt=salt_mm_minion_1.id)
    assert ret.returncode == 0
    assert ret.data == "baz"

    ret = mm_master_1_salt_cli.run("test.conf_test", minion_tgt=salt_mm_minion_2.id)
    assert ret.returncode == 0
    assert ret.data == "baz"

    ret = mm_master_2_salt_cli.run("test.conf_test", minion_tgt=salt_mm_minion_2.id)
    assert ret.returncode == 0
    assert ret.data == "baz"


def test_cross_test(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.cross_text
    """
    ret = mm_master_1_salt_cli.run(
        "test.cross_test", "test.ping", minion_tgt=salt_mm_minion_1.id
    )
    assert ret.returncode == 0
    assert ret.data is True

    ret = mm_master_2_salt_cli.run(
        "test.cross_test", "test.ping", minion_tgt=salt_mm_minion_1.id
    )
    assert ret.returncode == 0
    assert ret.data is True

    ret = mm_master_1_salt_cli.run(
        "test.cross_test", "test.ping", minion_tgt=salt_mm_minion_2.id
    )
    assert ret.returncode == 0
    assert ret.data is True

    ret = mm_master_2_salt_cli.run(
        "test.cross_test", "test.ping", minion_tgt=salt_mm_minion_2.id
    )
    assert ret.returncode == 0
    assert ret.data is True


def test_outputter(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.outputter
    """
    ret = mm_master_1_salt_cli.run(
        "test.outputter", "text", minion_tgt=salt_mm_minion_1.id
    )
    assert ret.returncode == 0
    assert ret.data == "text"

    ret = mm_master_2_salt_cli.run(
        "test.outputter", "text", minion_tgt=salt_mm_minion_1.id
    )
    assert ret.returncode == 0
    assert ret.data == "text"

    ret = mm_master_1_salt_cli.run(
        "test.outputter", "text", minion_tgt=salt_mm_minion_2.id
    )
    assert ret.returncode == 0
    assert ret.data == "text"

    ret = mm_master_2_salt_cli.run(
        "test.outputter", "text", minion_tgt=salt_mm_minion_2.id
    )
    assert ret.returncode == 0
    assert ret.data == "text"


def test_fib(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.fib
    """
    ret = mm_master_1_salt_cli.run("test.fib", "20", minion_tgt=salt_mm_minion_1.id)
    assert ret.returncode == 0
    assert ret.data[0] == 6765

    ret = mm_master_2_salt_cli.run("test.fib", "20", minion_tgt=salt_mm_minion_1.id)
    assert ret.returncode == 0
    assert ret.data[0] == 6765

    ret = mm_master_1_salt_cli.run("test.fib", "20", minion_tgt=salt_mm_minion_2.id)
    assert ret.returncode == 0
    assert ret.data[0] == 6765

    ret = mm_master_2_salt_cli.run("test.fib", "20", minion_tgt=salt_mm_minion_2.id)
    assert ret.returncode == 0
    assert ret.data[0] == 6765


def test_collatz(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.fib
    """
    ret = mm_master_1_salt_cli.run("test.collatz", "40", minion_tgt=salt_mm_minion_1.id)
    assert ret.returncode == 0
    assert ret.data[0][-1] == 2

    ret = mm_master_2_salt_cli.run("test.collatz", "40", minion_tgt=salt_mm_minion_1.id)
    assert ret.returncode == 0
    assert ret.data[0][-1] == 2

    ret = mm_master_1_salt_cli.run("test.collatz", "40", minion_tgt=salt_mm_minion_2.id)
    assert ret.returncode == 0
    assert ret.data[0][-1] == 2

    ret = mm_master_2_salt_cli.run("test.collatz", "40", minion_tgt=salt_mm_minion_2.id)
    assert ret.returncode == 0
    assert ret.data[0][-1] == 2


def test_get_opts(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.conf_text
    """
    ret = mm_master_1_salt_cli.run("test.get_opts", minion_tgt=salt_mm_minion_1.id)
    assert ret.returncode == 0
    assert ret.data["cachedir"] == salt_mm_minion_1.config["cachedir"]

    ret = mm_master_2_salt_cli.run("test.get_opts", minion_tgt=salt_mm_minion_1.id)
    assert ret.returncode == 0
    assert ret.data["cachedir"] == salt_mm_minion_1.config["cachedir"]

    ret = mm_master_1_salt_cli.run("test.get_opts", minion_tgt=salt_mm_minion_2.id)
    assert ret.returncode == 0
    assert ret.data["cachedir"] == salt_mm_minion_2.config["cachedir"]

    ret = mm_master_2_salt_cli.run("test.get_opts", minion_tgt=salt_mm_minion_2.id)
    assert ret.returncode == 0
    assert ret.data["cachedir"] == salt_mm_minion_2.config["cachedir"]
