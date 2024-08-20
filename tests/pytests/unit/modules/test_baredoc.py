import pytest

import salt.modules.baredoc as baredoc
from tests.support.paths import SALT_CODE_DIR


@pytest.fixture
def configure_loader_modules():
    return {
        baredoc: {
            "__opts__": {"extension_modules": SALT_CODE_DIR},
            "__grains__": {"saltpath": SALT_CODE_DIR},
        }
    }


def test_baredoc_list_states():
    """
    Test baredoc state module listing
    """
    ret = baredoc.list_states(names_only=True)
    assert "run" in ret["cmd"]


def test_baredoc_list_states_args():
    """
    Test baredoc state listing with args
    """
    ret = baredoc.list_states()
    assert "wait" in ret["cmd"][0]
    assert "runas" in ret["cmd"][0]["wait"]


def test_baredoc_list_states_single():
    """
    Test baredoc state listing single state module
    """
    ret = baredoc.list_states("cmd")
    assert "wait" in ret["cmd"][0]
    assert "runas" in ret["cmd"][0]["wait"]


def test_baredoc_list_modules():
    """
    test baredoc executiion module listing
    """
    ret = baredoc.list_modules(names_only=True)
    assert "run" in ret["cmd"]


def test_baredoc_list_modules_args():
    """
    test baredoc execution module listing with args
    """
    ret = baredoc.list_modules()
    assert "get_value" in ret["xml"][0]
    assert "file" in ret["xml"][0]["get_value"]


def test_baredoc_list_modules_single_and_alias():
    """
    test baredoc single module listing
    """
    ret = baredoc.list_modules("cmdmod")
    assert "run_stdout" in ret["cmd"][2]


def test_baredoc_state_docs():
    ret = baredoc.state_docs()
    assert "Execution of arbitrary commands" in ret["cmd"]
    assert "acl.absent" in ret


def test_baredoc_state_docs_single_arg():
    ret = baredoc.state_docs("cmd")
    assert "Execution of arbitrary commands" in ret["cmd"]
    ret = baredoc.state_docs("timezone.system")
    assert "Set the timezone for the system." in ret["timezone.system"]


def test_baredoc_state_docs_multiple_args():
    ret = baredoc.state_docs("timezone.system", "cmd")
    assert "Set the timezone for the system." in ret["timezone.system"]
    assert "Execution of arbitrary commands" in ret["cmd"]


def test_baredoc_module_docs():
    ret = baredoc.module_docs()
    assert "A module for testing" in ret["saltcheck"]


def test_baredoc_module_docs_single_arg():
    ret = baredoc.module_docs("saltcheck")
    assert "A module for testing" in ret["saltcheck"]


def test_baredoc_module_docs_multiple_args():
    ret = baredoc.module_docs("saltcheck", "xml.get_value")
    assert "A module for testing" in ret["saltcheck"]
    assert "Returns the value of the matched xpath element" in ret["xml.get_value"]
