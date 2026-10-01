"""
Capture-and-assert tests that ensure every event tag emitted by Salt Cloud is
documented on the :ref:`cloud-events-reference` page.

The tests scan ``salt/cloud/clouds/`` together with ``salt/cloud/__init__.py``
and ``salt/utils/cloud.py`` for literal ``"salt/cloud/..."`` strings used as
the ``tag=`` argument to ``cloud.fire_event``, normalise each tag into its
``<task>`` (and, where relevant, ``<resource>``) segments, and verify that
the normalised tag is referenced in ``doc/topics/cloud/events.rst``.

If a driver introduces a new event tag the documentation page must be updated
to mention it; otherwise this test fails.
"""

import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
EVENTS_DOC = REPO_ROOT / "doc" / "topics" / "cloud" / "events.rst"

SCAN_PATHS = [
    REPO_ROOT / "salt" / "cloud" / "clouds",
    REPO_ROOT / "salt" / "cloud" / "__init__.py",
    REPO_ROOT / "salt" / "utils" / "cloud.py",
]

TAG_RE = re.compile(r"""['"](salt/cloud/[^'"]+)['"]""")


def _normalise(tag):
    """
    Replace per-VM / per-resource interpolation placeholders with the
    ``<vm_name>`` / ``<node>`` / ``<resource>`` tokens used in the docs.
    """
    parts = tag.split("/")
    # parts[0:2] == ['salt', 'cloud']
    # parts[2]  == resource (vm name or fixed resource type)
    # parts[3:] == task path
    if len(parts) < 4:
        return tag

    resource = parts[2]
    task = "/".join(parts[3:])

    # Strip the ``cache_node_*`` family back to the documented form. The
    # resource segment is the node name there.
    if task.startswith("cache_node_"):
        return f"salt/cloud/<node>/{task}"

    # Fixed resource buckets used by the GCE driver.
    if resource in {
        "disk",
        "snapshot",
        "net",
        "subnet",
        "address",
        "firewall",
        "loadbalancer",
        "healthcheck",
    }:
        return f"salt/cloud/{resource}/{task}"

    # Block-volume / spot-request templated buckets.
    if resource.startswith("spot_request_"):
        return f"salt/cloud/spot_request_<request_id>/{task}"
    if resource.startswith("block_volume_"):
        return f"salt/cloud/block_volume_<volume_id>/{task}"

    # Volume-name tags emitted by the OpenStack driver use ``{volume.name}``.
    if "volume" in resource:
        return f"salt/cloud/<volume_name>/{task}"

    # Any remaining placeholder is a per-VM runtime value.
    if "{" in resource:
        return f"salt/cloud/<vm_name>/{task}"

    return f"salt/cloud/{resource}/{task}"


def _gather_tags():
    tags = set()
    for path in SCAN_PATHS:
        if path.is_dir():
            files = sorted(path.glob("*.py"))
        else:
            files = [path]
        for source in files:
            text = source.read_text(encoding="utf-8")
            for match in TAG_RE.findall(text):
                tags.add(match)
    return tags


def _doc_text():
    return EVENTS_DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def emitted_tags():
    return {_normalise(tag) for tag in _gather_tags()}


@pytest.fixture(scope="module")
def documented_tags_text():
    return _doc_text()


def test_events_reference_page_exists():
    assert EVENTS_DOC.is_file(), (
        "doc/topics/cloud/events.rst is required by Salt Cloud event "
        "documentation tests"
    )


def test_documented_tags_render_under_salt_event_directive(documented_tags_text):
    """
    Every event documented on the reference page must be declared with the
    ``.. salt:event::`` directive so the rendered HTML includes a permalink.
    """
    directive_count = documented_tags_text.count(".. salt:event:: salt/cloud/")
    # The reference page is expected to declare at least the documented
    # lifecycle, power-state, reactor-hook and resource events. The number is
    # intentionally generous so that adding new tags does not require touching
    # this assertion.
    assert directive_count >= 30


@pytest.mark.parametrize(
    "tag",
    [
        "salt/cloud/<vm_name>/creating",
        "salt/cloud/<vm_name>/requesting",
        "salt/cloud/<vm_name>/querying",
        "salt/cloud/<vm_name>/waiting_for_ssh",
        "salt/cloud/<vm_name>/deploying",
        "salt/cloud/<vm_name>/deploy_script",
        "salt/cloud/<vm_name>/deploy_windows",
        "salt/cloud/<vm_name>/created",
        "salt/cloud/<vm_name>/destroying",
        "salt/cloud/<vm_name>/destroyed",
        "salt/cloud/<vm_name>/tagging",
        "salt/cloud/<vm_name>/requesting/failed",
        "salt/cloud/<vm_name>/starting",
        "salt/cloud/<vm_name>/started",
        "salt/cloud/<vm_name>/stopping",
        "salt/cloud/<vm_name>/stopped",
        "salt/cloud/<vm_name>/rebooting",
        "salt/cloud/<vm_name>/rebooted",
        "salt/cloud/<vm_name>/resizing",
        "salt/cloud/<vm_name>/resized",
        "salt/cloud/<vm_name>/query_reactor",
        "salt/cloud/<vm_name>/ssh_ready_reactor",
        "salt/cloud/<node>/cache_node_new",
        "salt/cloud/<node>/cache_node_missing",
        "salt/cloud/<node>/cache_node_diff",
        "salt/cloud/disk/created",
        "salt/cloud/snapshot/created",
        "salt/cloud/net/created",
        "salt/cloud/subnet/created",
        "salt/cloud/address/created",
        "salt/cloud/firewall/created",
        "salt/cloud/loadbalancer/created",
        "salt/cloud/healthcheck/created",
        "salt/cloud/spot_request_<request_id>/tagging",
        "salt/cloud/block_volume_<volume_id>/tagging",
    ],
)
def test_documented_tag_appears_in_reference(tag, documented_tags_text):
    assert tag in documented_tags_text, (
        f"{tag} is in the canonical Salt Cloud event tag list but is missing "
        "from doc/topics/cloud/events.rst"
    )


def test_every_emitted_tag_is_documented(emitted_tags, documented_tags_text):
    """
    The set of tags emitted by the cloud drivers must be a subset of the
    documented set. If a driver introduces a new tag, the reference page must
    be updated to mention it.
    """
    undocumented = sorted(t for t in emitted_tags if t not in documented_tags_text)
    assert (
        not undocumented
    ), "Undocumented salt-cloud event tags emitted from the code: " + ", ".join(
        undocumented
    )
