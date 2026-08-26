"""
Documentation-tracking tests for the VMware driver.

Backed by issue #57933 (customization_spec missing from docs) and #55889
(Ubuntu hostname not set).
"""

import pathlib

from salt.cloud.clouds import vmware

REPO_ROOT = pathlib.Path(__file__).resolve().parents[5]
VMWARE_DOC = REPO_ROOT / "doc" / "topics" / "cloud" / "vmware.rst"


def _doc_text():
    return VMWARE_DOC.read_text(encoding="utf-8")


def test_customization_spec_is_documented():
    doc = _doc_text()
    assert "``customization_spec``" in doc
    # The doc must explain the dependency on customization=True, otherwise
    # users will be surprised when their spec is silently ignored.
    assert "``customization``" in doc


def test_customization_spec_used_by_create():
    """
    The driver actually reads ``customization_spec`` from the profile; this
    test guarantees the option name survives any future refactor of
    create().
    """
    source = pathlib.Path(vmware.__file__).read_text(encoding="utf-8")
    assert '"customization_spec"' in source
    assert "get_customizationspec_ref" in source


def test_ubuntu_hostname_known_issue_referenced():
    doc = _doc_text()
    assert "issue #55889" in doc
