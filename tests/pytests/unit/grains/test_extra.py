"""
tests.pytests.unit.grains.test_extra
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import pytest

import salt.grains.extra as extra
import salt.utils.platform
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {extra: {}}


def test_static_grains_file_conflicting_keys(tmp_path):
    """
    Test that static grains files with conflicting keys don't result in failure
    to load all grains from that file.
    """
    with (tmp_path / "grains").open("w") as fh:
        fh.write('foo: bar\nfoo: baz\nno_conflict_here: "yay"\n')

    with patch.object(
        salt.utils.platform, "is_proxy", MagicMock(return_value=False)
    ), patch("salt.grains.extra.__opts__", {"conf_file": str(tmp_path / "minion")}):
        static_grains = extra.config()
        assert "no_conflict_here" in static_grains
