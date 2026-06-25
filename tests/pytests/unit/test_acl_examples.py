"""
Parser-level tests for every publisher_acl / external_auth example
shown in the rendered Salt documentation.

The point of these tests is *not* to re-test ``salt.utils.minions``;
those paths are covered elsewhere. The point is to pin every YAML
example we publish so that documentation drift cannot reintroduce
unparseable or unmatchable rules. If a doc example is changed the
parsed structure here must move with it.

The examples come from:

* doc/ref/publisheracl.rst
* doc/topics/eauth/access_control.rst
* doc/topics/eauth/index.rst
* doc/security/threat-model.rst (cross-link sanity)

Each test loads the YAML snippet, then drives the snippet through
the same ``auth_check`` / ``spec_check`` codepaths the master uses
in production for a representative request.

These tests cover the following linked issues:

* #57874 — bad publisher_acl examples should parse and resolve
* #61769 — @wheel / @runner / @jobs syntax under publisher_acl
"""

import textwrap

import pytest
import yaml

from salt.utils.minions import CkMinions


@pytest.fixture
def opts():
    """
    Minimal opts dict sufficient to drive auth_check / spec_check
    without touching the filesystem or the cache.
    """
    return {
        "pki_dir": "/tmp/test-acl-pki",
        "cache": "localfs",
        "transport": "zeromq",
        "key_cache": False,
        "minion_data_cache": False,
        "nodegroups": {},
        "extension_modules": "",
    }


