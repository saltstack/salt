"""
Tests that the Thorium SLS examples shipped in
``doc/topics/thorium/index.rst`` parse as YAML and reference Thorium
module functions that actually exist.

These tests pin the docs against the code so a future drift causes a
loud failure rather than silent stale documentation. Issue addressed:
:issue:`61921`.
"""

import inspect

import pytest

import salt.utils.yaml
from salt.thorium import calc, check, file, reg, runner

# The exact SLS payloads documented in
# doc/topics/thorium/index.rst under "Worked Examples".
EXAMPLE_LOAD_SPIKE = """
load_avg:
  reg.mean:
    - add: 1m
    - match: salt/beacon/*/load
  check.gt:
    - value: 4.0

notify_high_load:
  local.cmd:
    - tgt: monitoring-host
    - func: cmd.run
    - arg:
      - 'logger -t salt-thorium "load spike: $(date -Is)"'
    - require:
      - check: load_avg
"""

EXAMPLE_FLAP_DETECTION = """
salt/beacon/*/service/nginx:
  check.event: []

nginx_history:
  reg.list:
    - add: _stamp
    - match: salt/beacon/*/service/nginx
    - stamp: true
    - prune: 20

page_oncall:
  local.cmd:
    - tgt: pager.example.com
    - func: cmd.run
    - arg:
      - 'oncall-page nginx-flap'
    - require:
      - check: salt/beacon/*/service/nginx
      - reg: nginx_history
"""

EXAMPLE_RUNNER_TRIGGER = """
cert/expiring:
  check.event: []

regen_cert:
  runner.cmd:
    - func: state.orchestrate
    - arg:
      - orch.regen_cert
    - require:
      - check: cert/expiring
"""

# Modules whose names appear as the top-level state types in Thorium
# SLS. ``local`` is the wrapper module that publishes to minions; it is
# loaded by Salt's master runtime, so we don't import it here -- a
# string-name lookup is enough to confirm the docs reference it as a
# module name the Thorium loader recognises.
THORIUM_MODULES = {
    "reg": reg,
    "check": check,
    "calc": calc,
    "file": file,
    "runner": runner,
}

# ``local.cmd`` and ``local.state.apply`` are master-side wrappers. The
# docs reference them; they live in ``salt/thorium/local.py``.
THORIUM_WRAPPER_MODULES = {"local"}


def _module_has_function(mod, func_name):
    """
    Thorium state modules sometimes alias function names via
    ``__func_alias__`` (e.g. ``set_`` -> ``set``, ``list_`` -> ``list``).
    Honour those aliases the same way the loader does.
    """
    aliases = getattr(mod, "__func_alias__", {})
    # Reverse: documented name -> actual python name.
    reverse_aliases = {v: k for k, v in aliases.items()}
    candidate = reverse_aliases.get(func_name, func_name)
    return inspect.isfunction(getattr(mod, candidate, None))


@pytest.mark.parametrize(
    "sls_text,name",
    [
        (EXAMPLE_LOAD_SPIKE, "load-spike"),
        (EXAMPLE_FLAP_DETECTION, "flap-detection"),
        (EXAMPLE_RUNNER_TRIGGER, "runner-trigger"),
    ],
)
def test_documented_thorium_example_parses(sls_text, name):
    """
    Each documented Thorium example must be parseable YAML.
    """
    parsed = salt.utils.yaml.safe_load(sls_text)
    assert isinstance(parsed, dict), f"{name}: parsed SLS is not a dict"
    assert parsed, f"{name}: parsed SLS is empty"


@pytest.mark.parametrize(
    "sls_text,name",
    [
        (EXAMPLE_LOAD_SPIKE, "load-spike"),
        (EXAMPLE_FLAP_DETECTION, "flap-detection"),
        (EXAMPLE_RUNNER_TRIGGER, "runner-trigger"),
    ],
)
def test_documented_thorium_example_module_functions_exist(sls_text, name):
    """
    For every ``<module>.<function>`` key under each SLS ID, the
    referenced Thorium module must be importable and the function
    callable.
    """
    parsed = salt.utils.yaml.safe_load(sls_text)
    seen = []

    for sls_id, body in parsed.items():
        assert isinstance(
            body, dict
        ), f"{name}/{sls_id}: state body must be a dict, got {type(body).__name__}"
        for state_key in body:
            # state_key is e.g. "reg.mean", "check.gt", "local.cmd".
            assert (
                "." in state_key
            ), f"{name}/{sls_id}: state key {state_key!r} missing dotted form"
            module_name, _, func_name = state_key.partition(".")
            seen.append((sls_id, module_name, func_name))

            if module_name in THORIUM_WRAPPER_MODULES:
                # Wrapper modules (``local``, etc.) are loaded by the
                # Thorium runtime rather than directly importable here.
                # Their string presence is enough.
                continue

            assert module_name in THORIUM_MODULES, (
                f"{name}/{sls_id}: thorium module {module_name!r} not "
                f"recognised (known: {sorted(THORIUM_MODULES)})"
            )
            mod = THORIUM_MODULES[module_name]
            assert _module_has_function(mod, func_name), (
                f"{name}/{sls_id}: {module_name}.{func_name} not found "
                f"in salt.thorium.{module_name}"
            )

    assert seen, f"{name}: no module.function references found"
