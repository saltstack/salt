"""
Scenario tests for remote Salt CLI client authentication lifecycle.

These tests simulate real-world workflows for client authentication,
from initial setup through daily operations to revocation.
"""

import pytest

import salt.crypt
import salt.key
import salt.wheel


class TestAdministratorOnboarding:
    """
    Scenario: Administrator setting up remote CLI access.

    Workflow:
    1. Administrator generates client keypair
    2. Administrator registers public key with Salt master
    3. Master administrator accepts the client key
    4. Client authenticates and executes first command
    """

    def test_admin_onboarding_workflow(self, salt_master):
        """Test complete administrator onboarding workflow."""
        # Step 1: Generate client keys (would be done on admin workstation)
        admin_id = "admin-workstation"
        priv_key, pub_key = salt.crypt.gen_keys(4096)

        # Step 2: Register public key (admin would send pub_key to master admin)
        with salt.key.ClientKey(salt_master.config) as ckey:
            ckey.cache.store(
                "client_keys", admin_id, {"pub": pub_key, "state": "pending"}
            )

            # Step 3: Master admin reviews and accepts
            pending_keys = ckey.list_keys()
            assert admin_id in pending_keys["clients_pre"]

            # Accept the key
            result = ckey.accept(admin_id)
            assert admin_id in result["clients"]

            # Verify key is now in accepted state
            all_keys = ckey.list_keys()
            assert admin_id in all_keys["clients"]
            assert admin_id not in all_keys["clients_pre"]

            # Step 4: Client would authenticate and execute commands
            # (Future enhancement: test actual command execution with RemoteClient)

            # Cleanup
            result = ckey.delete_key(admin_id)
            assert admin_id in result["clients"]


class TestMultipleClientsManagement:
    """
    Scenario: Managing multiple client keys for different administrators.

    Workflow:
    1. Multiple administrators request access
    2. Master administrator reviews all pending requests
    3. Accepts trusted administrators
    4. Rejects untrusted requests
    5. Later revokes compromised client
    """

    def test_bulk_client_management(self, salt_master):
        """Test managing multiple client keys."""
        with salt.key.ClientKey(salt_master.config) as ckey:
            # Step 1: Multiple administrators request access
            administrators = {
                "admin-alice": "trusted",
                "admin-bob": "trusted",
                "admin-charlie": "untrusted",
                "admin-dave": "trusted",
            }

            for admin_id in administrators:
                _, pub = salt.crypt.gen_keys(4096)
                ckey.cache.store(
                    "client_keys", admin_id, {"pub": pub, "state": "pending"}
                )

            # Step 2: Master admin reviews pending requests
            pending = ckey.list_keys()
            assert len(pending["clients_pre"]) == 4

            # Step 3: Accept trusted administrators
            trusted = [k for k, v in administrators.items() if v == "trusted"]
            result = ckey.accept(match_dict={"clients_pre": trusted})
            assert len(result["clients"]) == 3
            assert all(admin in result["clients"] for admin in trusted)

            # Step 4: Reject untrusted
            untrusted = [k for k, v in administrators.items() if v == "untrusted"]
            result = ckey.reject(untrusted[0])
            assert untrusted[0] in result["clients_rejected"]

            # Step 5: Later, revoke compromised client (alice's laptop stolen)
            result = ckey.reject("admin-alice", include_accepted=True)
            assert "admin-alice" in result["clients_rejected"]

            # Verify final state
            all_keys = ckey.list_keys()
            assert "admin-bob" in all_keys["clients"]
            assert "admin-dave" in all_keys["clients"]
            assert "admin-alice" in all_keys["clients_rejected"]
            assert "admin-charlie" in all_keys["clients_rejected"]

            # Cleanup
            for admin_id in administrators:
                ckey.delete_key(admin_id)


