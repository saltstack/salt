# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Simon Dodsley <simon@purestorage.com>`
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import errno
import textwrap

# Import Salt Libs
import salt.grains.nvme as nvme
from tests.support.mock import MagicMock, mock_open, patch

# Import Salt Testing Libs
from tests.support.unit import TestCase


class NvmeGrainsTestCase(TestCase):
    """
    Test cases for nvme grains
    """

    def test_linux_nvme_nqn_grains(self):
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

    @patch(
        "salt.utils.files.fopen",
        MagicMock(
            side_effect=IOError(errno.EPERM, "The cables are not the same length.")
        ),
    )
    @patch("salt.grains.nvme.log", MagicMock())
    def test_linux_nqn_non_root(self):
        """
        Test if linux_nqn is running on salt-master as non-root
        and handling access denial properly.
        :return:
        """
        assert nvme._linux_nqn() == []
        nvme.log.debug.assert_called()
        assert "Error while accessing" in nvme.log.debug.call_args[0][0]
        assert "cables are not the same" in nvme.log.debug.call_args[0][2].strerror
        assert nvme.log.debug.call_args[0][2].errno == errno.EPERM
        assert nvme.log.debug.call_args[0][1] == "/etc/nvme/hostnqn"

    @patch("salt.utils.files.fopen", MagicMock(side_effect=IOError(errno.ENOENT, "")))
    @patch("salt.grains.nvme.log", MagicMock())
    def test_linux_nqn_no_nvme_initiator(self):
        """
        Test if linux_nqn is running on salt-master as root.
        nvme initiator is not there accessible or is not supported.
        :return:
        """
        assert nvme._linux_nqn() == []
        nvme.log.debug.assert_not_called()
