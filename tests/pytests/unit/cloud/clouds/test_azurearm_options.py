"""
Documentation-tracking tests for the AzureARM driver.

Backed by issues #65063 (inconsistent ssh_interface/bootstrap_interface
documentation) and #58096 (make_master traceback) / #65064 (query error on
Windows with no public IP). These assertions hold the docs page accountable
for the runtime behaviour described in the ``create()`` body.
"""

import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[5]
AZUREARM_DOC = REPO_ROOT / "doc" / "topics" / "cloud" / "azurearm.rst"


def _doc_text():
    return AZUREARM_DOC.read_text(encoding="utf-8")


def test_azurearm_doc_documents_bootstrap_interface():
    doc = _doc_text()
    assert "bootstrap_interface" in doc
    # The two valid values must both appear under the option's section so
    # users do not have to read the source to discover them.
    assert "``public``" in doc and "``private``" in doc


def test_azurearm_doc_calls_out_ssh_interface_is_not_used():
    """
    ``ssh_interface`` is honoured by other drivers; AzureARM uses
    ``bootstrap_interface``. The note about that must be present.
    """
    doc = _doc_text()
    assert (
        "generic ``ssh_interface`` option" in doc
        and "is **not** consulted by ``azurearm``" in doc
    )


def test_azurearm_doc_references_make_master_bug():
    doc = _doc_text()
    assert "issue #58096" in doc


def test_azurearm_doc_references_query_error_bug():
    doc = _doc_text()
    assert "issue #65064" in doc
    assert "list index out of range" in doc
