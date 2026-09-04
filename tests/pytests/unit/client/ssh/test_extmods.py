import re

import salt.client.ssh
import salt.fileclient
from tests.support.mock import MagicMock, patch


def test_internal_modules_are_not_synced_as_extmods(master_opts):
    fsclient = salt.fileclient.FSClient(master_opts)
    tar = MagicMock()
    with patch("tarfile.open", return_value=tar):
        salt.client.ssh.mod_data(fsclient)
    ptrn = re.compile(
        r".*/salt/(modules|states|grains|renderers|returners|utils)/\w+\.py$"
    )
    for call in tar.add.call_args_list:
        assert not ptrn.match(call[0][0])
