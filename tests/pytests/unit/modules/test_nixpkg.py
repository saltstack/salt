"""
Unit tests for the nixpkg execution module.
"""

import copy
import json

import pytest

import salt.modules.nixpkg as nixpkg
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

NIX_LIST_JSON = json.dumps(
    {
        "elements": {
            "vim": {"storePaths": ["/nix/store/abc123-vim-9.0.1"]},
            "git": {"storePaths": ["/nix/store/def456-git-2.42.0"]},
        }
    }
)

NIX_SEARCH_VIM_JSON = json.dumps(
    {
        "legacyPackages.x86_64-linux.vim": {
            "pname": "vim",
            "version": "9.1.0",
            "description": "The most popular clone of the VI editor",
        }
    }
)


@pytest.fixture
def configure_loader_modules():
    return {
        nixpkg: {
            "__opts__": {"user": "testuser"},
            "__context__": {},
        }
    }


# __virtual__ tests


def test_virtual_success():
    with patch(
        "salt.utils.path.which", return_value="/home/testuser/.nix-profile/bin/nix"
    ):
        result = nixpkg.__virtual__()
        assert result == "pkg"


def test_virtual_missing_binaries():
    with patch("salt.utils.path.which", return_value=None):
        result = nixpkg.__virtual__()
        assert isinstance(result, tuple)
        assert result[0] is False
        assert "nix" in result[1]


# _extract_version tests


def test_extract_version_standard_path():
    info = {"storePaths": ["/nix/store/4s0nkdxk97ckjs90ag0arsxli912pymy-aria2-1.37.0"]}
    assert nixpkg._extract_version(info) == "1.37.0"


def test_extract_version_with_suffix():
    info = {
        "storePaths": ["/nix/store/4s0nkdxk97ckjs90ag0arsxli912pymy-aria2-1.37.0-bin"]
    }
    assert nixpkg._extract_version(info) == "1.37.0"


def test_extract_version_hyphenated_name():
    info = {"storePaths": ["/nix/store/abc123-google-chrome-120.0.1"]}
    assert nixpkg._extract_version(info) == "120.0.1"


def test_extract_version_hyphenated_name_with_output():
    info = {"storePaths": ["/nix/store/abc123-xorg-server-21.1.8-dev"]}
    assert nixpkg._extract_version(info) == "21.1.8"


def test_extract_version_no_store_paths():
    info = {}
    assert nixpkg._extract_version(info) == "unknown"


def test_extract_version_empty_store_paths():
    info = {"storePaths": []}
    assert nixpkg._extract_version(info) == "unknown"


# _add_source tests


def test_add_source_plain_package():
    assert nixpkg._add_source("vim") == "nixpkgs#vim"


def test_add_source_already_qualified():
    assert nixpkg._add_source("nixpkgs#vim") == "nixpkgs#vim"


def test_add_source_custom_flake():
    assert nixpkg._add_source("myflake#vim") == "myflake#vim"


# list_pkgs tests


def test_list_pkgs():
    mock_run = MagicMock(return_value={"stdout": NIX_LIST_JSON, "retcode": 0})
    mock_add_pkg = MagicMock(
        side_effect=lambda ret, name, ver: ret.update({name: [ver]})
    )
    mock_sort = MagicMock()
    mock_stringify = MagicMock(
        side_effect=lambda ret: ret.update({k: ",".join(v) for k, v in ret.items()})
    )

    with patch.dict(
        nixpkg.__salt__,
        {
            "cmd.run_all": mock_run,
            "pkg_resource.add_pkg": mock_add_pkg,
            "pkg_resource.sort_pkglist": mock_sort,
            "pkg_resource.stringify": mock_stringify,
        },
    ):
        result = nixpkg.list_pkgs()
        assert "vim" in result
        assert "git" in result


def test_list_pkgs_purge_desired():
    assert nixpkg.list_pkgs(purge_desired=True) == {}


def test_list_pkgs_from_context():
    mock_context = {"vim": ["9.0.1"], "git": ["2.42.0"]}
    mock_stringify = MagicMock()

    with patch.dict(nixpkg.__context__, {"pkg.list_pkgs": mock_context}):
        with patch.dict(nixpkg.__salt__, {"pkg_resource.stringify": mock_stringify}):
            result = nixpkg.list_pkgs(versions_as_list=True)
            assert result == mock_context