class TestClientKeyRotation:
    """
    Scenario: Rotating client keys for security.

    Workflow:
    1. Client authenticates with current key
    2. Client generates new keypair
    3. Client registers new public key
    4. Master admin accepts new key
    5. Old key is deleted
    """

    def test_key_rotation_workflow(self, salt_master):
        """Test client key rotation."""
        client_id = "admin-rotation-test"

        with salt.key.ClientKey(salt_master.config) as ckey:
            # Step 1: Client has current key
            _, old_pub = salt.crypt.gen_keys(4096)
            ckey.cache.store(
                "client_keys", client_id, {"pub": old_pub, "state": "accepted"}
            )

            # Verify old key is accepted
            all_keys = ckey.list_keys()
            assert client_id in all_keys["clients"]

            # Get old key fingerprint
            old_fp = ckey.finger(client_id)
            old_fingerprint = old_fp["clients"][client_id]

            # Step 2 & 3: Client generates and registers new key
            _, new_pub = salt.crypt.gen_keys(4096)
            ckey.cache.store(
                "client_keys", client_id, {"pub": new_pub, "state": "accepted"}
            )

            # Verify key was updated
            new_fp = ckey.finger(client_id)
            new_fingerprint = new_fp["clients"][client_id]

            # Fingerprints should be different
            assert old_fingerprint != new_fingerprint

            # Cleanup
            ckey.delete_key(client_id)


class TestEmergencyRevocation:
    """
    Scenario: Emergency revocation of compromised client keys.

    Workflow:
    1. Multiple clients are authenticated
    2. Security incident: laptop stolen
    3. Administrator immediately revokes affected client
    4. Verifies client cannot authenticate (future)
    """

    def test_emergency_revocation(self, salt_master):
        """Test emergency client key revocation."""
        with salt.key.ClientKey(salt_master.config) as ckey:
            # Step 1: Multiple clients authenticated
            clients = ["admin-laptop-1", "admin-laptop-2", "admin-laptop-3"]
            for client_id in clients:
                _, pub = salt.crypt.gen_keys(4096)
                ckey.cache.store(
                    "client_keys", client_id, {"pub": pub, "state": "accepted"}
                )

            # Verify all accepted
            all_keys = ckey.list_keys()
            assert all(c in all_keys["clients"] for c in clients)

            # Step 2 & 3: Laptop stolen - immediate revocation
            compromised = "admin-laptop-2"
            result = ckey.reject(compromised, include_accepted=True)
            assert compromised in result["clients_rejected"]

            # Verify compromised client is rejected
            all_keys = ckey.list_keys()
            assert compromised in all_keys["clients_rejected"]
            assert compromised not in all_keys["clients"]

            # Other clients still accepted
            assert "admin-laptop-1" in all_keys["clients"]
            assert "admin-laptop-3" in all_keys["clients"]

            # Step 4: Future - verify client cannot authenticate
            # (requires full AsyncAuth setup)

            # Cleanup
            for client_id in clients:
                ckey.delete_key(client_id)


class TestClientKeyAudit:
    """
    Scenario: Auditing client keys for security compliance.

    Workflow:
    1. List all client keys
    2. Identify keys by fingerprint
    3. Review key states (accepted/rejected/pending)
    4. Generate audit report
    """

    def test_client_key_audit(self, salt_master):
        """Test client key auditing."""
        with salt.key.ClientKey(salt_master.config) as ckey:
            # Setup: Create clients in various states
            test_clients = {
                "audit-accepted-1": "accepted",
                "audit-accepted-2": "accepted",
                "audit-pending-1": "pending",
                "audit-rejected-1": "rejected",
            }

            for client_id, state in test_clients.items():
                _, pub = salt.crypt.gen_keys(4096)
                ckey.cache.store("client_keys", client_id, {"pub": pub, "state": state})

            # Step 1: List all client keys
            all_keys = ckey.list_keys()

            # Step 2 & 3: Audit each category
            audit_report = {
                "accepted": all_keys["clients"],
                "pending": all_keys["clients_pre"],
                "rejected": all_keys["clients_rejected"],
                "denied": all_keys["clients_denied"],
            }

            # Verify audit findings
            assert len(audit_report["accepted"]) == 2
            assert len(audit_report["pending"]) == 1
            assert len(audit_report["rejected"]) == 1

            # Step 2: Get fingerprints for all accepted clients
            fingerprints = {}
            for client_id in audit_report["accepted"]:
                fp = ckey.finger(client_id)
                fingerprints[client_id] = fp["clients"][client_id]

            assert len(fingerprints) == 2
            assert all(":" in fp for fp in fingerprints.values())

            # Cleanup
            for client_id in test_clients:
                ckey.delete_key(client_id)


