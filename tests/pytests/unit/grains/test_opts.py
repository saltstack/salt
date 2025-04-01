"""
tests.pytests.unit.grains.test_opts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import salt.grains.opts as opts
from tests.support.mock import patch


def test_grain_opts_does_not_overwrite_core_grains(tmp_path):
    """
    Tests that enabling grain_opts doesn't overwrite the core grains

    See: https://github.com/saltstack/salt/issues/66784
    """
    dunder_opts = {"grain_opts": True}

    with patch.object(opts, "__opts__", dunder_opts, create=True):
        with patch.object(opts, "__pillar__", {}, create=True):
            assert opts.opts() == {"opts": dunder_opts}
