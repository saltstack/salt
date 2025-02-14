"""
    Tests of salt.states.gem
"""

import pytest

import salt.states.gem as gem
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {gem: {"__opts__": {"test": False}}}


def test_installed():
    gems = {"foo": ["1.0"], "bar": ["2.0"]}
    gem_list = MagicMock(return_value=gems)
    gem_install_succeeds = MagicMock(return_value=True)
    gem_install_fails = MagicMock(return_value=False)

    with patch.dict(gem.__salt__, {"gem.list": gem_list}):
        with patch.dict(gem.__salt__, {"gem.install": gem_install_succeeds}):
            ret = gem.installed("foo")
            assert ret["result"] is True
            ret = gem.installed("quux")
            assert ret["result"] is True
            gem_install_succeeds.assert_called_once_with(
                "quux",
                pre_releases=False,
                ruby=None,
                runas=None,
                version=None,
                proxy=None,
                rdoc=False,
                source=None,
                ri=False,
                gem_bin=None,
            )

        with patch.dict(gem.__salt__, {"gem.install": gem_install_fails}):
            ret = gem.installed("quux")
            assert ret["result"] is False
            gem_install_fails.assert_called_once_with(
                "quux",
                pre_releases=False,
                ruby=None,
                runas=None,
                version=None,
                proxy=None,
                rdoc=False,
                source=None,
                ri=False,
                gem_bin=None,
            )


def test_installed_version():
    gems = {"foo": ["1.0"], "bar": ["2.0"]}
    gem_list = MagicMock(return_value=gems)
    gem_install_succeeds = MagicMock(return_value=True)

    with patch.dict(gem.__salt__, {"gem.list": gem_list}):
        with patch.dict(gem.__salt__, {"gem.install": gem_install_succeeds}):
            ret = gem.installed("foo", version=">= 1.0")
            assert ret["result"] is True
            assert ret["comment"] == "Installed Gem meets version requirements."


def test_removed():
    gems = ["foo", "bar"]
    gem_list = MagicMock(return_value=gems)
    gem_uninstall_succeeds = MagicMock(return_value=True)
    gem_uninstall_fails = MagicMock(return_value=False)
    with patch.dict(gem.__salt__, {"gem.list": gem_list}):
        with patch.dict(gem.__salt__, {"gem.uninstall": gem_uninstall_succeeds}):
            ret = gem.removed("quux")
            assert ret["result"] is True
            ret = gem.removed("foo")
            assert ret["result"] is True
            gem_uninstall_succeeds.assert_called_once_with(
                "foo", None, runas=None, gem_bin=None
            )

        with patch.dict(gem.__salt__, {"gem.uninstall": gem_uninstall_fails}):
            ret = gem.removed("bar")
            assert ret["result"] is False
            gem_uninstall_fails.assert_called_once_with(
                "bar", None, runas=None, gem_bin=None
            )


def test_sources_add():
    gem_sources = ["http://foo", "http://bar"]
    gem_sources_list = MagicMock(return_value=gem_sources)
    gem_sources_add_succeeds = MagicMock(return_value=True)
    gem_sources_add_fails = MagicMock(return_value=False)
    with patch.dict(gem.__salt__, {"gem.sources_list": gem_sources_list}):
        with patch.dict(gem.__salt__, {"gem.sources_add": gem_sources_add_succeeds}):
            ret = gem.sources_add("http://foo")
            assert ret["result"] is True
            ret = gem.sources_add("http://fui")
            assert ret["result"] is True
            gem_sources_add_succeeds.assert_called_once_with(
                source_uri="http://fui", ruby=None, runas=None
            )
        with patch.dict(gem.__salt__, {"gem.sources_add": gem_sources_add_fails}):
            ret = gem.sources_add("http://fui")
            assert ret["result"] is False
            gem_sources_add_fails.assert_called_once_with(
                source_uri="http://fui", ruby=None, runas=None
            )


def test_sources_remove():
    gem_sources = ["http://foo", "http://bar"]
    gem_sources_list = MagicMock(return_value=gem_sources)
    gem_sources_remove_succeeds = MagicMock(return_value=True)
    gem_sources_remove_fails = MagicMock(return_value=False)
    with patch.dict(gem.__salt__, {"gem.sources_list": gem_sources_list}):
        with patch.dict(
            gem.__salt__, {"gem.sources_remove": gem_sources_remove_succeeds}
        ):
            ret = gem.sources_remove("http://fui")
            assert ret["result"] is True
            ret = gem.sources_remove("http://foo")
            assert ret["result"] is True
            gem_sources_remove_succeeds.assert_called_once_with(
                source_uri="http://foo", ruby=None, runas=None
            )
        with patch.dict(gem.__salt__, {"gem.sources_remove": gem_sources_remove_fails}):
            ret = gem.sources_remove("http://bar")
            assert ret["result"] is False
            gem_sources_remove_fails.assert_called_once_with(
                source_uri="http://bar", ruby=None, runas=None
            )