class TestWheelModuleIntegration:
    """
    Scenario: Using wheel module for remote client key management.

    Workflow:
    1. Use wheel module to list client keys
    2. Accept client via wheel
    3. Reject client via wheel
    4. Delete client via wheel
    """

    def test_wheel_client_key_management(self, salt_master, wheel_client):
        """Test wheel module client key functions."""
        # Setup: Create pending client
        client_id = "wheel-test-client"
        _, pub = salt.crypt.gen_keys(4096)

        with salt.key.ClientKey(salt_master.config) as ckey:
            ckey.cache.store("client_keys", client_id, {"pub": pub, "state": "pending"})

        # Use wildcard auth (works with auto eauth wildcard config)
        # This approach doesn't require actual user account creation
        auth_creds = {
            "username": "wheel-test-user",
            "password": "test-password",
            "eauth": "auto",
        }

        # Step 1: List via wheel
        result = wheel_client.cmd_sync(
            {"fun": "key.list_all_client", "print_event": False, **auth_creds}
        )
        assert result
        assert "data" in result
        assert result["data"]["success"] is True
        assert result["data"]["user"] == auth_creds["username"]
        assert client_id in result["data"]["return"]["clients_pre"]

        # Step 2: Accept via wheel
        result = wheel_client.cmd_sync(
            {
                "fun": "key.accept_client",
                "match": client_id,
                "print_event": False,
                **auth_creds,
            }
        )
        assert result["data"]["success"] is True
        assert client_id in result["data"]["return"]["clients"]

        # Step 3: Reject via wheel
        result = wheel_client.cmd_sync(
            {
                "fun": "key.reject_client",
                "match": client_id,
                "include_accepted": True,
                "print_event": False,
                **auth_creds,
            }
        )
        assert result["data"]["success"] is True
        assert client_id in result["data"]["return"]["clients_rejected"]

        # Step 4: Delete via wheel
        result = wheel_client.cmd_sync(
            {
                "fun": "key.delete_client",
                "match": client_id,
                "print_event": False,
                **auth_creds,
            }
        )
        assert result["data"]["success"] is True
        assert client_id in result["data"]["return"]["clients_rejected"]

        # Verify deleted
        result = wheel_client.cmd_sync(
            {"fun": "key.list_all_client", "print_event": False, **auth_creds}
        )
        assert result["data"]["success"] is True
        assert client_id not in result["data"]["return"]["clients"]
        assert client_id not in result["data"]["return"]["clients_rejected"]


@pytest.mark.parametrize("num_clients", [1, 5, 10])
def test_bulk_client_operations(salt_master, num_clients):
    """Test performance with varying numbers of clients."""
    with salt.key.ClientKey(salt_master.config) as ckey:
        # Create clients
        clients = []
        for i in range(num_clients):
            client_id = f"bulk-client-{i}"
            _, pub = salt.crypt.gen_keys(4096)
            ckey.cache.store("client_keys", client_id, {"pub": pub, "state": "pending"})
            clients.append(client_id)

        # Accept all at once
        result = ckey.accept("bulk-client-*")
        assert len(result["clients"]) == num_clients

        # Verify all accepted
        all_keys = ckey.list_keys()
        assert len(all_keys["clients"]) >= num_clients

        # Delete all at once
        result = ckey.delete_key("bulk-client-*")
        assert len(result["clients"]) == num_clients

        # Verify all deleted
        all_keys = ckey.list_keys()
        assert all(c not in all_keys["clients"] for c in clients)
