#!/usr/bin/env python3
"""
Test script to verify Client ACL publish implementation.
This tests the ClientACL class and its publish authorization logic.
"""

import os
import sys

# Add salt to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

import salt.acl


def test_client_acl_basic():
    """Test basic ClientACL functionality for publish."""
    print("Test 1: Basic ClientACL initialization")

    # Test with no ACL configured (backward compatible)
    acl = salt.acl.ClientACL({})
    assert acl.client_acl == {}
    print("  ✓ Empty ACL initializes correctly")

    # Test with ACL configured
    config = {
        "admin-client": {
            "runner": ["*"],
            "wheel": ["*"],
            "minions": ["*"],
            "modules": ["*"],
        },
        "restricted-client": {
            "runner": ["jobs.*"],
            "wheel": [],
            "minions": ["web-*", "db-*"],
            "modules": ["test.ping", "grains.items"],
        },
    }
    acl = salt.acl.ClientACL(config)
    assert acl.client_acl == config
    print("  ✓ ACL with configuration initializes correctly")


def test_client_can_publish():
    """Test the client_can_publish method."""
    print("\nTest 2: client_can_publish() method")

    config = {
        "admin-client": {
            "minions": ["*"],
            "modules": ["*"],
        },
        "web-client": {
            "minions": ["web-*"],
            "modules": ["test.*", "service.restart"],
        },
    }
    acl = salt.acl.ClientACL(config)

    # Test admin client (should allow all)
    result = acl.client_can_publish(
        "admin-client", ["web-01", "db-01", "app-01"], "state.apply"
    )
    assert result["allowed"] is True
    assert result["error"] is None
    print("  ✓ Admin client can publish to all minions with any module")

    # Test web client with allowed minions and module
    result = acl.client_can_publish("web-client", ["web-01", "web-02"], "test.ping")
    assert result["allowed"] is True
    assert result["error"] is None
    print("  ✓ Web client can publish to web-* minions with test.* modules")

    # Test web client with disallowed minions
    result = acl.client_can_publish("web-client", ["db-01"], "test.ping")
    assert result["allowed"] is False
    assert "not authorized to target" in result["error"]["message"]
    print("  ✓ Web client cannot publish to non-web minions")

    # Test web client with disallowed module
    result = acl.client_can_publish("web-client", ["web-01"], "state.apply")
    assert result["allowed"] is False
    assert "not authorized to execute" in result["error"]["message"]
    print("  ✓ Web client cannot execute disallowed modules")

    # Test unknown client
    result = acl.client_can_publish("unknown-client", ["web-01"], "test.ping")
    assert result["allowed"] is False
    assert "No client_acl configuration" in result["error"]["message"]
    print("  ✓ Unknown client is denied")


def test_client_can_target_minions():
    """Test the client_can_target_minions method."""
    print("\nTest 3: client_can_target_minions() method")

    config = {
        "web-client": {
            "minions": ["web-*"],
            "modules": ["*"],
        },
    }
    acl = salt.acl.ClientACL(config)

    # Test allowed minions
    allowed, denied = acl.client_can_target_minions(
        "web-client", ["web-01", "web-02", "web-03"]
    )
    assert allowed is True
    assert denied == []
    print("  ✓ Returns True for all allowed minions")

    # Test mixed minions
    allowed, denied = acl.client_can_target_minions(
        "web-client", ["web-01", "db-01", "web-02"]
    )
    assert allowed is False
    assert "db-01" in denied
    print("  ✓ Returns False and lists denied minions for mixed list")


def test_backward_compatibility():
    """Test backward compatibility with no ACL configured."""
    print("\nTest 4: Backward compatibility (no ACL configured)")

    # No ACL configured - should allow everything
    acl = salt.acl.ClientACL({})

    result = acl.client_can_publish("any-client", ["any-minion"], "any.function")
    assert result["allowed"] is True
    assert result["error"] is None
    print("  ✓ No ACL configured allows all operations")


def test_key_name_variants():
    """Test support for different key name variants."""
    print("\nTest 5: Key name variants (minions vs minion, modules vs minion_function)")

    # Test "minion" instead of "minions"
    config = {
        "client1": {
            "minion": ["web-*"],  # Old style
            "minion_function": ["test.*"],  # Old style
        },
    }
    acl = salt.acl.ClientACL(config)

    # Should work with old-style keys
    assert acl.client_can_target_minion("client1", "web-01") is True
    assert acl.client_can_target_minion("client1", "db-01") is False
    print("  ✓ Old-style 'minion' key works")

    assert acl.client_can_run_minion_function("client1", "test.ping") is True
    assert acl.client_can_run_minion_function("client1", "state.apply") is False
    print("  ✓ Old-style 'minion_function' key works")

    # Test new style
    config = {
        "client2": {
            "minions": ["web-*"],  # New style
            "modules": ["test.*"],  # New style
        },
    }
    acl = salt.acl.ClientACL(config)

    assert acl.client_can_target_minion("client2", "web-01") is True
    assert acl.client_can_run_minion_function("client2", "test.ping") is True
    print("  ✓ New-style 'minions' and 'modules' keys work")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Client ACL Publish Implementation Tests")
    print("=" * 60)

    try:
        test_client_acl_basic()
        test_client_can_publish()
        test_client_can_target_minions()
        test_backward_compatibility()
        test_key_name_variants()

        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