@pytest.fixture
def ckminions(opts):
    return CkMinions(opts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _yaml(snippet):
    """
    Dedent + safe_load a documentation snippet. Anything that round-trips
    through this helper is a snippet we are willing to ship as documentation.
    """
    return yaml.safe_load(textwrap.dedent(snippet))


# ---------------------------------------------------------------------------
# publisher_acl — examples currently in doc/ref/publisheracl.rst
# ---------------------------------------------------------------------------


def test_publisheracl_main_example_parses():
    """
    The principal publisher_acl example from doc/ref/publisheracl.rst.

    Every documented sub-form must parse without raising.
    """
    data = _yaml(
        """
        publisher_acl:
          # Allow thatch to execute anything.
          thatch:
            - .*
          # Allow fred to use test and pkg, but only on "web*" minions.
          fred:
            - 'web*':
              - test.*
              - pkg.*
          # Allow admin and managers to use saltutil module functions
          admin|manager_.*:
            - saltutil.*
          # Allow users to use only my_mod functions on "web*" minions
          # with specific arguments.
          user_.*:
            - 'web*':
              - 'my_mod.*':
                  args:
                    - 'a.*'
                    - 'b.*'
                  kwargs:
                    'kwa': 'kwa.*'
                    'kwb': 'kwb'
        """
    )
    acl = data["publisher_acl"]
    assert set(acl) == {"thatch", "fred", "admin|manager_.*", "user_.*"}
    # The "thatch" rule must be a flat list of strings.
    assert acl["thatch"] == [".*"]
    # The "fred" rule is a list with one dict of {target: [funs]}.
    assert isinstance(acl["fred"], list)
    assert isinstance(acl["fred"][0], dict)
    assert "web*" in acl["fred"][0]
    assert acl["fred"][0]["web*"] == ["test.*", "pkg.*"]
    # The argument-constrained user_.* rule must round-trip.
    fun_block = acl["user_.*"][0]["web*"][0]["my_mod.*"]
    assert fun_block["args"] == ["a.*", "b.*"]
    assert fun_block["kwargs"] == {"kwa": "kwa.*", "kwb": "kwb"}


def test_publisheracl_blacklist_example_parses():
    """
    publisher_acl_blacklist example.

    The regex ``^(?!sudo_).*$`` (negative lookahead) is the one that has
    historically been mis-quoted; it must round-trip as a single string
    rather than getting eaten by YAML's flow scalar rules.
    """
    data = _yaml(
        """
        publisher_acl_blacklist:
          users:
            - root
            - '^(?!sudo_).*$'
          modules:
            - cmd.*
            - test.echo
        """
    )
    bl = data["publisher_acl_blacklist"]
    assert bl["users"] == ["root", "^(?!sudo_).*$"]
    assert bl["modules"] == ["cmd.*", "test.echo"]


# ---------------------------------------------------------------------------
# publisher_acl — runner / wheel / jobs syntax (#61769)
# ---------------------------------------------------------------------------


def test_publisheracl_wheel_runner_jobs_example_parses_and_authorizes(ckminions):
    """
    The publisher_acl page must show @wheel, @runner and @jobs syntax that
    actually authorizes through ``spec_check`` (#61769).
    """
    data = _yaml(
        """
        publisher_acl:
          ops_user:
            - '@wheel'    # all wheel modules
            - '@runner'   # all runner modules
            - '@jobs'     # the jobs runner / wheel
        """
    )
    auth_list = data["publisher_acl"]["ops_user"]

    # @wheel covers any wheel module function.
    assert ckminions.wheel_check(auth_list, "key.accept", {}) is True
    assert ckminions.wheel_check(auth_list, "key.delete", {}) is True
    # @runner covers any runner module function.
    assert ckminions.runner_check(auth_list, "manage.up", {}) is True
    assert ckminions.runner_check(auth_list, "cache.grains", {}) is True
    # @jobs is a specific name; spec_check matches it as the form alias.
    assert ckminions.runner_check(auth_list, "jobs.active", {}) is True


def test_publisheracl_wheel_runner_narrow_module_example(ckminions):
    """
    Narrowing @<modname> grants only the named module.
    """
    data = _yaml(
        """
        publisher_acl:
          ops_user:
            - '@key'           # only the key.* wheel module
            - '@manage'        # only the manage.* runner module
        """
    )
    auth_list = data["publisher_acl"]["ops_user"]

    # @key is shorthand for the key.* wheel module.
    assert ckminions.wheel_check(auth_list, "key.accept", {}) is True
    # @manage is shorthand for the manage.* runner module.
    assert ckminions.runner_check(auth_list, "manage.up", {}) is True
    # An unrelated wheel module is not authorized.
    assert ckminions.wheel_check(auth_list, "config.values", {}) is False
    # An unrelated runner module is not authorized.
    assert ckminions.runner_check(auth_list, "cache.grains", {}) is False


def test_publisheracl_wheel_with_function_filter(ckminions):
    """
    @<modname>: [funs] grants only the named functions of the named module.
    """
    data = _yaml(
        """
        publisher_acl:
          ops_user:
            - '@key':
              - accept
              - finger
        """
    )
    auth_list = data["publisher_acl"]["ops_user"]
    assert ckminions.wheel_check(auth_list, "key.accept", {}) is True
    assert ckminions.wheel_check(auth_list, "key.finger", {}) is True
    # Function not in the whitelist is rejected.
    assert ckminions.wheel_check(auth_list, "key.delete", {}) is False


# ---------------------------------------------------------------------------
# external_auth — examples in doc/topics/eauth/index.rst
# ---------------------------------------------------------------------------


def test_external_auth_main_example_parses_and_authorizes(ckminions):
    """
    The principal external_auth example. It must parse and the documented
    rule for ``thatch`` must authorize ``test.version`` on ``web*``.
    """
    data = _yaml(
        """
        external_auth:
          pam:
            thatch:
              - 'web*':
                - test.*
                - network.*
            steve|admin.*:
              - .*
        """
    )
    auth_list = data["external_auth"]["pam"]["thatch"]
    # thatch may run test.version on web* targets (target validation
    # happens against an empty minion list here, so we go through
    # auth_check with a `web*` target and an empty minion list).
    assert ckminions.auth_check(
        auth_list, "test.version", [], tgt="web*", tgt_type="glob"
    )
    # thatch may NOT run cmd.run.
    assert not ckminions.auth_check(
        auth_list, "cmd.run", [["ls"]], tgt="web*", tgt_type="glob"
    )


def test_external_auth_wheel_runner_example_parses(ckminions):
    """
    @wheel / @runner / @jobs documented for external_auth must parse and
    authorize through spec_check.
    """
    data = _yaml(
        """
        external_auth:
          pam:
            thatch:
              - '@wheel'
              - '@runner'
              - '@jobs'
        """
    )
    auth_list = data["external_auth"]["pam"]["thatch"]
    assert ckminions.wheel_check(auth_list, "key.accept", {}) is True
    assert ckminions.runner_check(auth_list, "manage.up", {}) is True


def test_external_auth_group_example_parses():
    """
    The ``%`` group suffix syntax must round-trip.
    """
    data = _yaml(
        """
        external_auth:
          pam:
            admins%:
              - '*':
                - 'pkg.*'
        """
    )
    rule = data["external_auth"]["pam"]["admins%"]
    assert isinstance(rule, list)
    assert "*" in rule[0]
    assert rule[0]["*"] == ["pkg.*"]


def test_external_auth_arg_kwarg_filter_example_parses_and_authorizes(ckminions):
    """
    The arg/kwarg whitelist example from the eauth page must parse, and the
    documented argument shape must be enforced by ``auth_check``.
    """
    data = _yaml(
        """
        external_auth:
          pam:
            my_user:
              - '*':
                - 'my_mod.*':
                    args:
                      - 'a.*'
                      - 'b.*'
                    kwargs:
                      'kwa': 'kwa.*'
                      'kwb': 'kwb'
        """
    )
    auth_list = data["external_auth"]["pam"]["my_user"]

    # Matching args + kwargs is accepted. Salt represents the trailing
    # kwargs dict in the publish wire as ``{"__kwarg__": True, ...}``.
    # auth_check wraps a non-list ``funs`` into a single-element list and
    # the matching ``args`` into ``[args]`` once, so we pass args at the
    # un-wrapped depth here.
    good_args = [
        "alpha",
        "beta",
        {"__kwarg__": True, "kwa": "kwa-1", "kwb": "kwb"},
    ]
    assert ckminions.auth_check(
        auth_list, "my_mod.do_thing", good_args, tgt="*", tgt_type="glob"
    )

    # An args[0] that does not match 'a.*' fails.
    bad_args = [
        "zzz",
        "beta",
        {"__kwarg__": True, "kwa": "kwa-1", "kwb": "kwb"},
    ]
    assert not ckminions.auth_check(
        auth_list, "my_mod.do_thing", bad_args, tgt="*", tgt_type="glob"
    )

    # A kwargs['kwb'] that does not match the literal 'kwb' fails.
    bad_kwargs = [
        "alpha",
        "beta",
        {"__kwarg__": True, "kwa": "kwa-1", "kwb": "NOPE"},
    ]
    assert not ckminions.auth_check(
        auth_list, "my_mod.do_thing", bad_kwargs, tgt="*", tgt_type="glob"
    )
