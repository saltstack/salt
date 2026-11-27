"""
Unit tests for ``tools.pkg.native_deps``: lock-file parsing, backend
output parsers, floor computation, and vendor-plan derivation.

Container-dependent code (`audit_slug` and the ``_dexec``/create helpers)
isn't exercised here — those are validated end-to-end by running
``tools pkg native-deps audit <slug>`` against real images.
"""

# pylint: disable=3rd-party-module-not-gated

from __future__ import annotations

import textwrap

import pytest

# `tools.pkg` imports `ptscripts` via `tools/__init__.py`. That's
# installed in the onedir/system tools-venv but not in the
# ci-test-onedir nox env where this test module is collected on macOS
# and Windows runners. Skip cleanly on hosts without it instead of
# failing collection.
pytest.importorskip("ptscripts")

from tools.pkg import native_deps  # noqa: E402

# ----- lock parser -----


def test_iter_lock_skips_comments_and_env_markers(tmp_path):
    lock = tmp_path / "linux.lock"
    lock.write_text(
        textwrap.dedent(
            """\
            # uv-generated header
            aiohttp==3.14.1
                # via -r requirements/base.txt
            typing-extensions==4.15.0 ; python_version < '3.11'
            requests[socks]==2.34.2
                # via -r requirements/base.txt
            """
        )
    )
    pairs = list(native_deps.iter_lock(lock))
    assert pairs == [
        ("aiohttp", "3.14.1"),
        ("typing-extensions", "4.15.0"),
        ("requests", "2.34.2"),
    ]


def test_iter_lock_lowercases_pkg(tmp_path):
    lock = tmp_path / "linux.lock"
    lock.write_text("PyYAML==6.0.3\n")
    assert list(native_deps.iter_lock(lock)) == [("pyyaml", "6.0.3")]


# ----- version parsers -----


def test_parse_rpm_version_takes_first_version_line():
    stdout = textwrap.dedent(
        """\
        Name          : python3-six
        Arch          : noarch
        Version       : 1.16.0
        Release       : 4.ph5
        """
    )
    assert native_deps._parse_rpm_version(stdout) == "1.16.0"


def test_parse_rpm_version_returns_none_on_empty():
    assert native_deps._parse_rpm_version("") is None


def test_parse_deb_version_strips_debian_revision():
    stdout = "Package: python3-six\nVersion: 1.16.0-4\n"
    assert native_deps._parse_deb_version(stdout) == "1.16.0"


def test_parse_deb_version_strips_backport_suffix():
    stdout = "Package: python3-foo\nVersion: 2.1.0+deb12u1\n"
    assert native_deps._parse_deb_version(stdout) == "2.1.0"


def test_parse_deb_version_handles_plain_pin():
    stdout = "Version: 3.2.1\n"
    assert native_deps._parse_deb_version(stdout) == "3.2.1"


# ----- floors -----


def _audit(slug: str, pyver: str, pkgs: dict) -> dict:
    """Build a minimal audit dict for compute_floors."""
    return {
        "slug": slug,
        "python_version": pyver,
        "packages": {
            name: {
                "lock_version": entry["lock"],
                "native_pkg": f"python3-{name}",
                "native_version": entry.get("native"),
                "status": "present" if entry.get("native") else "missing",
            }
            for name, entry in pkgs.items()
        },
    }


def test_floor_is_min_across_voters():
    audits = [
        _audit(
            "ubuntu-24.04",
            "3.12",
            {"requests": {"lock": "2.34.2", "native": "2.31.0"}},
        ),
        _audit(
            "debian-12",
            "3.11",  # different pyver — segregated
            {"requests": {"lock": "2.34.2", "native": "2.28.1"}},
        ),
        _audit(
            "ubuntu-22.04",
            "3.12",  # same pyver as ubuntu-24.04
            {"requests": {"lock": "2.34.2", "native": "2.25.1"}},
        ),
    ]
    out = native_deps.compute_floors(audits)
    assert set(out) == {"py3.11", "py3.12"}
    assert out["py3.12"]["requests"]["floor"] == "2.25.1"
    assert out["py3.12"]["requests"]["floor_slug"] == "ubuntu-22.04"
    assert out["py3.12"]["requests"]["votes"] == {
        "ubuntu-22.04": "2.25.1",
        "ubuntu-24.04": "2.31.0",
    }
    assert out["py3.11"]["requests"]["floor"] == "2.28.1"


