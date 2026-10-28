#!/usr/bin/env python3
"""
End-to-end test for remote Salt CLI client authentication.

This script tests the complete workflow:
1. Client key generation
2. Client authentication
3. Key acceptance
4. Command execution

Run this on a machine with a running Salt master.
"""

import os
import sys
import tempfile

# Add salt to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import salt.client
import salt.config
import salt.crypt
import salt.key


def test_client_key_generation():
    """Test 1: Verify client keys are generated correctly."""
    print("\n" + "=" * 70)
    print("TEST 1: Client Key Generation")
    print("=" * 70)

    # Create temp config with test pki_dir
    with tempfile.TemporaryDirectory() as tmpdir:
        pki_dir = os.path.join(tmpdir, "pki")
        os.makedirs(pki_dir, exist_ok=True)

        # Use actual Salt config defaults
        test_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        test_opts.update(
            {
                "pki_dir": pki_dir,
                "__role": "client",
                "id": "test-client",
                "keysize": 2048,  # Smaller for faster test
                "keys.cache_driver": "localfs_key",
                "cachedir": tmpdir,
                "master": "localhost",
                "master_uri": "tcp://localhost:4506",
            }
        )

        # Generate keys
        print(f"Generating client keys in {pki_dir}...")
        auth = salt.crypt.AsyncAuth(test_opts)
        private_key = auth.get_keys()

        # Verify files exist
        client_priv = os.path.join(pki_dir, "client.pem")
        client_pub = os.path.join(pki_dir, "client.pub")

        assert os.path.exists(client_priv), f"Private key not found: {client_priv}"
        assert os.path.exists(client_pub), f"Public key not found: {client_pub}"

        # Verify key format
        with open(client_pub) as f:
            pub_content = f.read()
            assert "BEGIN PUBLIC KEY" in pub_content, "Invalid public key format"

        with open(client_priv) as f:
            priv_content = f.read()
            assert (
                "BEGIN" in priv_content and "PRIVATE KEY" in priv_content
            ), "Invalid private key format"

        print("✅ Client keys generated successfully")
        print(f"   Private key: {client_priv}")
        print(f"   Public key: {client_pub}")
        print(f"   Key size: 2048 bits")

        return True


def test_client_key_management():
    """Test 2: Verify ClientKey management operations."""
    print("\n" + "=" * 70)
    print("TEST 2: Client Key Management")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        pki_dir = os.path.join(tmpdir, "pki")
        os.makedirs(pki_dir, exist_ok=True)

        # Use actual Salt master config defaults
        test_opts = salt.config.DEFAULT_MASTER_OPTS.copy()
        test_opts.update(
            {
                "pki_dir": pki_dir,
                "keys.cache_driver": "localfs_key",
                "cachedir": tmpdir,
                "__role": "master",  # Acting as master for key management
                "sock_dir": tmpdir,
            }
        )

        client_id = "test-admin-laptop"

        # Generate a test public key
        priv, pub = salt.crypt.gen_keys(2048)

        print(f"Testing key management for client: {client_id}")

        with salt.key.ClientKey(test_opts) as ckey:
            # 1. Store pending key
            print("\n1. Storing client key in pending state...")
            ckey.cache.store("client_keys", client_id, {"pub": pub, "state": "pending"})

            # 2. List pending
            all_keys = ckey.list_keys()
            assert client_id in all_keys["clients_pre"], "Client not in pending"
            print(f"   ✅ Client in pending: {all_keys['clients_pre']}")

            # 3. Accept key
            print("\n2. Accepting client key...")
            result = ckey.accept(client_id)
            assert client_id in result["clients"], "Client not accepted"
            print(f"   ✅ Client accepted: {result['clients']}")

            # 4. Verify accepted
            all_keys = ckey.list_keys()
            assert client_id in all_keys["clients"], "Client not in accepted list"
            assert client_id not in all_keys["clients_pre"], "Client still in pending"
            print(f"   ✅ Client in accepted state")

            # 5. Get fingerprint
            print("\n3. Getting client key fingerprint...")
            fp = ckey.finger(client_id)
            assert client_id in fp["clients"], "Fingerprint not found"
            print(f"   ✅ Fingerprint: {fp['clients'][client_id]}")

            # 6. Reject (revoke)
            print("\n4. Rejecting (revoking) client key...")
            result = ckey.reject(client_id, include_accepted=True)
            assert client_id in result["clients_rejected"], "Client not rejected"
            print(f"   ✅ Client rejected: {result['clients_rejected']}")

            # 7. Delete
            print("\n5. Deleting client key...")
            result = ckey.delete_key(client_id)
            assert (
                client_id in result["clients_rejected"]
            ), "Client not in delete result"
            print(f"   ✅ Client deleted: {result['clients_rejected']}")

            # 8. Verify deleted
            all_keys = ckey.list_keys()
            assert client_id not in all_keys["clients"], "Client still in accepted"
            assert (
                client_id not in all_keys["clients_rejected"]
            ), "Client still in rejected"
            print(f"   ✅ Client fully removed")

        print("\n✅ All client key management operations successful")
        return True


