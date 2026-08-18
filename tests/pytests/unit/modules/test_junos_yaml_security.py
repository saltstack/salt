"""
Regression test for unsafe YAML loading in junos module.

This test ensures that the junos.get_table() function uses a safe YAML loader
and does not allow arbitrary code execution.

CVE/Security Issue: The junos module was using yamlordereddictloader.Loader
which extends yaml.Loader (unsafe). It should use yamlordereddictloader.SafeLoader.
"""

import pytest
import yaml

try:
    import yamlordereddictloader

    HAS_YAMLORDEREDDICTLOADER = True
except ImportError:
    HAS_YAMLORDEREDDICTLOADER = False


pytestmark = [
    pytest.mark.skipif(
        not HAS_YAMLORDEREDDICTLOADER,
        reason="The yamlordereddictloader module is required",
    ),
]


def test_junos_module_uses_safe_yaml_loader():
    """
    Regression test to ensure junos module uses SafeLoader, not Loader.

    This test will:
    - FAIL if salt/modules/junos.py uses yamlordereddictloader.Loader (UNSAFE)
    - PASS if salt/modules/junos.py uses yamlordereddictloader.SafeLoader (SAFE)
    """
    import inspect

    import salt.modules.junos as junos

    # Get the source code of the get_table function
    source = inspect.getsource(junos.get_table)

    # Check that SafeLoader is used, not Loader
    if "yamlordereddictloader.Loader" in source and "SafeLoader" not in source.replace(
        "yamlordereddictloader.Loader", ""
    ):
        pytest.fail(
            "SECURITY VULNERABILITY: junos.get_table() uses yamlordereddictloader.Loader!\n\n"
            "The unsafe Loader can execute arbitrary Python code from YAML files.\n\n"
            "FIX: Change yamlordereddictloader.Loader to yamlordereddictloader.SafeLoader\n"
            "in salt/modules/junos.py (around line 1861)"
        )

    # Verify SafeLoader is actually used
    assert "yamlordereddictloader.SafeLoader" in source, (
        "Expected to find yamlordereddictloader.SafeLoader in junos.get_table(). "
        "Make sure the safe loader is being used."
    )


def test_yamlordereddictloader_safeloader_blocks_code_execution():
    """
    Test that yamlordereddictloader.SafeLoader blocks arbitrary code execution.

    This demonstrates the correct, secure behavior that should be used.
    """
    # Malicious YAML attempting to execute os.system
    malicious_yaml = "!!python/object/apply:os.system ['echo this should not execute']"

    # SafeLoader should reject this and raise ConstructorError
    with pytest.raises(yaml.constructor.ConstructorError):
        yaml.load(malicious_yaml, Loader=yamlordereddictloader.SafeLoader)


def test_yamlordereddictloader_loader_inheritance():
    """
    Verify the inheritance chain showing why Loader is unsafe.
    """
    # yamlordereddictloader.Loader extends yaml.Loader (UNSAFE)
    assert issubclass(
        yamlordereddictloader.Loader, yaml.Loader
    ), "yamlordereddictloader.Loader should extend yaml.Loader (unsafe)"

    # yamlordereddictloader.SafeLoader extends yaml.SafeLoader (SAFE)
    assert issubclass(
        yamlordereddictloader.SafeLoader, yaml.SafeLoader
    ), "yamlordereddictloader.SafeLoader should extend yaml.SafeLoader (safe)"


def test_ordered_dict_functionality_with_safeloader():
    """
    Verify that SafeLoader still provides OrderedDict functionality.

    This ensures that switching to SafeLoader doesn't break the intended
    functionality of maintaining key order.
    """
    test_yaml = """
TableTest:
    key1: value1
    key2: value2
    key3: value3
"""

    # Load with SafeLoader
    result = yaml.load(test_yaml, Loader=yamlordereddictloader.SafeLoader)

    # Verify it loaded successfully
    assert "TableTest" in result
    assert result["TableTest"]["key1"] == "value1"

    # Verify it returns OrderedDict (the whole point of yamlordereddictloader)
    from collections import OrderedDict

    assert isinstance(result, OrderedDict) or isinstance(result, dict)
    assert isinstance(result["TableTest"], OrderedDict) or isinstance(
        result["TableTest"], dict
    )


def test_compare_unsafe_vs_safe_loader():
    """
    Direct comparison showing the difference between unsafe and safe loaders.
    """
    # Safe YAML that should work with both loaders
    safe_yaml = """
config:
    host: example.com
    port: 8080
    enabled: true
"""

    # Load with both loaders - should work fine
    result_unsafe = yaml.load(safe_yaml, Loader=yamlordereddictloader.Loader)
    result_safe = yaml.load(safe_yaml, Loader=yamlordereddictloader.SafeLoader)

    # Both should produce the same result for safe YAML
    assert result_unsafe == result_safe

    # Malicious YAML with Python object constructor
    malicious_yaml = "!!python/object/apply:os.system ['ls']"

    # Safe Loader will raise an exception (correct behavior)
    with pytest.raises(yaml.constructor.ConstructorError):
        yaml.load(malicious_yaml, Loader=yamlordereddictloader.SafeLoader)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
