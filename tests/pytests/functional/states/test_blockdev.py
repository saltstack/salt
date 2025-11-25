import logging

import pytest

log = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def non_blockdev_file():
    with pytest.helpers.temp_file() as tmp_file:
        assert tmp_file.is_file()
        yield tmp_file


def test_tuned_not_block_device(states, non_blockdev_file):
    """
    Test to ensure that when the target is not a block device,
    the state returns False and a comment indicating the issue.
    """
    name = str(non_blockdev_file)

    ret = states.blockdev.tuned(
        name=name,
    )
    assert ret["result"] is False
    assert ret["comment"] == f"Changes to {name} cannot be applied. Not a block device."