def test_list_pkgs_from_context_stringified():
    mock_context = {"vim": ["9.0.1"], "git": ["2.42.0"]}

    def mock_stringify(ret):
        for k, v in ret.items():
            ret[k] = ",".join(v)

    with patch.dict(nixpkg.__context__, {"pkg.list_pkgs": mock_context}):
        with patch.dict(nixpkg.__salt__, {"pkg_resource.stringify": mock_stringify}):
            result = nixpkg.list_pkgs(versions_as_list=False)
            assert result["vim"] == "9.0.1"
            assert result["git"] == "2.42.0"


# install tests


def test_install_single_package():
    mock_parse = MagicMock(return_value=({"vim": None}, "repository"))
    mock_run = MagicMock(return_value={"stdout": "", "stderr": "", "retcode": 0})

    old_pkgs = {"git": "2.42.0"}
    new_pkgs = {"git": "2.42.0", "vim": "9.0.1"}
    call_count = {"n": 0}

    def mock_list_pkgs(**kwargs):
        call_count["n"] += 1
        return copy.deepcopy(old_pkgs if call_count["n"] == 1 else new_pkgs)

    with patch.dict(
        nixpkg.__salt__,
        {
            "pkg_resource.parse_targets": mock_parse,
            "cmd.run_all": mock_run,
        },
    ):
        with patch.object(nixpkg, "list_pkgs", side_effect=mock_list_pkgs):
            result = nixpkg.install(name="vim")
            assert "vim" in result
            assert result["vim"]["new"] == "9.0.1"
            assert result["vim"]["old"] == ""


def test_install_no_targets():
    mock_parse = MagicMock(return_value=({}, "repository"))

    with patch.dict(nixpkg.__salt__, {"pkg_resource.parse_targets": mock_parse}):
        result = nixpkg.install(name=None)
        assert result == {}


def test_install_error():
    mock_parse = MagicMock(return_value=({"vim": None}, "repository"))
    mock_run = MagicMock(
        return_value={"stdout": "", "stderr": "error: package not found", "retcode": 1}
    )

    with patch.dict(
        nixpkg.__salt__,
        {
            "pkg_resource.parse_targets": mock_parse,
            "cmd.run_all": mock_run,
        },
    ):
        with patch.object(nixpkg, "list_pkgs", return_value={}):
            with pytest.raises(CommandExecutionError):
                nixpkg.install(name="nonexistent")


# remove tests


def test_remove_single_package():
    mock_parse = MagicMock(return_value=({"vim": None}, "repository"))
    mock_run = MagicMock(return_value={"stdout": "", "stderr": "", "retcode": 0})

    old_pkgs = {"git": "2.42.0", "vim": "9.0.1"}
    new_pkgs = {"git": "2.42.0"}
    call_count = {"n": 0}

    def mock_list_pkgs(**kwargs):
        call_count["n"] += 1
        return copy.deepcopy(old_pkgs if call_count["n"] == 1 else new_pkgs)

    with patch.dict(
        nixpkg.__salt__,
        {
            "pkg_resource.parse_targets": mock_parse,
            "cmd.run_all": mock_run,
        },
    ):
        with patch.object(nixpkg, "list_pkgs", side_effect=mock_list_pkgs):
            result = nixpkg.remove(name="vim")
            assert "vim" in result
            assert result["vim"]["old"] == "9.0.1"
            assert result["vim"]["new"] == ""


def test_remove_package_not_installed():
    mock_parse = MagicMock(return_value=({"vim": None}, "repository"))

    with patch.dict(nixpkg.__salt__, {"pkg_resource.parse_targets": mock_parse}):
        with patch.object(nixpkg, "list_pkgs", return_value={"git": "2.42.0"}):
            result = nixpkg.remove(name="vim")
            assert result == {}


# upgrade tests


