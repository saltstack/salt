"""
Regression bar: every ```yaml fenced config block in the master-topology
docs must load through ``salt.config.master_config`` and
``salt.config.topology.load_topology_config`` without raising.

Docs that drift from the loader get caught here.  If a doc example
starts failing, either the loader regressed or the example needs
updating --- do not relax this test to paper over either case.

Scope
-----

* ``doc/topics/master-topology/index.md``
* ``doc/topics/master-topology/overview.md``

Only ``yaml`` fenced blocks are checked.  Shell-command transcripts
(unfenced or plain ``` blocks), ASCII diagrams, and log excerpts are
not master-config fragments and are skipped.
"""

import pathlib
import re

import pytest
import yaml

import salt.config
from salt.config.topology import (
    DEFAULT_EVENT_SUBSCRIPTIONS,
    PeerRef,
    TopologyConfig,
    load_topology_config,
)

# Repo-root relative path to the docs tree.  Walk up from this test file
# until we see ``doc/topics/master-topology`` --- works regardless of
# where pytest is invoked.
_HERE = pathlib.Path(__file__).resolve()


def _find_docs_dir():
    for parent in _HERE.parents:
        candidate = parent / "doc" / "topics" / "master-topology"
        if candidate.is_dir():
            return candidate
    raise RuntimeError("Could not locate doc/topics/master-topology from " f"{_HERE}")


DOCS_DIR = _find_docs_dir()

# Fenced-block pattern: opening ```lang on its own line, then content,
# then closing ``` on its own line.  ``lang`` captured so we can filter
# to ``yaml`` only.
_FENCE_RE = re.compile(
    r"^```(?P<lang>[a-zA-Z0-9_+-]+)\n(?P<body>.*?)^```",
    re.MULTILINE | re.DOTALL,
)


def _extract_yaml_blocks(md_path):
    """Yield (line_number, yaml_text) for every ```yaml block in a file."""
    text = md_path.read_text()
    for match in _FENCE_RE.finditer(text):
        if match.group("lang") != "yaml":
            continue
        # Convert byte offset of the opening fence to a 1-based line.
        line = text.count("\n", 0, match.start()) + 1
        yield line, match.group("body")


def _yaml_blocks_from_docs():
    """Collect every ```yaml block across the two doc files."""
    blocks = []
    for name in ("index.md", "overview.md"):
        path = DOCS_DIR / name
        for lineno, body in _extract_yaml_blocks(path):
            blocks.append((path.name, lineno, body))
    return blocks


YAML_BLOCKS = _yaml_blocks_from_docs()


def test_docs_contain_yaml_examples():
    """Sanity: at least one yaml block exists in each doc file.

    Guards against a regex regression silently making the test vacuous.
    """
    files_with_blocks = {name for name, _, _ in YAML_BLOCKS}
    assert "index.md" in files_with_blocks, (
        "index.md lost its ```yaml config example --- either the doc "
        "regressed or _FENCE_RE needs updating."
    )
    assert "overview.md" in files_with_blocks, (
        "overview.md lost its ```yaml config example --- either the doc "
        "regressed or _FENCE_RE needs updating."
    )


@pytest.mark.parametrize(
    "docfile,lineno,body",
    YAML_BLOCKS,
    ids=[f"{name}:{line}" for name, line, _ in YAML_BLOCKS],
)
def test_doc_yaml_block_parses(docfile, lineno, body):
    """Each ```yaml block in the topology docs parses as a YAML mapping."""
    parsed = yaml.safe_load(body)
    assert isinstance(parsed, dict), (
        f"{docfile}:{lineno} ```yaml block did not parse to a mapping "
        f"(got {type(parsed).__name__}). Doc examples must be valid "
        "master-config fragments."
    )


@pytest.mark.parametrize(
    "docfile,lineno,body",
    YAML_BLOCKS,
    ids=[f"{name}:{line}" for name, line, _ in YAML_BLOCKS],
)
def test_doc_yaml_block_loads_via_master_config(docfile, lineno, body, tmp_path):
    """
    Each ```yaml block round-trips through ``salt.config.master_config``.

    This is the strongest "docs match the loader" bar: write the block
    to a temp file, run it through the full master config loader, and
    verify the opts land with the types the docs promise.
    """
    cfg_path = tmp_path / f"master-{docfile.replace('.md','')}-{lineno}.conf"
    cfg_path.write_text(body)
    opts = salt.config.master_config(str(cfg_path))

    # Minimum contract: if the doc block set topology_enabled or
    # cluster_id, the opts must reflect those values after load.
    doc_parsed = yaml.safe_load(body)
    for key, expected in doc_parsed.items():
        if key not in opts:
            # Unknown keys (interface etc.) pass through untouched --- not
            # our concern here.  Only assert on topology / cluster keys.
            if not key.startswith("topology_") and key != "cluster_id":
                continue
            pytest.fail(
                f"{docfile}:{lineno} example sets {key!r} but "
                "master_config() dropped it"
            )
        if key.startswith("topology_") or key == "cluster_id":
            assert opts[key] == expected, (
                f"{docfile}:{lineno} {key} mis-coerced by master_config: "
                f"doc said {expected!r}, loader produced {opts[key]!r}"
            )


