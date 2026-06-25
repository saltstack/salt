"""
Unit tests for ``tools/check_new_config_opts.py`` — the pre-commit
helper that gates adding a new opt without docs (#59908).
"""

import importlib.util
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
TOOL_PATH = REPO_ROOT / "tools" / "check_new_config_opts.py"


def _load_tool():
    """
    The check tool sits at ``tools/check_new_config_opts.py`` and is
    not packaged as a module. Load it via importlib so the unit
    tests are self-contained.
    """
    spec = importlib.util.spec_from_file_location("check_new_config_opts", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("check_new_config_opts", module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tool():
    return _load_tool()


@pytest.fixture
def fake_config_source():
    """
    Synthetic salt/config/__init__.py — just enough so the tool's
    AST scanner can find the three opts dicts.
    """
    return (
        "DEFAULT_MASTER_OPTS = {\n"
        "    'existing_documented_opt': '',\n"
        "    'a_brand_new_opt': '',\n"
        "    'opt_with_marker': '',  # noqa: undocumented\n"
        "}\n"
        "DEFAULT_MINION_OPTS = {\n"
        "    'existing_documented_opt': '',\n"
        "}\n"
        "DEFAULT_PROXY_MINION_OPTS = {\n"
        "    'existing_documented_opt': '',\n"
        "}\n"
    )


@pytest.fixture
def fake_layout(tmp_path, monkeypatch, tool, fake_config_source):
    """
    Build a minimal fake repo layout under tmp_path:

    * ``conf/master``, ``conf/minion``, ``conf/proxy`` carry only
      ``existing_documented_opt`` — ``a_brand_new_opt`` is missing.
    * ``doc/ref/configuration/{master,minion,proxy}.rst`` carry the
      ``.. conf_master::`` (etc.) directive for
      ``existing_documented_opt`` only.

    Then monkey-patch the tool's path constants to point at the
    fake layout.
    """
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir()
    for daemon in ("master", "minion", "proxy"):
        (conf_dir / daemon).write_text("existing_documented_opt: ''\n")

    ref_dir = tmp_path / "doc" / "ref" / "configuration"
    ref_dir.mkdir(parents=True)
    for daemon in ("master", "minion", "proxy"):
        (ref_dir / f"{daemon}.rst").write_text(
            f".. conf_{daemon}:: existing_documented_opt\n\n"
            "``existing_documented_opt``\n"
            "---------------------------\n\n"
            "Default: ''\n"
        )

    monkeypatch.setattr(
        tool,
        "CONF_FILE",
        {daemon: conf_dir / daemon for daemon in ("master", "minion", "proxy")},
    )
    monkeypatch.setattr(
        tool,
        "REF_FILE",
        {daemon: ref_dir / f"{daemon}.rst" for daemon in ("master", "minion", "proxy")},
    )
    return tmp_path


def test_parse_opts_dict_extracts_keys_and_noqa(tool, fake_config_source):
    keys, noqa = tool.parse_opts_dict(fake_config_source, "DEFAULT_MASTER_OPTS")
    assert keys == {
        "existing_documented_opt",
        "a_brand_new_opt",
        "opt_with_marker",
    }
    assert noqa == {"opt_with_marker"}


def test_parse_conf_file_picks_up_commented_keys(tool, tmp_path):
    sample = tmp_path / "master"
    sample.write_text(
        "# A comment-only line\n"
        "documented_uncommented: ''\n"
        "#documented_commented: ''\n"
        "    nested: ''\n"  # indented, not a top-level key
    )
    found = tool.parse_conf_file(sample)
    assert found == {"documented_uncommented", "documented_commented"}


def test_parse_ref_file_picks_up_conf_directives(tool, tmp_path):
    ref = tmp_path / "master.rst"
    ref.write_text(
        ".. conf_master:: documented_master_opt\n"
        ".. conf_minion:: documented_minion_opt\n"
        ".. conf_proxy:: documented_proxy_opt\n"
        "Some prose that mentions documented_master_opt but does not declare it.\n"
    )
    found = tool.parse_ref_file(ref)
    assert found == {
        "documented_master_opt",
        "documented_minion_opt",
        "documented_proxy_opt",
    }


def test_undocumented_new_opt_is_flagged(tool, fake_layout, fake_config_source):
    """
    The core contract: an opt that exists in the runtime dict but is
    missing from ``conf/`` and ``doc/ref/configuration/`` triggers
    two issue strings (one per missing location).
    """
    issues = tool.run(config_source=fake_config_source)
    assert any("a_brand_new_opt" in issue and "conf" in issue for issue in issues)
    assert any(
        "a_brand_new_opt" in issue and "ref/configuration" in issue for issue in issues
    )


def test_noqa_marker_suppresses_flag(tool, fake_layout, fake_config_source):
    """
    ``# noqa: undocumented`` on the dict line is honoured.
    """
    issues = tool.run(config_source=fake_config_source)
    assert not any("opt_with_marker" in issue for issue in issues)


def test_documented_opt_is_silent(tool, fake_layout, fake_config_source):
    """
    The already-documented opt does not appear in any issue string.
    """
    issues = tool.run(config_source=fake_config_source)
    assert not any("existing_documented_opt" in issue for issue in issues)


def test_baseline_lets_existing_undocumented_opts_pass(
    tool, fake_layout, fake_config_source
):
    """
    The pre-commit hook is graded on *new* drift; pre-existing
    undocumented opts (passed in via ``--baseline``) must not fail
    the check.
    """
    issues = tool.run(
        config_source=fake_config_source,
        baseline={"a_brand_new_opt"},
    )
    # opt_with_marker is suppressed by noqa, a_brand_new_opt by baseline,
    # everything else is documented.
    assert issues == []


def test_run_returns_zero_when_clean(tool, fake_layout):
    """
    A config source where every key is documented in both places
    must return an empty issue list.
    """
    clean_source = (
        "DEFAULT_MASTER_OPTS = {'existing_documented_opt': ''}\n"
        "DEFAULT_MINION_OPTS = {'existing_documented_opt': ''}\n"
        "DEFAULT_PROXY_MINION_OPTS = {'existing_documented_opt': ''}\n"
    )
    issues = tool.run(config_source=clean_source)
    assert issues == []


def test_only_one_daemon_can_be_checked(tool, fake_layout, fake_config_source):
    """
    ``daemons=`` lets the caller (or ``--daemon``) narrow the scope.
    """
    issues = tool.run(config_source=fake_config_source, daemons=("minion",))
    # Minion dict only contains existing_documented_opt, so no issues
    # even though the master dict has an undocumented one.
    assert issues == []