def test_missing_distros_do_not_vote_but_are_recorded():
    audits = [
        _audit("photon-5", "3.14", {"rich": {"lock": "15.0.0"}}),  # missing
        _audit(
            "ubuntu-26.04",
            "3.14",
            {"rich": {"lock": "15.0.0", "native": "14.1.0"}},
        ),
    ]
    out = native_deps.compute_floors(audits)
    info = out["py3.14"]["rich"]
    assert info["floor"] == "14.1.0"
    assert info["votes"] == {"ubuntu-26.04": "14.1.0"}
    assert info["missing_in"] == ["photon-5"]


def test_floor_none_when_no_voter_ships_pkg():
    audits = [
        _audit("photon-5", "3.14", {"opentelemetry-api": {"lock": "1.42.1"}}),
        _audit("ubuntu-26.04", "3.14", {"opentelemetry-api": {"lock": "1.42.1"}}),
    ]
    out = native_deps.compute_floors(audits)
    info = out["py3.14"]["opentelemetry-api"]
    assert info["floor"] is None
    assert info["floor_slug"] is None
    assert info["gap_major"] is None
    assert info["votes"] == {}
    assert info["missing_in"] == ["photon-5", "ubuntu-26.04"]


def test_gap_major_reflects_lock_vs_floor_major_delta():
    audits = [
        _audit(
            "debian-12",
            "3.11",
            {"pyzmq": {"lock": "27.1.0", "native": "23.2.1"}},
        ),
        _audit(
            "ubuntu-22.04",
            "3.11",
            {"pyzmq": {"lock": "27.1.0", "native": "24.0.1"}},
        ),
    ]
    out = native_deps.compute_floors(audits)
    info = out["py3.11"]["pyzmq"]
    assert info["floor"] == "23.2.1"
    assert info["lock_pin"] == "27.1.0"
    assert info["gap_major"] == 4


def test_version_sort_uses_pep440_not_lexical():
    # Lexical sort would pick "10.0.0" < "2.0.0" ("1" < "2"); PEP 440 must not.
    audits = [
        _audit("a", "3.11", {"pkg": {"lock": "11.0.0", "native": "10.0.0"}}),
        _audit("b", "3.11", {"pkg": {"lock": "11.0.0", "native": "2.0.0"}}),
    ]
    out = native_deps.compute_floors(audits)
    assert out["py3.11"]["pkg"]["floor"] == "2.0.0"


# ----- vendor plan -----


def test_vendor_list_lists_only_missing_pkgs_pinned_at_lock_version():
    audit = _audit(
        "photon-5",
        "3.14",
        {
            "msgpack": {"lock": "1.2.1", "native": "1.2.2"},  # present
            "rich": {"lock": "15.0.0"},  # missing
            "typer": {"lock": "0.26.7"},  # missing
            "pyzmq": {"lock": "27.1.0", "native": "23.2.1"},  # present
        },
    )
    assert native_deps.vendor_list(audit) == [
        "rich==15.0.0",
        "typer==0.26.7",
    ]


def test_vendor_list_sorted_alphabetically():
    audit = _audit(
        "slug",
        "3.11",
        {
            "zzz-pkg": {"lock": "1.0"},
            "aaa-pkg": {"lock": "2.0"},
            "mmm-pkg": {"lock": "3.0"},
        },
    )
    assert native_deps.vendor_list(audit) == [
        "aaa-pkg==2.0",
        "mmm-pkg==3.0",
        "zzz-pkg==1.0",
    ]


# ----- distro table sanity -----


def test_every_distro_defines_a_known_backend():
    known = {
        native_deps.BACKEND_TDNF,
        native_deps.BACKEND_YUM_DNF,
        native_deps.BACKEND_APT,
    }
    for slug, descr in native_deps.DISTROS.items():
        assert descr["backend"] in known, f"{slug} has unknown backend"


