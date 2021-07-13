import logging
import shutil
import types

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def minion_config_overrides(tmp_path_factory):
    temp_path = tmp_path_factory.mktemp("aliases-temp")
    aliases_file = temp_path / "aliases-file"
    try:
        yield {
            "aliases.file": str(aliases_file),
            "integration.test": True,
        }
    finally:
        shutil.rmtree(str(temp_path), ignore_errors=True)


@pytest.fixture(scope="module")
def aliases(modules):
    return modules.aliases


@pytest.fixture
def alias(aliases):
    ret = aliases.set_target(alias="fred", target="bob")
    assert ret is True
    return types.SimpleNamespace(name="fred", target="bob")


def test_set_target(aliases, alias):
    """
    aliases.set_target and aliases.get_target
    """
    ret = aliases.get_target(alias.name)
    assert ret == alias.target


def test_has_target(aliases, alias):
    """
    aliases.set_target and aliases.has_target
    """
    ret = aliases.has_target(alias.name, alias.target)
    assert ret is True


def test_list_aliases(aliases, alias):
    """
    aliases.list_aliases
    """
    ret = aliases.list_aliases()
    assert isinstance(ret, dict)
    assert alias.name in ret


def test_rm_alias(aliases, alias):
    """
    aliases.rm_alias
    """
    ret = aliases.rm_alias(alias=alias.name)
    assert ret is True
    ret = aliases.list_aliases()
    assert isinstance(ret, dict)
    assert ret == {}
