import pytest

import salt.runners.saltutil as saltutil
from tests.support.mock import MagicMock, patch


def get_module_types():
    module_types = [
        "clouds",
        "modules",
        "states",
        "grains",
        "renderers",
        "returners",
        "output",
        "proxy",
        "runners",
        "wheel",
        "engines",
        "thorium",
        "queues",
        "pillar",
        "utils",
        "sdb",
        "cache",
        "fileserver",
        "tops",
        "tokens",
        "serializers",
        "executors",
        "roster",
    ]
    return module_types


@pytest.fixture(params=get_module_types())
def module_type(request):
    yield request.param


@pytest.fixture
def module_sync_functions():
    yield {
        "clouds": "clouds",
        "modules": "modules",
        "states": "states",
        "grains": "grains",
        "renderers": "renderers",
        "returners": "returners",
        "output": "output",
        "proxy": "proxymodules",
        "runners": "runners",
        "wheel": "wheel",
        "engines": "engines",
        "thorium": "thorium",
        "queues": "queues",
        "pillar": "pillar",
        "utils": "utils",
        "sdb": "sdb",
        "cache": "cache",
        "fileserver": "fileserver",
        "tops": "tops",
        "tokens": "eauth_tokens",
        "serializers": "serializers",
        "executors": "executors",
        "roster": "roster",
    }


@pytest.fixture
def configure_loader_modules(master_opts):
    return {saltutil: {"opts": master_opts}}


def test_sync_all():
    """
    Test saltutil.sync_all
    """
    sync_out = MagicMock(return_value=[[], True])
    module_types = [
        "clouds",
        "modules",
        "states",
        "grains",
        "renderers",
        "returners",
        "output",
        "proxymodules",
        "runners",
        "wheel",
        "engines",
        "thorium",
        "queues",
        "pillar",
        "utils",
        "sdb",
        "cache",
        "fileserver",
        "tops",
        "tokens",
        "serializers",
        "executors",
        "roster",
    ]
    with patch("salt.utils.extmods.sync", sync_out):
        ret = saltutil.sync_all()
        for key in module_types:
            assert key in ret


def test_sync(module_type, module_sync_functions):
    """
    Test saltutil.sync functions
    """
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_modules()
        func = f"sync_{module_sync_functions[module_type]}"
        ret = getattr(saltutil, func)()
        assert ret == []

        extmods_sync.assert_called_with(
            {},
            f"{module_type}",
            extmod_blacklist=None,
            extmod_whitelist=None,
            saltenv="base",
        )
