"""
Functional tests verifying that win_pkg functions respect the ``saltenv``
setting in minion opts when no explicit ``saltenv`` kwarg is supplied.

The module-level ``minion_config_overrides`` fixture sets ``saltenv: prod``
so that all loaders in this module run with ``__opts__["saltenv"] == "prod"``.
The conftest will still layer on the winrepo / file_roots settings on top.
"""

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def minion_config_overrides():
    return {"saltenv": "prod"}


@pytest.fixture(scope="module")
def pkg(modules):
    yield modules.pkg


@pytest.fixture(scope="module")
def pkg_def_contents():
    return r"""
    prod-software:
      '2.0.0':
        full_name: 'Prod Software'
        installer: 'C:\files\prodsoftware.msi'
        install_flags: '/qn /norestart'
        uninstaller: 'C:\files\prodsoftware.msi'
        uninstall_flags: '/qn /norestart'
        msiexec: True
        reboot: False
    """


def test_refresh_db_respects_opts_saltenv(
    pkg, pkg_def_contents, state_tree_prod, minion_opts
):
    """
    When ``saltenv`` is set in minion opts and not passed as a kwarg,
    refresh_db() must read package definitions from the configured saltenv
    rather than always falling back to ``base``.
    """
    assert minion_opts.get("saltenv") == "prod"
    assert len(pkg.get_package_info("prod-software")) == 0

    repo_dir = state_tree_prod / "winrepo_ng"
    with pytest.helpers.temp_file("prod-software.sls", pkg_def_contents, repo_dir):
        # No saltenv kwarg — must derive "prod" from __opts__
        pkg.refresh_db()

    assert len(pkg.get_package_info("prod-software")) == 1
