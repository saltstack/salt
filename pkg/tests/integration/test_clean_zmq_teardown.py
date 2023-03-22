import logging

import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
]

log = logging.getLogger(__name__)


def test_check_no_import_error(salt_call_cli):
    """
    Test that we don't have any errors on teardown of python when using a py-rendered sls file
    """
    output = salt_call_cli.run("state.apply", "breaks", "--output-diff", "test=true")
    log.debug(output.stderr)
    assert not output.stderr
