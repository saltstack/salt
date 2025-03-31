"""
    Taken 1:1 from test cases for salt.modules.config
    This tests the SSH wrapper module.
"""

import fnmatch

import pytest

import salt.client.ssh.wrapper.config as config
from tests.support.mock import patch


@pytest.fixture
def defaults():
    return {
        "test.option.foo": "value of test.option.foo in defaults",
        "test.option.bar": "value of test.option.bar in defaults",
        "test.option.baz": "value of test.option.baz in defaults",
        "test.option": "value of test.option in defaults",
    }


@pytest.fixture
def no_match():
    return "test.option.nope"


@pytest.fixture
def opt_name():
    return "test.option.foo"


@pytest.fixture
def wildcard_opt_name():
    return "test.option.b*"


@pytest.fixture
def configure_loader_modules():
    return {
        config: {
            "__opts__": {
                "test.option.foo": "value of test.option.foo in __opts__",
                "test.option.bar": "value of test.option.bar in __opts__",
                "test.option.baz": "value of test.option.baz in __opts__",
            },
            "__pillar__": {
                "test.option.foo": "value of test.option.foo in __pillar__",
                "test.option.bar": "value of test.option.bar in __pillar__",
                "test.option.baz": "value of test.option.baz in __pillar__",
                "master": {
                    "test.option.foo": "value of test.option.foo in master",
                    "test.option.bar": "value of test.option.bar in master",
                    "test.option.baz": "value of test.option.baz in master",
                },
            },
            "__grains__": {
                "test.option.foo": "value of test.option.foo in __grains__",
                "test.option.bar": "value of test.option.bar in __grains__",
                "test.option.baz": "value of test.option.baz in __grains__",
            },
        }
    }


def _wildcard_match(data, wildcard_opt_name):
    return {x: data[x] for x in fnmatch.filter(data, wildcard_opt_name)}


def test_defaults_only_name(defaults):
    with patch.dict(config.DEFAULTS, defaults):
        opt_name = "test.option"
        opt = config.option(opt_name)
        assert opt == config.DEFAULTS[opt_name]


def test_no_match(defaults, no_match, wildcard_opt_name):
    """
    Make sure that the defa
    """
    with patch.dict(config.DEFAULTS, defaults):
        ret = config.option(no_match)
        assert ret == "", ret

        default = "wat"
        ret = config.option(no_match, default=default)
        assert ret == default, ret

        ret = config.option(no_match, wildcard=True)
        assert ret == {}, ret

        default = {"foo": "bar"}
        ret = config.option(no_match, default=default, wildcard=True)
        assert ret == default, ret

        # Should be no match since wildcard=False
        ret = config.option(wildcard_opt_name)
        assert ret == "", ret


def test_omits(defaults, opt_name, wildcard_opt_name):
    with patch.dict(config.DEFAULTS, defaults):

        # ********** OMIT NOTHING **********

        # Match should be in __opts__ dict
        ret = config.option(opt_name)
        assert ret == config.__opts__[opt_name], ret

        # Wildcard match
        ret = config.option(wildcard_opt_name, wildcard=True)
        assert ret == _wildcard_match(config.__opts__, wildcard_opt_name), ret

        # ********** OMIT __opts__ **********

        # Match should be in __grains__ dict
        ret = config.option(opt_name, omit_opts=True)
        assert ret == config.__grains__[opt_name], ret

        # Wildcard match
        ret = config.option(wildcard_opt_name, omit_opts=True, wildcard=True)
        assert ret == _wildcard_match(config.__grains__, wildcard_opt_name), ret

        # ********** OMIT __opts__, __grains__ **********

        # Match should be in __pillar__ dict
        ret = config.option(opt_name, omit_opts=True, omit_grains=True)
        assert ret == config.__pillar__[opt_name], ret

        # Wildcard match
        ret = config.option(
            wildcard_opt_name, omit_opts=True, omit_grains=True, wildcard=True
        )
        assert ret == _wildcard_match(config.__pillar__, wildcard_opt_name), ret

        # ********** OMIT __opts__, __grains__, __pillar__ **********

        # Match should be in master opts
        ret = config.option(
            opt_name, omit_opts=True, omit_grains=True, omit_pillar=True
        )
        assert ret == config.__pillar__["master"][opt_name], ret

        # Wildcard match
        ret = config.option(
            wildcard_opt_name,
            omit_opts=True,
            omit_grains=True,
            omit_pillar=True,
            wildcard=True,
        )
        assert ret == _wildcard_match(
            config.__pillar__["master"], wildcard_opt_name
        ), ret

        # ********** OMIT ALL THE THINGS **********

        # Match should be in master opts
        ret = config.option(
            opt_name,
            omit_opts=True,
            omit_grains=True,
            omit_pillar=True,
            omit_master=True,
        )
        assert ret == config.DEFAULTS[opt_name], ret

        # Wildcard match
        ret = config.option(
            wildcard_opt_name,
            omit_opts=True,
            omit_grains=True,
            omit_pillar=True,
            omit_master=True,
            wildcard=True,
        )
        assert ret == _wildcard_match(config.DEFAULTS, wildcard_opt_name), ret

        # Match should be in master opts
        ret = config.option(opt_name, omit_all=True)
        assert ret == config.DEFAULTS[opt_name], ret

        # Wildcard match
        ret = config.option(wildcard_opt_name, omit_all=True, wildcard=True)
        assert ret == _wildcard_match(config.DEFAULTS, wildcard_opt_name), ret


# --- Additional tests not found in the execution module tests


@pytest.mark.parametrize("backup", ("", "minion", "master", "both"))
def test_backup_mode(backup):
    res = config.backup_mode(backup)
    assert res == backup or "minion"


@pytest.mark.parametrize(
    "uri,expected",
    (("salt://my/foo.txt", True), ("mysql://foo:bar@foo.bar/baz", False)),
)
def test_valid_fileproto(uri, expected):
    res = config.valid_fileproto(uri)
    assert res is expected


def test_dot_vals():
    extra_master_opt = ("test.option.baah", "value of test.option.baah in master")
    with patch.dict(config.__pillar__, {"master": dict((extra_master_opt,))}):
        res = config.dot_vals("test")
    assert isinstance(res, dict)
    assert res
    for var in ("foo", "bar", "baz"):
        key = f"test.option.{var}"
        assert key in res
        assert res[key] == f"value of test.option.{var} in __opts__"
    assert extra_master_opt[0] in res
    assert res[extra_master_opt[0]] == extra_master_opt[1]
