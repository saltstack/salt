import logging

import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
]

log = logging.getLogger(__name__)


def test_check_imports(salt_call_cli):
    """
    Test imports
    """
    output = salt_call_cli.run("state.apply", "breaks", "--output-diff", "test=true")
    print(output)