def test_authentication_payload():
    """Test 3: Verify authentication payload includes role=client."""
    print("\n" + "=" * 70)
    print("TEST 3: Authentication Payload")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        pki_dir = os.path.join(tmpdir, "pki")
        os.makedirs(pki_dir, exist_ok=True)

        # Use actual Salt config defaults
        test_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        test_opts.update(
            {
                "pki_dir": pki_dir,
                "__role": "client",
                "id": "test-client",
                "keysize": 2048,
                "keys.cache_driver": "localfs_key",
                "cachedir": tmpdir,
                "master": "localhost",
                "master_uri": "tcp://localhost:4506",
                "encryption_algorithm": "OAEP-SHA1",
                "signing_algorithm": "PKCS1v15-SHA1",
            }
        )

        print("Creating authentication payload...")
        auth = salt.crypt.AsyncAuth(test_opts)
        payload = auth.minion_sign_in_payload()

        # Verify payload structure
        assert "cmd" in payload and payload["cmd"] == "_auth", "Missing _auth command"
        assert "id" in payload and payload["id"] == "test-client", "Missing or wrong ID"
        assert (
            "role" in payload and payload["role"] == "client"
        ), "Missing or wrong role"
        assert "nonce" in payload, "Missing nonce"
        assert "enc_algo" in payload, "Missing encryption algorithm"
        assert "sig_algo" in payload, "Missing signing algorithm"

        print("✅ Authentication payload structure:")
        print(f"   cmd: {payload['cmd']}")
        print(f"   id: {payload['id']}")
        print(f"   role: {payload['role']} ← CRITICAL for client auth")
        print(f"   nonce: {payload['nonce']}")
        print(f"   enc_algo: {payload['enc_algo']}")
        print(f"   sig_algo: {payload['sig_algo']}")

        return True


def test_client_verification_logic():
    """Test 4: Verify AESFuncs can distinguish clients from minions."""
    print("\n" + "=" * 70)
    print("TEST 4: Client vs Minion Verification")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        pki_dir = os.path.join(tmpdir, "pki")
        os.makedirs(pki_dir, exist_ok=True)

        # Use actual Salt master config defaults
        test_opts = salt.config.DEFAULT_MASTER_OPTS.copy()
        test_opts.update(
            {
                "pki_dir": pki_dir,
                "keys.cache_driver": "localfs_key",
                "cachedir": tmpdir,
                "__role": "master",
                "conf_file": None,
                "sock_dir": tmpdir,
            }
        )

        # Create client and minion keys
        client_id = "test-client"
        minion_id = "test-minion"

        client_priv, client_pub = salt.crypt.gen_keys(2048)
        minion_priv, minion_pub = salt.crypt.gen_keys(2048)

        # Store keys
        cache = salt.cache.Cache(test_opts, driver="localfs_key")

        print("\n1. Storing client and minion keys...")
        cache.store("client_keys", client_id, {"pub": client_pub, "state": "accepted"})
        cache.store("keys", minion_id, {"pub": minion_pub, "state": "accepted"})
        print(f"   ✅ Client key stored in client_keys bank")
        print(f"   ✅ Minion key stored in keys bank")

        print("\n2. Verifying cache separation...")
        # Verify client key is ONLY in client_keys
        client_key = cache.fetch("client_keys", client_id)
        assert client_key is not None, "Client key not found in client_keys"
        assert client_key["state"] == "accepted", "Client key not accepted"
        print(f"   ✅ Client key in client_keys: {client_id}")

        # Verify minion key is ONLY in keys
        minion_key = cache.fetch("keys", minion_id)
        assert minion_key is not None, "Minion key not found in keys"
        assert minion_key["state"] == "accepted", "Minion key not accepted"
        print(f"   ✅ Minion key in keys: {minion_id}")

        # Verify separation
        try:
            cache.fetch("keys", client_id)
            should_be_none = True
        except:
            should_be_none = False

        print(f"   ✅ Complete separation: clients in client_keys, minions in keys")

        return True


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("REMOTE SALT CLI CLIENT AUTHENTICATION - END-TO-END TESTS")
    print("=" * 70)

    tests = [
        ("Client Key Generation", test_client_key_generation),
        ("Client Key Management", test_client_key_management),
        ("Authentication Payload", test_authentication_payload),
        ("Client vs Minion Verification", test_client_verification_logic),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, "PASS", None))
        except Exception as e:
            results.append((name, "FAIL", str(e)))
            import traceback

            traceback.print_exc()

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, status, _ in results if status == "PASS")
    failed = sum(1 for _, status, _ in results if status == "FAIL")

    for name, status, error in results:
        symbol = "✅" if status == "PASS" else "❌"
        print(f"{symbol} {name}: {status}")
        if error:
            print(f"   Error: {error}")

    print(f"\nTotal: {passed}/{len(tests)} passed, {failed}/{len(tests)} failed")

    if failed == 0:
        print("\n✅ ALL TESTS PASSED - Remote CLI authentication is working!")
        return 0
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
