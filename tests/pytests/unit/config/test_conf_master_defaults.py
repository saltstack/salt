"""
Regression test: make sure every opt documented in the
``Master Cluster Settings`` block of ``conf/master`` is still present in
``salt.config.DEFAULT_MASTER_OPTS`` and in the ``VALID_OPTS`` schema, and
that the example value in the template type-matches the schema.

Rationale: operators copy from ``conf/master``.  If an opt is renamed or
removed in the Python schema but the template is not updated, operators
will silently ship a config with an unknown key.  Keep this file in sync
with any additions / renames to the Master Cluster Settings block.
"""

import ast
import pathlib
import re

import pytest

import salt.config

REPO_ROOT = pathlib.Path(salt.config.__file__).resolve().parents[2]
CONF_MASTER = REPO_ROOT / "conf" / "master"

# Section header that starts the Master Cluster Settings block.  The block
# ends at either the next ``#####`` section header or EOF.
_SECTION_HEADER_RE = re.compile(r"^#####\s+(.+?)\s+#####\s*$")
_OPT_LINE_RE = re.compile(r"^#(?P<key>[a-zA-Z_][\w.]*):\s?(?P<value>.*)$")


def _parse_cluster_block():
    """
    Return ``{opt_name: example_value_or_None}`` for every commented-opt
    line inside the ``Master Cluster Settings`` section of conf/master.

    List-valued opts (``cluster_peers``) and opts with no inline value
    map to ``None`` because the example is on the following lines.
    """
    opts = {}
    text = CONF_MASTER.read_text().splitlines()
    inside = False
    for line in text:
        header = _SECTION_HEADER_RE.match(line)
        if header:
            inside = "Master Cluster Settings" in header.group(1)
            continue
        if not inside:
            continue
        m = _OPT_LINE_RE.match(line)
        if not m:
            continue
        key = m.group("key")
        raw = m.group("value").strip()
        if not raw:
            opts[key] = None
            continue
        # Try to parse as a Python literal; fall back to the raw string.
        try:
            opts[key] = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            opts[key] = raw
    return opts


def test_conf_master_cluster_block_opts_are_in_schema():
    """
    Every opt in the "Master Cluster Settings" block must be a real key
    in ``DEFAULT_MASTER_OPTS`` and in the master ``VALID_OPTS`` schema.
    """
    documented = _parse_cluster_block()
    assert documented, "Master Cluster Settings block not found in conf/master"

    defaults = salt.config.DEFAULT_MASTER_OPTS
    valid = salt.config.VALID_OPTS

    missing_from_defaults = sorted(k for k in documented if k not in defaults)
    missing_from_valid = sorted(k for k in documented if k not in valid)
    assert not missing_from_defaults, (
        f"conf/master documents opts not in DEFAULT_MASTER_OPTS: "
        f"{missing_from_defaults}"
    )
    assert not missing_from_valid, (
        f"conf/master documents opts not in VALID_OPTS schema: " f"{missing_from_valid}"
    )


@pytest.mark.parametrize(
    "key",
    sorted(_parse_cluster_block().keys()),
)
def test_conf_master_example_value_type_matches_schema(key):
    """
    Where conf/master shows an inline example value, that value must
    be an instance of one of the types declared in VALID_OPTS for the
    same key (or be the string ``"None"`` placeholder).
    """
    documented = _parse_cluster_block()
    example = documented[key]
    if example is None:
        # List-valued opts carry their example on subsequent lines; not
        # worth re-parsing here.  The presence check in the other test
        # already covers them.
        pytest.skip(f"{key} has no inline example value")
    schema_type = salt.config.VALID_OPTS[key]
    if not isinstance(schema_type, tuple):
        schema_type = (schema_type,)
    # ``None`` sentinels show up both as the Python ``None`` literal
    # and (less commonly) as the bare string "None" in templates.  The
    # schema uses ``type(None)`` for optional fields; normalize.
    if example is None or example == "None":
        assert (
            type(None) in schema_type
        ), f"conf/master documents {key} as None but schema is {schema_type}"
        return
    # Bools must match bool exactly — ``bool`` is a subclass of ``int``.
    if bool in schema_type and isinstance(example, bool):
        return
    allowed = tuple(t for t in schema_type if t is not type(None))
    assert isinstance(example, allowed), (
        f"conf/master example for {key} is {example!r} ({type(example).__name__}), "
        f"but VALID_OPTS declares {schema_type}"
    )


def test_cluster_id_default_is_none():
    """conf/master shows ``cluster_id: master_cluster`` as an example only."""
    assert salt.config.DEFAULT_MASTER_OPTS["cluster_id"] is None


def test_cluster_pool_port_default_matches_template():
    assert salt.config.DEFAULT_MASTER_OPTS["cluster_pool_port"] == 4520


def test_cluster_pki_dir_falls_back_to_pki_dir():
    """
    When ``cluster_id`` is set but ``cluster_pki_dir`` is not, the
    master-config post-processing must copy ``pki_dir`` into
    ``cluster_pki_dir``.  conf/master promises this behaviour.
    """
    defaults = salt.config.DEFAULT_MASTER_OPTS.copy()
    overrides = {"cluster_id": "cfg-fallback-test"}
    opts = salt.config.apply_master_config(overrides, defaults)
    assert opts["cluster_pki_dir"] == opts["pki_dir"]
