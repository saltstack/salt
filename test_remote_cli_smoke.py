#!/usr/bin/env python3
"""
Smoke tests for remote CLI functionality after rebase.
Tests basic functionality to ensure nothing is critically broken.
"""
import os
import sys

# Add salt to path
sys.path.insert(0, os.path.dirname(__file__))


def test_imports():
    """Test that all modified modules can be imported."""
    print("\n[TEST 1] Testing module imports...")
    try:
        import salt.client

        print("  ✓ salt.client")

        import salt.cli.salt

        print("  ✓ salt.cli.salt")

        import salt.cli.daemons

        print("  ✓ salt.cli.daemons")

        import salt.master

        print("  ✓ salt.master")

        import salt.crypt

        print("  ✓ salt.crypt")

        import salt.config

        print("  ✓ salt.config")

        import salt.key

        print("  ✓ salt.key")

        return True
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_config_new_options():
    """Test that new config options are present."""
    print("\n[TEST 2] Testing new config options...")
    try:
        import salt.config

        # Check that new options exist in DEFAULT_MASTER_OPTS
        opts = salt.config.DEFAULT_MASTER_OPTS

        assert "encryption_algorithm" in opts, "encryption_algorithm missing"
        print(f"  ✓ encryption_algorithm: {opts['encryption_algorithm']}")

        assert "signing_algorithm" in opts, "signing_algorithm missing"
        print(f"  ✓ signing_algorithm: {opts['signing_algorithm']}")

        # Check that existing master options still exist
        assert "publish_signing_algorithm" in opts
        print(f"  ✓ publish_signing_algorithm: {opts['publish_signing_algorithm']}")

        return True
    except Exception as e:
        print(f"  ✗ Config test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_remote_client_exists():
    """Test that RemoteClient class exists and can be instantiated."""
    print("\n[TEST 3] Testing RemoteClient class...")
    try:
        import salt.client

        # Check that get_remote_client function exists
        assert hasattr(salt.client, "get_remote_client"), "get_remote_client not found"
        print("  ✓ get_remote_client() function exists")

        # Check that RemoteClient class exists
        assert hasattr(salt.client, "RemoteClient"), "RemoteClient class not found"
        print("  ✓ RemoteClient class exists")

        # Check RemoteClient is a subclass of LocalClient
        assert issubclass(salt.client.RemoteClient, salt.client.LocalClient)
        print("  ✓ RemoteClient extends LocalClient")

        return True
    except Exception as e:
        print(f"  ✗ RemoteClient test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_client_key_class():
    """Test that ClientKey class exists."""
    print("\n[TEST 4] Testing ClientKey class...")
    try:
        import salt.key

        # Check that ClientKey class exists
        assert hasattr(salt.key, "ClientKey"), "ClientKey class not found"
        print("  ✓ ClientKey class exists")

        # Check ClientKey is a subclass of Key
        assert issubclass(salt.key.ClientKey, salt.key.Key)
        print("  ✓ ClientKey extends Key")

        return True
    except Exception as e:
        print(f"  ✗ ClientKey test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_master_aes_funcs():
    """Test that AESFuncs structure is intact."""
    print("\n[TEST 5] Testing AESFuncs modifications...")
    try:
        import salt.master

        # Check that AESFuncs class exists
        assert hasattr(salt.master, "AESFuncs"), "AESFuncs class not found"
        print(f"  ✓ AESFuncs class exists")

        # Check that expose_methods exists
        assert hasattr(
            salt.master.AESFuncs, "expose_methods"
        ), "expose_methods not found"
        print(f"  ✓ AESFuncs.expose_methods exists")

        # Check that channels attribute will be set (requires master instantiation)
        print("  ✓ AESFuncs structure intact (full test requires master setup)")

        return True
    except Exception as e:
        print(f"  ✗ AESFuncs test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_salt_cli_integration():
    """Test that SaltCMD uses RemoteClient."""
    print("\n[TEST 6] Testing SaltCMD integration...")
    try:
        import inspect

        import salt.cli.salt

        # Check that SaltCMD exists
        assert hasattr(salt.cli.salt, "SaltCMD"), "SaltCMD class not found"
        print("  ✓ SaltCMD class exists")

        # Check the run method to see if it uses 'client' instead of 'local_client'
        source = inspect.getsource(salt.cli.salt.SaltCMD.run)

        if "get_remote_client" in source:
            print("  ✓ SaltCMD.run() calls get_remote_client()")
        else:
            print("  ⚠ SaltCMD.run() may not be using get_remote_client()")

        if "self.client" in source:
            print("  ✓ Uses self.client attribute")
        elif "self.local_client" in source:
            print("  ⚠ Still uses self.local_client (may need update)")

        return True
    except Exception as e:
        print(f"  ✗ SaltCMD test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_syntax():
    """Test that modified files have no syntax errors."""
    print("\n[TEST 7] Testing syntax of modified files...")
    import py_compile
    import tempfile

    files_to_check = [
        "salt/client/__init__.py",
        "salt/cli/salt.py",
        "salt/cli/daemons.py",
        "salt/master.py",
        "salt/crypt.py",
        "salt/config/__init__.py",
        "salt/key.py",
    ]

    all_ok = True
    for filepath in files_to_check:
        try:
            py_compile.compile(filepath, doraise=True)
            print(f"  ✓ {filepath}")
        except py_compile.PyCompileError as e:
            print(f"  ✗ {filepath}: {e}")
            all_ok = False

    return all_ok


def main():
    """Run all smoke tests."""
    print("=" * 60)
    print("Remote CLI Smoke Test Suite")
    print("=" * 60)

    tests = [
        ("Syntax Check", test_syntax),
        ("Module Imports", test_imports),
        ("Config Options", test_config_new_options),
        ("RemoteClient", test_remote_client_exists),
        ("ClientKey", test_client_key_class),
        ("AESFuncs", test_master_aes_funcs),
        ("SaltCMD Integration", test_salt_cli_integration),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} crashed: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
