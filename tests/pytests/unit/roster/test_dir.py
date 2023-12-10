"""
Test the directory roster.
"""


import logging

import pytest

import salt.config
import salt.loader
import salt.roster.dir as dir_


@pytest.fixture
def roster_domain():
    return "test.roster.domain"


@pytest.fixture
def expected(roster_domain):
    return {
        "basic": {
            "test1_us-east-2_test_basic": {
                "host": "127.0.0.2",
                "port": 22,
                "sudo": True,
                "user": "scoundrel",
            }
        },
        "domain": {
            "test1_us-east-2_test_domain": {
                "host": "test1_us-east-2_test_domain." + roster_domain,
                "port": 2222,
                "user": "george",
            }
        },
        "empty": {
            "test1_us-east-2_test_empty": {
                "host": "test1_us-east-2_test_empty." + roster_domain,
            }
        },
    }


@pytest.fixture
def create_roster_files(tmp_path):
    badfile_contents = """
    #!jinja|yaml
    host: 127.0.0.2
    port: 22
    THIS FILE IS NOT WELL FORMED YAML
    sudo: true
    user: scoundrel
    """

    basic_contents = """
    #!jinja|yaml
    host: 127.0.0.2
    port: 22
    sudo: true
    user: scoundrel
    """

    domain_contents = """
    #!jinja|yaml
    port: 2222
    user: george
    """

    empty_contents = """
    """

    with pytest.helpers.temp_file(
        "test1_us-east-2_test_badfile", badfile_contents, directory=tmp_path
    ), pytest.helpers.temp_file(
        "test1_us-east-2_test_basic", basic_contents, directory=tmp_path
    ), pytest.helpers.temp_file(
        "test1_us-east-2_test_domain", domain_contents, directory=tmp_path
    ), pytest.helpers.temp_file(
        "test1_us-east-2_test_empty", empty_contents, directory=tmp_path
    ):
        yield


@pytest.fixture
def configure_loader_modules(roster_domain, salt_master_factory, tmp_path):

    opts = salt_master_factory.config.copy()
    utils = salt.loader.utils(opts, whitelist=["json", "stringutils", "roster_matcher"])
    runner = salt.loader.runner(opts, utils=utils, whitelist=["salt"])
    return {
        dir_: {
            "__opts__": {
                "extension_modules": "",
                "optimization_order": [0, 1, 2],
                "renderer": "jinja|yaml",
                "renderer_blacklist": [],
                "renderer_whitelist": [],
                "roster_dir": str(tmp_path),
                "roster_domain": roster_domain,
            },
            "__runner__": runner,
            "__utils__": utils,
        }
    }


def _test_match(ret, expected):
    """
    assertDictEquals is too strict with OrderedDicts. The order isn't crucial
    for roster entries, so we test that they contain the expected members directly.
    """
    assert ret != {}, "Found no matches, expected {}".format(expected)
    for minion, data in ret.items():
        assert minion in expected, "Expected minion {} to match, but it did not".format(
            minion
        )
        assert (
            dict(data) == expected[minion]
        ), "Data for minion {} did not match expectations".format(minion)


def test_basic_glob(expected, create_roster_files):
    """Test that minion files in the directory roster match and render."""
    expected = expected["basic"]
    ret = dir_.targets("*_basic", saltenv="")
    _test_match(ret, expected)


def test_basic_re(expected, create_roster_files):
    """Test that minion files in the directory roster match and render."""
    expected = expected["basic"]
    ret = dir_.targets(".*basic$", "pcre", saltenv="")
    _test_match(ret, expected)


def test_basic_list(expected, create_roster_files):
    """Test that minion files in the directory roster match and render."""
    expected = expected["basic"]
    ret = dir_.targets(expected.keys(), "list", saltenv="")
    _test_match(ret, expected)


def test_roster_domain(expected, create_roster_files):
    """Test that when roster_domain is configured, it will provide a default hostname
    in the roster of {filename}.{roster_domain}, so that users can use the minion
    id as the local hostname without having to supply the fqdn everywhere."""
    expected = expected["domain"]
    ret = dir_.targets(expected.keys(), "list", saltenv="")
    _test_match(ret, expected)


def test_empty(expected, create_roster_files):
    """Test that an empty roster file matches its hostname"""
    expected = expected["empty"]
    ret = dir_.targets("*_empty", saltenv="")
    _test_match(ret, expected)


def test_nomatch(create_roster_files):
    """Test that no errors happen when no files match"""
    try:
        ret = dir_.targets("", saltenv="")
    except:  # pylint: disable=bare-except
        pytest.fail(
            "No files matched, which is OK, but we raised an exception and we should not have."
        )
    assert len(ret) == 0, "Expected empty target list to yield zero targets."


def test_badfile(create_roster_files):
    """Test error handling when we can't render a file"""
    ret = dir_.targets("*badfile", saltenv="")
    assert len(ret) == 0


def test_badfile_logging(caplog, create_roster_files):
    """Test error handling when we can't render a file"""
    with caplog.at_level(logging.WARNING, logger="salt.roster.dir"):
        dir_.targets("*badfile", saltenv="")
        assert "test1_us-east-2_test_badfile" in caplog.text