def test_deb_pkgmap_covers_known_rename_cases():
    # Regression guard: Debian renames pyzmq -> python3-zmq (not
    # python3-pyzmq), so if someone forgets the mapping the audit silently
    # reports pyzmq as missing on every deb distro. Pin the invariant.
    assert native_deps.DEB_PKGMAP["pyzmq"] == "python3-zmq"
    assert native_deps.DEB_PKGMAP["pyyaml"] == "python3-yaml"
    assert native_deps.DEB_PKGMAP["pycryptodomex"] == "python3-pycryptodome"


def test_amazon_pkgmap_differs_from_rhel_on_pyzmq():
    # Amazon Linux 2023 names it python3-pyzmq, RHEL/Rocky/Fedora use
    # python3-zmq. Guard against drift between those tables.
    assert native_deps.AMAZON_PKGMAP["pyzmq"] == "python3-pyzmq"
    assert native_deps.RHEL_PKGMAP["pyzmq"] == "python3-zmq"


# ----- import-name resolution -----


def test_import_names_falls_back_to_dash_to_underscore():
    assert native_deps.import_names("markdown-it-py-unknown") == [
        "markdown_it_py_unknown"
    ]
    assert native_deps.import_names("xxhash") == ["xxhash"]


def test_import_names_uses_hand_override_for_py_prefixed():
    # pyyaml imports as yaml, not as pyyaml — the fallback would get this
    # wrong, so IMPORT_NAMES must override.
    assert native_deps.import_names("pyyaml") == ["yaml"]
    assert native_deps.import_names("pyzmq") == ["zmq"]
    assert native_deps.import_names("pycryptodomex") == ["Cryptodome"]


def test_import_names_handles_namespace_packages():
    assert native_deps.import_names("jaraco-text") == ["jaraco.text"]
    assert native_deps.import_names("zc-lockfile") == ["zc.lockfile"]


def test_import_names_multi_module_entry_preserved():
    # googleapis-common-protos ships two sibling namespaces.
    assert native_deps.import_names("googleapis-common-protos") == [
        "google.api",
        "google.rpc",
    ]


# ----- grep parsing + tier classification -----


def test_parse_grep_output_splits_by_leading_whitespace():
    stdout = (
        "salt/foo.py:10:import aiohttp\n"
        "salt/bar.py:5:    import aiohttp\n"
        "salt/bar.py:6:\timport aiohttp.web\n"
    )
    top, indented = native_deps._parse_grep_output(stdout)
    assert top == ["salt/foo.py:10"]
    assert indented == ["salt/bar.py:5", "salt/bar.py:6"]


def test_parse_grep_output_skips_malformed_lines():
    stdout = "not-a-grep-line\nsalt/x.py:3:import foo\n"
    top, indented = native_deps._parse_grep_output(stdout)
    assert top == ["salt/x.py:3"]
    assert indented == []


def test_classify_from_sites_module_top_wins_on_hot_path():
    tier, features, sites = native_deps._classify_from_sites(
        ["salt/a.py:1"],
        ["salt/b.py:5", "salt/c.py:6"],
    )
    assert tier == native_deps.TIER_MODULE_TOP
    assert features == []
    # module-top sites come first, indented appended.
    assert sites == ["salt/a.py:1", "salt/b.py:5", "salt/c.py:6"]


def test_classify_from_sites_indented_only():
    tier, features, sites = native_deps._classify_from_sites([], ["salt/x.py:9"])
    assert tier == native_deps.TIER_INDENTED
    assert features == []
    assert sites == ["salt/x.py:9"]


def test_classify_from_sites_none():
    tier, features, sites = native_deps._classify_from_sites([], [])
    assert tier == native_deps.TIER_NONE
    assert features == []
    assert sites == []


# ----- lazy-feature-owner handling -----


def test_feature_for_site_matches_exact_file():
    assert native_deps._feature_for_site("salt/transport/ws.py:8") == "ws transport"