@pytest.mark.parametrize(
    "docfile,lineno,body",
    YAML_BLOCKS,
    ids=[f"{name}:{line}" for name, line, _ in YAML_BLOCKS],
)
def test_doc_yaml_block_loads_via_topology_loader(docfile, lineno, body, tmp_path):
    """
    Every ```yaml block in the topology docs must pass
    ``load_topology_config`` without raising.

    This catches two classes of drift:

    * A doc example that used a deprecated opt name or an opt that
      silently no longer exists.
    * A doc example whose ``topology_peers`` entry shape no longer
      matches ``PeerRef`` (missing required key, wrong type).
    """
    cfg_path = tmp_path / f"master-{docfile.replace('.md','')}-{lineno}.conf"
    cfg_path.write_text(body)
    opts = salt.config.master_config(str(cfg_path))

    cfg = load_topology_config(opts)
    assert isinstance(
        cfg, TopologyConfig
    ), f"{docfile}:{lineno} load_topology_config returned non-TopologyConfig"

    # If the doc flipped topology_enabled, the loader must agree.
    if opts.get("topology_enabled"):
        assert cfg.enabled, (
            f"{docfile}:{lineno} set topology_enabled: True but loader "
            "produced an inert config"
        )
        # Every peer must land as a PeerRef with a non-empty host.
        for idx, peer in enumerate(cfg.peers):
            assert isinstance(peer, PeerRef), (
                f"{docfile}:{lineno} peers[{idx}] is {type(peer).__name__}, "
                "not PeerRef"
            )
            assert peer.host, (
                f"{docfile}:{lineno} peers[{idx}] has empty host --- doc "
                "example and PeerRef shape are out of sync"
            )


def test_index_md_minimal_example_has_expected_shape():
    """
    Pin the index.md 'minimal topology-enabled master config' example.

    The prose around it (lines 126-155 as of writing) promises a
    specific shape:

    * ``cluster_id: east``
    * ``topology_link_port: 4521``
    * two ``topology_peers`` entries, each a ``{host, port}`` mapping

    If the example drifts away from this shape, the surrounding prose
    stops matching the code block --- which is exactly the kind of
    silent doc rot this suite is here to catch.
    """
    index_blocks = [b for name, _, b in YAML_BLOCKS if name == "index.md"]
    assert index_blocks, "index.md lost its yaml example"
    body = index_blocks[0]
    parsed = yaml.safe_load(body)
    assert parsed.get("topology_enabled") is True
    assert parsed.get("cluster_id") == "east"
    assert parsed.get("topology_link_port") == 4521
    peers = parsed.get("topology_peers")
    assert isinstance(peers, list) and len(peers) >= 1
    for entry in peers:
        assert isinstance(entry, dict)
        assert "host" in entry, (
            "index.md topology_peers entry is missing the 'host' key --- "
            "PeerRef requires 'host' and the doc example must show it."
        )


def test_overview_md_minimal_example_has_expected_shape():
    """Pin the overview.md east master example shape."""
    overview_blocks = [b for name, _, b in YAML_BLOCKS if name == "overview.md"]
    assert overview_blocks, "overview.md lost its yaml example"
    body = overview_blocks[0]
    parsed = yaml.safe_load(body)
    assert parsed.get("topology_enabled") is True
    assert parsed.get("cluster_id") == "east"
    assert parsed.get("topology_link_port") == 4521
    peers = parsed.get("topology_peers")
    assert isinstance(peers, list) and peers, "overview.md example lost its peer"
    first = peers[0]
    assert isinstance(first, dict)
    assert first.get("host") == "west"
    assert first.get("port") == 4521


def test_default_event_subscriptions_match_loader():
    """
    The index.md comment above the commented-out
    ``topology_event_subscriptions`` block names the exact defaults
    (``salt/job/*/ret/*`` and ``salt/job/*/new``).  If
    ``DEFAULT_EVENT_SUBSCRIPTIONS`` ever changes, that doc prose
    becomes a lie.  Anchor it here.
    """
    assert DEFAULT_EVENT_SUBSCRIPTIONS == (
        "salt/job/*/ret/*",
        "salt/job/*/new",
    ), (
        "DEFAULT_EVENT_SUBSCRIPTIONS drifted from the values listed in "
        "doc/topics/master-topology/index.md (search for "
        "'topology_event_subscriptions')"
    )
