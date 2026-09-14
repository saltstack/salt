"""
Verify that every master config example in
``doc/topics/tutorials/master-cluster-reference.rst`` is valid YAML and
loads through :func:`salt.config.master_config` without raising.

The reference page is the documented contract for the 2-node and 3-node
production topologies; if any of its example configs stops loading,
the page is wrong and somebody following it will hit the same error.
"""

import logging
import pathlib
import re

import pytest
import yaml

import salt.config

log = logging.getLogger(__name__)

DOC_PATH = (
    pathlib.Path(__file__).resolve().parents[3]
    / "doc"
    / "topics"
    / "tutorials"
    / "master-cluster-reference.rst"
)

REQUIRED_CLUSTER_KEYS = {
    "id",
    "cluster_id",
    "cluster_peers",
    "cluster_pki_dir",
    "cluster_secret",
    "cluster_isolated_filesystem",
    "file_roots",
    "pillar_roots",
}


def _extract_yaml_blocks(rst_text):
    """
    Return every ``.. code-block:: yaml`` block in ``rst_text`` as a list
    of raw YAML strings.  Blocks are recognised by the directive line
    followed by a blank line and then 4-space-indented body.
    """
    blocks = []
    pattern = re.compile(
        r"^\.\. code-block:: yaml\s*\n\s*\n((?:(?: {4,}|\t).*\n|\s*\n)+)",
        re.MULTILINE,
    )
    for match in pattern.finditer(rst_text):
        raw = match.group(1)
        # Strip the leading 4-space indent from every non-empty line.
        lines = []
        for line in raw.splitlines():
            if line.startswith("    "):
                lines.append(line[4:])
            elif line.strip() == "":
                lines.append("")
            else:
                lines.append(line)
        blocks.append("\n".join(lines).rstrip() + "\n")
    return blocks


def _cluster_master_blocks():
    """
    Return only the YAML blocks that look like complete master configs
    (i.e. have an ``id:`` and a ``cluster_id:``).  The reference page
    also contains a minion-config block that we deliberately skip
    here -- it's exercised separately below.
    """
    text = DOC_PATH.read_text()
    blocks = _extract_yaml_blocks(text)
    masters = []
    for block in blocks:
        if "cluster_id:" in block and re.search(r"^id:\s", block, re.MULTILINE):
            masters.append(block)
    return masters


def test_reference_page_exists():
    assert DOC_PATH.is_file(), f"Reference page missing: {DOC_PATH}"


def test_yaml_blocks_extracted():
    blocks = _cluster_master_blocks()
    # 2-node topology: 2 masters; 3-node topology: 3 masters.
    assert len(blocks) >= 5, (
        f"Expected at least 5 master-config blocks in "
        f"{DOC_PATH.name}, found {len(blocks)}"
    )


@pytest.mark.parametrize("block_idx", range(5))
def test_documented_master_config_loads(tmp_path, block_idx):
    """
    Each documented master config must parse as YAML AND load through
    salt.config.master_config without raising.
    """
    blocks = _cluster_master_blocks()
    if block_idx >= len(blocks):
        pytest.skip(f"Only {len(blocks)} cluster master blocks found")
    block = blocks[block_idx]

    # Round-trip through PyYAML so we catch syntax errors before
    # touching salt.config.
    parsed = yaml.safe_load(block)
    assert isinstance(
        parsed, dict
    ), f"Block {block_idx} did not parse to a dict: {parsed!r}"

    missing = REQUIRED_CLUSTER_KEYS - set(parsed.keys())
    assert not missing, f"Block {block_idx} is missing required cluster keys: {missing}"

    # cluster_peers must NOT include the host's own id (subtle config
    # bug we don't want creeping into the docs).
    own_id = parsed["id"]
    peers = parsed["cluster_peers"]
    assert (
        own_id not in peers
    ), f"Block {block_idx} ({own_id}) lists itself in cluster_peers"

    # Write it out and load it through the real master config loader.
    cfg_path = tmp_path / "master"
    cfg_path.write_text(block)
    opts = salt.config.master_config(str(cfg_path))

    # Spot-check the cluster-specific knobs survived the load.
    assert opts["cluster_id"] == parsed["cluster_id"]
    assert opts["cluster_isolated_filesystem"] is True
    assert opts["cluster_secret"] == parsed["cluster_secret"]
    assert opts["cluster_peers"] == parsed["cluster_peers"]


def test_documented_minion_config_loads(tmp_path):
    """
    The reference page also ships a minion config (master = LB VIP).
    Make sure that loads cleanly too.
    """
    text = DOC_PATH.read_text()
    blocks = _extract_yaml_blocks(text)
    minion_blocks = [
        b
        for b in blocks
        if re.search(r"^master:\s", b, re.MULTILINE) and "cluster_id:" not in b
    ]
    assert minion_blocks, "No minion config block found in reference page"

    cfg_path = tmp_path / "minion"
    cfg_path.write_text(minion_blocks[0])
    opts = salt.config.minion_config(str(cfg_path))
    assert opts["master"], "minion config did not parse a master value"
    assert (
        opts.get("master_alive_interval", 0) > 0
    ), "reference page should set master_alive_interval > 0"


def test_two_node_and_three_node_topologies_present():
    """
    The reference page must document BOTH the 2-node and the 3-node
    topology.  We detect them by counting unique cluster_peers list
    lengths across the master blocks.
    """
    blocks = _cluster_master_blocks()
    peer_counts = set()
    for block in blocks:
        parsed = yaml.safe_load(block)
        peer_counts.add(len(parsed["cluster_peers"]))
    # 2-node topology -> each master has 1 peer
    # 3-node topology -> each master has 2 peers
    assert 1 in peer_counts, "No 2-node topology (1 peer) example found"
    assert 2 in peer_counts, "No 3-node topology (2 peers) example found"
