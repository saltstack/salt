import logging
import textwrap

import pytest

import salt.grains.mdadm as mdadm
from tests.support.mock import mock_open, patch

log = logging.getLogger(__name__)


@pytest.fixture
def proc_mdstat_no_devices():
    return textwrap.dedent(
        """
        Personalities : [raid0] [raid1] [raid6] [raid5] [raid4] [raid10]
        unused devices: <none>
    """
    )


@pytest.fixture
def proc_mdstat_md_device():
    return textwrap.dedent(
        """
        Personalities : [raid0] [raid1] [raid6] [raid5] [raid4] [raid10]
        md0 : active raid1 loop2[1] loop1[0]
              101376 blocks super 1.2 [2/2] [UU]

        unused devices: <none>
    """
    )


def test_mdadm_grain_no_devices(proc_mdstat_no_devices):
    """
    Test mdadm grain with no md devices present
    """
    mock = mock_open(read_data=proc_mdstat_no_devices)
    with patch("salt.utils.files.fopen", mock):

        assert mdadm.mdadm() == {"mdadm": []}


def test_mdadm_grain_md_device(proc_mdstat_md_device):
    """
    Test mdadm grain with md0 device present
    """
    mock = mock_open(read_data=proc_mdstat_md_device)
    with patch("salt.utils.files.fopen", mock):

        assert mdadm.mdadm() == {"mdadm": ["md0"]}


def test_mdadm_grain_no_proc_mdstat():
    """
    Test mdadm grain when /proc/mdstat is not present
    """
    with patch("salt.utils.files.fopen", side_effect=FileNotFoundError()):

        assert mdadm.mdadm() == {}
