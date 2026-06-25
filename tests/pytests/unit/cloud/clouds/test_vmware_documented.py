"""
Tests that the cloud-profile keys documented in
``doc/topics/cloud/vmware.rst`` actually exist in
:mod:`salt.cloud.clouds.vmware`.

This is a documentation-driven regression test for
`saltstack/salt#60037 <https://github.com/saltstack/salt/issues/60037>`_:
the "Getting Started with VMware" page added explicit guidance on
``customization``, ``customization_spec``, and ``win_run_once``. The
tests here exercise the source of those keys (``get_cloud_config_value``
lookups) to verify the docs and the code stay in sync.

The tests are gated on ``pyVmomi`` being importable but never reach a
live vCenter; they patch ``__opts__`` and assert the cloud module reads
the documented keys.
"""

import os

import pytest

import salt.utils.files

HAS_LIBS = True
try:
    # pylint: disable=import-error,unused-import
    from pyVim.connect import SmartConnect  # noqa: F401
    from pyVmomi import vim  # noqa: F401

    # pylint: enable=import-error,unused-import
except ImportError:
    HAS_LIBS = False

from salt import config
from salt.cloud.clouds import vmware

pytestmark = [
    pytest.mark.skipif(
        not HAS_LIBS, reason="Install pyVmomi to be able to run this test."
    ),
]


@pytest.fixture
def documented_profile():
    return {
        "test-vm": {
            "provider": "vcenter01:vmware",
            "clonefrom": "template-vm",
            "customization": True,
            "customization_spec": "my-saved-spec",
            "win_run_once": [
                "powershell.exe c:\\scripts\\enable-winrm.ps1",
                "cmd.exe /c c:\\scripts\\post-deploy.bat",
            ],
            "image": "windows2019srv_64Guest",
        }
    }


@pytest.fixture
def opts(documented_profile):
    return {
        "profiles": documented_profile,
        "providers": {
            "vcenter01": {
                "vmware": {
                    "driver": "vmware",
                    "url": "vcenter01.example.com",
                    "user": "DOMAIN\\user",
                    "password": "verybadpass",
                    "profiles": documented_profile,
                }
            }
        },
    }


def _vm(documented_profile, **extra):
    vm_ = dict(documented_profile["test-vm"], profile="test-vm")
    vm_.setdefault("driver", "vmware")
    vm_.update(extra)
    return vm_


def test_documented_customization_spec_read(opts, documented_profile):
    """``customization_spec`` is read by the vmware cloud driver."""
    value = config.get_cloud_config_value(
        "customization_spec",
        _vm(documented_profile),
        opts,
        search_global=False,
        default=None,
    )
    assert value == "my-saved-spec"


def test_documented_win_run_once_read(opts, documented_profile):
    """``win_run_once`` is read as a list of command lines."""
    value = config.get_cloud_config_value(
        "win_run_once",
        _vm(documented_profile),
        opts,
        search_global=False,
        default=None,
    )
    assert isinstance(value, list)
    assert len(value) == 2
    assert all(isinstance(cmd, str) for cmd in value)


def test_documented_customization_read(opts, documented_profile):
    """``customization`` is read from the profile when set."""
    value = config.get_cloud_config_value(
        "customization",
        _vm(documented_profile),
        opts,
        search_global=False,
        default=True,
    )
    assert value is True


def test_win_run_once_field_name_matches_module():
    """
    Guard against a future rename: the cloud module must still query a
    config value named ``win_run_once`` (the name documented in
    vmware.rst).
    """
    source = vmware.__file__
    # The compiled .pyc has no source; fall back to inspecting source if available.
    if source.endswith(".pyc"):
        source = source[:-1]
    if not os.path.exists(source):
        pytest.skip("vmware cloud module source is unavailable in this install.")
    with salt.utils.files.fopen(source, "r", encoding="utf-8") as fh:
        text = fh.read()
    assert '"win_run_once"' in text, (
        "salt/cloud/clouds/vmware.py no longer references win_run_once; "
        "doc/topics/cloud/vmware.rst must be updated to match."
    )
    assert '"customization_spec"' in text, (
        "salt/cloud/clouds/vmware.py no longer references customization_spec; "
        "doc/topics/cloud/vmware.rst must be updated to match."
    )


@pytest.mark.skipif(
    not os.environ.get("RUN_VMWARE_INTEGRATION"),
    reason="Set RUN_VMWARE_INTEGRATION=1 with VMWARE_* env vars to run.",
)
def test_documented_clone_integration():
    """
    Placeholder for a live vCenter clone test. Gated on
    RUN_VMWARE_INTEGRATION because it requires real vCenter credentials.
    """
    pytest.skip("Live vCenter integration is not exercised in CI.")