def test_upgrade_all():
    mock_run = MagicMock(return_value={"stdout": "", "stderr": "", "retcode": 0})

    old_pkgs = {"vim": "9.0.1"}
    new_pkgs = {"vim": "9.1.0"}
    call_count = {"n": 0}

    def mock_list_pkgs(**kwargs):
        call_count["n"] += 1
        return copy.deepcopy(old_pkgs if call_count["n"] == 1 else new_pkgs)

    with patch.dict(nixpkg.__salt__, {"cmd.run_all": mock_run}):
        with patch.object(nixpkg, "list_pkgs", side_effect=mock_list_pkgs):
            with patch.object(nixpkg, "refresh_db", return_value=True):
                result = nixpkg.upgrade()
                assert "vim" in result
                assert result["vim"]["old"] == "9.0.1"
                assert result["vim"]["new"] == "9.1.0"


def test_upgrade_error():
    mock_run = MagicMock(
        return_value={"stdout": "", "stderr": "error: upgrade failed", "retcode": 1}
    )

    with patch.dict(nixpkg.__salt__, {"cmd.run_all": mock_run}):
        with patch.object(nixpkg, "list_pkgs", return_value={"vim": "9.0.1"}):
            with patch.object(nixpkg, "refresh_db", return_value=True):
                with pytest.raises(CommandExecutionError):
                    nixpkg.upgrade()


# version tests


def test_version():
    mock_version = MagicMock(return_value="9.0.1")
    with patch.dict(nixpkg.__salt__, {"pkg_resource.version": mock_version}):
        result = nixpkg.version("vim")
        assert result == "9.0.1"
        mock_version.assert_called_once_with("vim")


# latest_version tests


def test_latest_version_single():
    mock_run = MagicMock(return_value={"stdout": NIX_SEARCH_VIM_JSON, "retcode": 0})

    with patch.dict(nixpkg.__salt__, {"cmd.run_all": mock_run}):
        with patch.object(nixpkg, "list_pkgs", return_value={"vim": "9.0.1"}):
            with patch.object(nixpkg, "refresh_db", return_value=True):
                result = nixpkg.latest_version("vim")
                assert result == "9.1.0"


def test_latest_version_already_latest():
    search_json = json.dumps(
        {
            "legacyPackages.x86_64-linux.vim": {
                "pname": "vim",
                "version": "9.0.1",
            }
        }
    )
    mock_run = MagicMock(return_value={"stdout": search_json, "retcode": 0})

    with patch.dict(nixpkg.__salt__, {"cmd.run_all": mock_run}):
        with patch.object(nixpkg, "list_pkgs", return_value={"vim": "9.0.1"}):
            with patch.object(nixpkg, "refresh_db", return_value=True):
                result = nixpkg.latest_version("vim")
                assert result == ""


def test_latest_version_not_found():
    mock_run = MagicMock(
        return_value={"stdout": "", "stderr": "not found", "retcode": 1}
    )

    with patch.dict(nixpkg.__salt__, {"cmd.run_all": mock_run}):
        with patch.object(nixpkg, "list_pkgs", return_value={}):
            with patch.object(nixpkg, "refresh_db", return_value=True):
                result = nixpkg.latest_version("nonexistent")
                assert result == ""


# refresh_db tests


def test_refresh_db_success():
    mock_run = MagicMock(return_value={"stdout": "", "stderr": "", "retcode": 0})

    with patch.dict(nixpkg.__salt__, {"cmd.run_all": mock_run}):
        assert nixpkg.refresh_db() is True


def test_refresh_db_failure():
    mock_run = MagicMock(return_value={"stdout": "", "stderr": "error", "retcode": 1})

    with patch.dict(nixpkg.__salt__, {"cmd.run_all": mock_run}):
        assert nixpkg.refresh_db() is False


# collect_garbage tests


def test_collect_garbage():
    mock_run = MagicMock(
        return_value={
            "stdout": "removing old generations\n3 store paths deleted, 150.00 MiB freed",
            "retcode": 0,
        }
    )

    with patch.dict(nixpkg.__salt__, {"cmd.run_all": mock_run}):
        result = nixpkg.collect_garbage()
        assert len(result) == 2
        assert "3 store paths deleted" in result[1]


# uninstall tests


def test_uninstall_delegates_to_remove():
    with patch.object(
        nixpkg, "remove", return_value={"vim": {"old": "9.0.1", "new": ""}}
    ) as mock_remove:
        result = nixpkg.uninstall("vim")
        mock_remove.assert_called_once_with(pkgs=("vim",))
        assert "vim" in result
