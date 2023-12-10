import logging
import os

import pytest

import salt.states.file as filestate
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


pytestmark = pytest.mark.skipif(
    pytest.mark.skip_unless_on_linux, reason="Only run on Linux"
)


@pytest.fixture
def configure_loader_modules():
    return {
        filestate: {
            "__env__": "base",
            "__salt__": {"file.manage_file": False},
            "__opts__": {"test": False, "cachedir": ""},
            "__instance_id__": "",
            "__low__": {},
            "__utils__": {},
        }
    }


def test_selinux_change():
    file_name = "/tmp/some-test-file"
    check_perms_result = [
        {
            "comment": "The file {} is set to be changed".format(file_name),
            "changes": {
                "selinux": {
                    "New": "User: unconfined_u Type: lost_found_t",
                    "Old": "User: system_u Type: user_tmp_t",
                }
            },
            "name": file_name,
            "result": True,
        },
        {"luser": "root", "lmode": "0644", "lgroup": "root"},
    ]

    with patch.object(os.path, "exists", MagicMock(return_value=True)):
        with patch.dict(
            filestate.__salt__,
            {
                "file.source_list": MagicMock(return_value=[file_name, None]),
                "file.check_perms": MagicMock(return_value=check_perms_result),
            },
        ):
            ret = filestate.managed(
                file_name,
                selinux={"seuser": "unconfined_u", "setype": "user_tmp_t"},
            )
            assert ret["result"]