def test_feature_for_site_matches_dir_prefix():
    assert (
        native_deps._feature_for_site("salt/netapi/rest_cherrypy/app.py:599")
        == "cherrypy netapi backend"
    )


def test_feature_for_site_none_for_hot_path():
    assert native_deps._feature_for_site("salt/utils/versions.py:19") is None


def test_classify_feature_opt_in_when_all_top_sites_are_owned():
    # aiohttp-style: unindented but only in salt/transport/ws.py.
    tier, features, sites = native_deps._classify_from_sites(
        ["salt/transport/ws.py:8", "salt/transport/ws.py:9"],
        [],
    )
    assert tier == native_deps.TIER_FEATURE_OPT_IN
    assert features == ["ws transport"]
    assert sites == ["salt/transport/ws.py:8", "salt/transport/ws.py:9"]


def test_classify_module_top_if_any_top_site_is_hot_path():
    # looseversion-style: module-top in both a lazy-owned file AND a
    # hot-path utility — treat as hot-path.
    tier, features, sites = native_deps._classify_from_sites(
        ["salt/transport/ws.py:8", "salt/utils/versions.py:19"],
        [],
    )
    assert tier == native_deps.TIER_MODULE_TOP
    assert features == []


def test_classify_feature_opt_in_collects_multiple_features():
    tier, features, sites = native_deps._classify_from_sites(
        [
            "salt/transport/zeromq.py:100",
            "salt/transport/ws.py:8",
        ],
        [],
    )
    assert tier == native_deps.TIER_FEATURE_OPT_IN
    assert features == ["ws transport", "zeromq transport"]


# ----- vendor plan tier filtering -----


def _audit_with_tiers(packages: dict) -> dict:
    return {
        "slug": "slug",
        "python_version": "3.14",
        "packages": {
            name: {
                "lock_version": meta["lock"],
                "native_pkg": f"python3-{name}",
                "native_version": meta.get("native"),
                "status": "present" if meta.get("native") else "missing",
                "import_tier": meta.get("tier", native_deps.TIER_NONE),
                "import_names": [name],
                "import_sites": [],
            }
            for name, meta in packages.items()
        },
    }


def test_vendor_list_tier_filter_narrows_to_module_top_crash_set():
    audit = _audit_with_tiers(
        {
            "aiohttp": {"lock": "3.14.1", "tier": native_deps.TIER_MODULE_TOP},
            "croniter": {"lock": "6.2.2", "tier": native_deps.TIER_INDENTED},
            "rich": {"lock": "15.0.0", "tier": native_deps.TIER_NONE},
            # Present deps are excluded regardless of tier.
            "pyzmq": {
                "lock": "27.1.0",
                "native": "23.2.1",
                "tier": native_deps.TIER_MODULE_TOP,
            },
        }
    )
    assert native_deps.vendor_list(audit, tiers=(native_deps.TIER_MODULE_TOP,)) == [
        "aiohttp==3.14.1",
    ]


def test_vendor_plan_sections_splits_into_four_lists():
    audit = _audit_with_tiers(
        {
            "looseversion": {"lock": "1.3.0", "tier": native_deps.TIER_MODULE_TOP},
            "aiohttp": {"lock": "3.14.1", "tier": native_deps.TIER_FEATURE_OPT_IN},
            "croniter": {"lock": "6.2.2", "tier": native_deps.TIER_INDENTED},
            "cheroot": {"lock": "11.1.2", "tier": native_deps.TIER_NONE},
            "rich": {"lock": "15.0.0", "tier": native_deps.TIER_NONE},
        }
    )
    sections = native_deps.vendor_plan_sections(audit)
    assert set(sections) == {"module_top", "feature_opt_in", "indented", "transitive"}
    assert sections["module_top"] == ["looseversion==1.3.0"]
    assert sections["feature_opt_in"] == ["aiohttp==3.14.1"]
    assert sections["indented"] == ["croniter==6.2.2"]
    assert sections["transitive"] == ["cheroot==11.1.2", "rich==15.0.0"]
