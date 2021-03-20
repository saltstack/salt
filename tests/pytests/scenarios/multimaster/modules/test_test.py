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
    assert ret.exitcode == 0
    assert ret.json is True

    ret = mm_master_2_salt_cli.run("test.ping", minion_tgt=salt_mm_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json is True

    ret = mm_master_1_salt_cli.run("test.ping", minion_tgt=salt_mm_minion_2.id)
    assert ret.exitcode == 0
    assert ret.json is True

    ret = mm_master_2_salt_cli.run("test.ping", minion_tgt=salt_mm_minion_2.id)
    assert ret.exitcode == 0
    assert ret.json is True


def test_echo(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.echo
    """
    ret = mm_master_1_salt_cli.run("test.echo", "text", minion_tgt=salt_mm_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json == "text"

    ret = mm_master_2_salt_cli.run("test.echo", "text", minion_tgt=salt_mm_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json == "text"

    ret = mm_master_1_salt_cli.run("test.echo", "text", minion_tgt=salt_mm_minion_2.id)
    assert ret.exitcode == 0
    assert ret.json == "text"

    ret = mm_master_2_salt_cli.run("test.echo", "text", minion_tgt=salt_mm_minion_2.id)
    assert ret.exitcode == 0
    assert ret.json == "text"


def test_version(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.version
    """
    ret = mm_master_1_salt_cli.run("test.version", minion_tgt=salt_mm_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json == salt.version.__saltstack_version__.string

    ret = mm_master_2_salt_cli.run("test.version", minion_tgt=salt_mm_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json == salt.version.__saltstack_version__.string

    ret = mm_master_1_salt_cli.run("test.version", minion_tgt=salt_mm_minion_2.id)
    assert ret.exitcode == 0
    assert ret.json == salt.version.__saltstack_version__.string

    ret = mm_master_2_salt_cli.run("test.version", minion_tgt=salt_mm_minion_2.id)
    assert ret.exitcode == 0
    assert ret.json == salt.version.__saltstack_version__.string


def test_conf_test(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.conf_text
    """
    ret = mm_master_1_salt_cli.run("test.conf_test", minion_tgt=salt_mm_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json == "baz"

    ret = mm_master_2_salt_cli.run("test.conf_test", minion_tgt=salt_mm_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json == "baz"

    ret = mm_master_1_salt_cli.run("test.conf_test", minion_tgt=salt_mm_minion_2.id)
    assert ret.exitcode == 0
    assert ret.json == "baz"

    ret = mm_master_2_salt_cli.run("test.conf_test", minion_tgt=salt_mm_minion_2.id)
    assert ret.exitcode == 0
    assert ret.json == "baz"


def test_cross_test(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.cross_text
    """
    ret = mm_master_1_salt_cli.run(
        "test.cross_test", "test.ping", minion_tgt=salt_mm_minion_1.id
    )
    assert ret.exitcode == 0
    assert ret.json is True

    ret = mm_master_2_salt_cli.run(
        "test.cross_test", "test.ping", minion_tgt=salt_mm_minion_1.id
    )
    assert ret.exitcode == 0
    assert ret.json is True

    ret = mm_master_1_salt_cli.run(
        "test.cross_test", "test.ping", minion_tgt=salt_mm_minion_2.id
    )
    assert ret.exitcode == 0
    assert ret.json is True

    ret = mm_master_2_salt_cli.run(
        "test.cross_test", "test.ping", minion_tgt=salt_mm_minion_2.id
    )
    assert ret.exitcode == 0
    assert ret.json is True


def test_outputter(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.outputter
    """
    ret = mm_master_1_salt_cli.run(
        "test.outputter", "text", minion_tgt=salt_mm_minion_1.id
    )
    assert ret.exitcode == 0
    assert ret.json == "text"

    ret = mm_master_2_salt_cli.run(
        "test.outputter", "text", minion_tgt=salt_mm_minion_1.id
    )
    assert ret.exitcode == 0
    assert ret.json == "text"

    ret = mm_master_1_salt_cli.run(
        "test.outputter", "text", minion_tgt=salt_mm_minion_2.id
    )
    assert ret.exitcode == 0
    assert ret.json == "text"

    ret = mm_master_2_salt_cli.run(
        "test.outputter", "text", minion_tgt=salt_mm_minion_2.id
    )
    assert ret.exitcode == 0
    assert ret.json == "text"


def test_fib(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.fib
    """
    ret = mm_master_1_salt_cli.run("test.fib", "20", minion_tgt=salt_mm_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json[0] == 6765

    ret = mm_master_2_salt_cli.run("test.fib", "20", minion_tgt=salt_mm_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json[0] == 6765

    ret = mm_master_1_salt_cli.run("test.fib", "20", minion_tgt=salt_mm_minion_2.id)
    assert ret.exitcode == 0
    assert ret.json[0] == 6765

    ret = mm_master_2_salt_cli.run("test.fib", "20", minion_tgt=salt_mm_minion_2.id)
    assert ret.exitcode == 0
    assert ret.json[0] == 6765


def test_collatz(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.fib
    """
    ret = mm_master_1_salt_cli.run("test.collatz", "40", minion_tgt=salt_mm_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json[0][-1] == 2

    ret = mm_master_2_salt_cli.run("test.collatz", "40", minion_tgt=salt_mm_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json[0][-1] == 2

    ret = mm_master_1_salt_cli.run("test.collatz", "40", minion_tgt=salt_mm_minion_2.id)
    assert ret.exitcode == 0
    assert ret.json[0][-1] == 2

    ret = mm_master_2_salt_cli.run("test.collatz", "40", minion_tgt=salt_mm_minion_2.id)
    assert ret.exitcode == 0
    assert ret.json[0][-1] == 2


def test_get_opts(
    mm_master_1_salt_cli, salt_mm_minion_1, mm_master_2_salt_cli, salt_mm_minion_2
):
    """
    test.conf_text
    """
    ret = mm_master_1_salt_cli.run("test.get_opts", minion_tgt=salt_mm_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json["cachedir"] == salt_mm_minion_1.config["cachedir"]

    ret = mm_master_2_salt_cli.run("test.get_opts", minion_tgt=salt_mm_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json["cachedir"] == salt_mm_minion_1.config["cachedir"]

    ret = mm_master_1_salt_cli.run("test.get_opts", minion_tgt=salt_mm_minion_2.id)
    assert ret.exitcode == 0
    assert ret.json["cachedir"] == salt_mm_minion_2.config["cachedir"]

    ret = mm_master_2_salt_cli.run("test.get_opts", minion_tgt=salt_mm_minion_2.id)
    assert ret.exitcode == 0
    assert ret.json["cachedir"] == salt_mm_minion_2.config["cachedir"]
