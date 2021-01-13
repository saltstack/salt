import logging
import types

import pytest
import salt.modules.aliases as aliases
import salt.modules.cmdmod as cmdmod
import salt.modules.config as config

pytestmark = [
    pytest.mark.windows_whitelisted,
]

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules(tmp_path):
    aliases_file = tmp_path / "aliases-file"
    log.debug("Aliases file path: %s", aliases_file)
    opts = {"aliases.file": str(aliases_file), "integration.test": True}
    return {
        aliases: {
            "__opts__": opts,
            "__salt__": {"cmd.run": cmdmod.run, "config.option": config.option},
        },
        cmdmod: {},
        config: {"__opts__": opts},
    }


@pytest.fixture
def alias():
    ret = aliases.set_target(alias="fred", target="bob")
    assert ret is True
    return types.SimpleNamespace(name="fred", target="bob")


def test_set_target(alias):
    """
    aliases.set_target and aliases.get_target
    """
    ret = aliases.get_target(alias.name)
    assert ret == alias.target


def test_has_target(alias):
    """
    aliases.set_target and aliases.has_target
    """
    ret = aliases.has_target(alias.name, alias.target)
    assert ret is True


def test_list_aliases(alias):
    """
    aliases.list_aliases
    """
    ret = aliases.list_aliases()
    assert isinstance(ret, dict)
    assert alias.name in ret


def test_rm_alias(alias):
    """
    aliases.rm_alias
    """
    ret = aliases.rm_alias(alias=alias.name)
    assert ret is True
    ret = aliases.list_aliases()
    assert isinstance(ret, dict)
    assert ret == {}
