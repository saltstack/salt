import logging

log = logging.getLogger(__name__)


def test_exception_exit(salt_run_cli):
    ret = salt_run_cli.run(
        "error.error", "name='Exception'", "message='This is an error.'"
    )
    assert ret.returncode == 1
