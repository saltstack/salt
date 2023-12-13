import pytest

import salt.modules.test as test


def test_raise_exception():
    """
    Add test raising an exception in test module.
    """
    msg = "message"
    with pytest.raises(Exception) as err:
        test.exception(message=msg)
    assert err.match(msg)
