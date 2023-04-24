"""
    :codeauthor: :email:`Simon Dodsley <simon@purestorage.com>`
"""

import errno
import textwrap

import salt.grains.nvme as nvme
from tests.support.mock import mock_open, patch


def test_linux_nvme_nqn_grains():
    _nvme_file = textwrap.dedent(
        """\
        nqn.2014-08.org.nvmexpress:fc_lif:uuid:2cd61a74-17f9-4c22-b350-3020020c458d
        """
    )

    with patch("salt.utils.files.fopen", mock_open(read_data=_nvme_file)):
        nqn = nvme._linux_nqn()

    assert isinstance(nqn, list)
    assert len(nqn) == 1
    assert nqn == [
        "nqn.2014-08.org.nvmexpress:fc_lif:uuid:2cd61a74-17f9-4c22-b350-3020020c458d"
    ]


def test_linux_nqn_non_root():
    """
    Test if linux_nqn is running on salt-master as non-root
    and handling access denial properly.
    :return:
    """
    with patch(
        "salt.utils.files.fopen",
        side_effect=IOError(errno.EPERM, "The cables are not the same length."),
    ):
        with patch("salt.grains.nvme.log"):
            assert nvme._linux_nqn() == []
            nvme.log.debug.assert_called()
            assert "Error while accessing" in nvme.log.debug.call_args[0][0]
            assert "cables are not the same" in nvme.log.debug.call_args[0][2].strerror
            assert nvme.log.debug.call_args[0][2].errno == errno.EPERM
            assert nvme.log.debug.call_args[0][1] == "/etc/nvme/hostnqn"


def test_linux_nqn_no_nvme_initiator():
    """
    Test if linux_nqn is running on salt-master as root.
    nvme initiator is not there accessible or is not supported.
    :return:
    """
    with patch("salt.utils.files.fopen", side_effect=IOError(errno.ENOENT, "")):
        with patch("salt.grains.nvme.log"):
            assert nvme._linux_nqn() == []
            nvme.log.debug.assert_not_called()
