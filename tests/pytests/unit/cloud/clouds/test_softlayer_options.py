"""
Documentation-tracking tests for the SoftLayer driver.

Backed by issue #56546: the SoftLayer / softlayer_hw drivers are slated for
removal in a future release. The driver source and the user-facing docs must
both carry a ``.. deprecated::`` block so users are not surprised when the
driver is removed.
"""

import pathlib

from salt.cloud.clouds import softlayer, softlayer_hw

REPO_ROOT = pathlib.Path(__file__).resolve().parents[5]
SOFTLAYER_DOC = REPO_ROOT / "doc" / "topics" / "cloud" / "softlayer.rst"


def _doc_text():
    return SOFTLAYER_DOC.read_text(encoding="utf-8")


def test_softlayer_doc_has_deprecation_banner():
    doc = _doc_text()
    assert ".. deprecated:: 3006.0" in doc
    assert "softlayer" in doc and "softlayer_hw" in doc


def test_softlayer_doc_links_to_issue():
    doc = _doc_text()
    assert "issue #56546" in doc


def test_softlayer_module_docstring_marks_deprecated():
    assert ".. deprecated:: 3006.0" in (softlayer.__doc__ or "")


def test_softlayer_hw_module_docstring_marks_deprecated():
    assert ".. deprecated:: 3006.0" in (softlayer_hw.__doc__ or "")
