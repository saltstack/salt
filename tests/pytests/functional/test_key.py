import pytest

import salt.crypt
import salt.key
import salt.utils.crypt
from tests.support.pytest.database import *  # pylint: disable=wildcard-import,unused-wildcard-import

sqlalchemy = pytest.importorskip("sqlalchemy")

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.parametrize(
        "database_backend",
        available_databases(
            [
                ("mysql-server", "8.0"),
                ("postgresql", "17"),
                ("sqlite", None),
                ("no_database", None),
            ]
        ),
        indirect=True,
    ),
]


@pytest.fixture
def base_key(master_opts, database_backend):
    """Create a base CkMinions instance without any data"""
    return salt.key.get_key(master_opts)


@pytest.fixture(scope="function")
def key(base_key):
    """
    Factory fixture that returns a function to create and configure key instances
    with test-specific data.
    """
    # Track minion IDs and their banks for cleanup
    created_data = []  # List of (minion_id, bank) tuples

    def setup_minion_data(data_dict=None, bank="grains"):
        """
        Create test data in the cache

        Args:
            data_dict: Dictionary with minion_id -> data mapping; data is key state
            bank: The cache bank to store data in ("grains" or "pillar")
                  Note: For pillar_pcre targeting, data must be in the "pillar" bank

        Returns:
            The configured Key instance

        Note on key matching methods:
            - list_match: Takes exact keys or comma-separated keys. Does NOT support glob patterns.
            - glob_match: Supports glob pattern matching (e.g., "web-*").
        """
        base_key.cache.flush("denied_keys")
        base_key.cache.flush("keys")

        if not data_dict:
            return base_key

        for minion_id, data in data_dict.items():
            created_data.append((minion_id, bank))
            if "pub" not in data:
                data["pub"] = salt.crypt.gen_keys(2048)[1]
            # Add key to cache (required for data to be found)
            base_key.cache.store("keys", minion_id, data)

        return base_key

    # Return the setup function
    yield setup_minion_data

    # Cleanup after all tests using this fixture
    base_key.cache.flush("denied_keys")
    base_key.cache.flush("keys")


def test_list_match_simple(key):
    """Test a simple grains match with one level"""
    minion_data = {"minion1": {"state": "accepted"}}
    k = key(minion_data)
    result = k.list_match("minion1")
    assert "minion1" in result["minions"]
    assert len(result["minions"]) == 1


def test_list_match_multiple(key):
    """Test matching multiple keys with comma-separated values"""
    minion_data = {
        "minion1": {"state": "accepted"},
        "minion2": {"state": "accepted"},
        "web-minion-1": {"state": "accepted"},
    }
    k = key(minion_data)

    # Test comma-separated matching (not glob - list_match does exact matching with comma separation)
    result = k.list_match("minion1,minion2")
    assert "minion1" in result["minions"]
    assert "minion2" in result["minions"]
    assert len(result["minions"]) == 2


def test_list_match_different_states(key):
    """Test matching keys in different states"""
    minion_data = {
        "minion1": {"state": "accepted"},
        "minion2": {"state": "pending"},
        "minion3": {"state": "rejected"},
    }
    k = key(minion_data)

    # Check specific states
    result = k.list_match("minion1")
    assert "minion1" in result["minions"]
    assert "minions_pre" not in result
    assert "minions_rejected" not in result

    result = k.list_match("minion2")
    assert "minion2" in result["minions_pre"]

    result = k.list_match("minion3")
    assert "minion3" in result["minions_rejected"]


def test_glob_match_simple(key):
    """Test simple glob matching"""
    minion_data = {
        "web-1": {"state": "accepted"},
        "web-2": {"state": "accepted"},
        "db-1": {"state": "accepted"},
        "db-2": {"state": "pending"},
    }
    k = key(minion_data)

    # Test glob pattern matching
    result = k.glob_match("web-*")
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions"]
    assert len(result["minions"]) == 2
    assert "db-1" not in result["minions"]

    # Test glob on pending minions
    result = k.glob_match("db-*")
    assert "db-1" in result["minions"]
    assert "db-2" in result["minions_pre"]


def test_glob_match_list_input(key):
    """Test glob matching with list input"""
    minion_data = {
        "web-1": {"state": "accepted"},
        "web-2": {"state": "accepted"},
        "db-1": {"state": "accepted"},
        "app-1": {"state": "rejected"},
    }
    k = key(minion_data)

    # Test with a list of patterns
    result = k.glob_match(["web-*", "app-*"])
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions"]
    assert "app-1" in result["minions_rejected"]
    assert "db-1" not in result["minions"]

    # Test with exact match list
    result = k.glob_match(["web-1", "db-1"])
    assert "web-1" in result["minions"]
    assert "db-1" in result["minions"]
    assert len(result["minions"]) == 2


def test_list_keys(key):
    """Test listing all keys"""
    minion_data = {
        "web-1": {"state": "accepted"},
        "web-2": {"state": "pending"},
        "db-1": {"state": "rejected"},
        "app-1": {"state": "accepted"},
    }
    k = key(minion_data)

    result = k.list_keys()
    assert "web-1" in result["minions"]
    assert "app-1" in result["minions"]
    assert "web-2" in result["minions_pre"]
    assert "db-1" in result["minions_rejected"]
    assert len(result["minions"]) == 2
    assert len(result["minions_pre"]) == 1
    assert len(result["minions_rejected"]) == 1

    # Keys should be sorted alphabetically (case insensitive)
    assert result["minions"] == ["app-1", "web-1"]


def test_accept_key(key):
    """Test accepting a pending key"""
    minion_data = {
        "web-1": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-3": {"state": "rejected", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Accept a single key
    result = k.accept(match="web-1")
    assert "web-1" in result["minions"]
    assert len(result["minions"]) == 1

    # Verify the key state was changed
    result = k.list_keys()
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions_pre"]
    assert "web-3" in result["minions_rejected"]


def test_accept_multiple_keys(key):
    """Test accepting multiple pending keys"""
    minion_data = {
        "web-1": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "db-1": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Accept multiple keys with glob pattern
    result = k.accept(match="web-*")
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions"]
    assert len(result["minions"]) == 2

    # Verify the state was changed for matched keys only
    result = k.list_keys()
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions"]
    assert "db-1" in result["minions_pre"]


def test_accept_all_keys(key):
    """Test accepting all pending keys"""
    minion_data = {
        "web-1": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "db-1": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Accept all pending keys
    result = k.accept_all()
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions"]
    assert "db-1" in result["minions"]
    assert len(result["minions"]) == 3
    assert len(result.get("minions_pre", [])) == 0

    # Verify all keys moved to accepted state
    result = k.list_keys()
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions"]
    assert "db-1" in result["minions"]
    assert len(result["minions_pre"]) == 0


def test_reject_key(key):
    """Test rejecting a pending key"""
    minion_data = {
        "web-1": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-3": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Reject a single key
    result = k.reject(match="web-1")
    assert "web-1" in result["minions_rejected"]
    assert len(result["minions_rejected"]) == 1

    # Verify the key state was changed
    result = k.list_keys()
    assert "web-1" in result["minions_rejected"]
    assert "web-2" in result["minions_pre"]
    assert "web-3" in result["minions"]


def test_reject_multiple_keys(key):
    """Test rejecting multiple pending keys"""
    minion_data = {
        "web-1": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "db-1": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Reject multiple keys with glob pattern
    result = k.reject(match="web-*")
    assert "web-1" in result["minions_rejected"]
    assert "web-2" in result["minions_rejected"]
    assert len(result["minions_rejected"]) == 2

    # Verify the state was changed for matched keys only
    result = k.list_keys()
    assert "web-1" in result["minions_rejected"]
    assert "web-2" in result["minions_rejected"]
    assert "db-1" in result["minions_pre"]


def test_reject_all_keys(key):
    """Test rejecting all pending keys"""
    minion_data = {
        "web-1": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "db-1": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Reject all pending keys
    result = k.reject_all()
    assert "web-1" in result["minions_rejected"]
    assert "web-2" in result["minions_rejected"]
    assert "db-1" in result["minions_rejected"]
    assert len(result["minions_rejected"]) == 3
    assert len(result.get("minions_pre", [])) == 0

    # Verify all keys moved to rejected state
    result = k.list_keys()
    assert "web-1" in result["minions_rejected"]
    assert "web-2" in result["minions_rejected"]
    assert "db-1" in result["minions_rejected"]
    assert len(result["minions_pre"]) == 0


def test_delete_key(key):
    """Test deleting keys"""
    minion_data = {
        "web-1": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-3": {"state": "rejected", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Delete a single key
    result = k.delete_key(match="web-1")
    assert result == {}

    # Verify the key was deleted
    result = k.list_keys()
    assert "web-1" not in result["minions"]
    assert "web-2" in result["minions_pre"]
    assert "web-3" in result["minions_rejected"]


def test_delete_multiple_keys(key):
    """Test deleting multiple keys with glob pattern"""
    minion_data = {
        "web-1": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-3": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
        "db-1": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
        "db-2": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Delete multiple keys with glob pattern
    result = k.delete_key(match="web-*")
    assert result == {}

    # Verify keys were deleted
    result = k.list_keys()
    assert "web-1" not in result["minions"]
    assert "web-2" not in result["minions"]
    assert "db-1" in result["minions"]
    assert "db-2" in result["minions_pre"]


def test_delete_all_keys(key):
    """Test deleting all keys from all states"""
    minion_data = {
        "web-1": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-3": {"state": "rejected", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Store a denied key
    k.cache.store("denied_keys", "web-4", ["ssh-rsa DENIED-KEY test-denied-data"])

    # Delete all keys
    result = k.delete_all()

    # Verify all keys are in the result
    assert result == {
        "minions": [],
        "minions_denied": [],
        "minions_pre": [],
        "minions_rejected": [],
    }

    # Verify all keys were deleted
    result = k.list_keys()
    assert len(result["minions"]) == 0
    assert len(result["minions_pre"]) == 0
    assert len(result["minions_rejected"]) == 0
    assert len(result["minions_denied"]) == 0


def test_delete_keys_by_state(key):
    """Test deleting keys from specific states"""
    minion_data = {
        "web-1": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-3": {"state": "rejected", "pub": salt.crypt.gen_keys(2048)[1]},
        "api-1": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
        "api-2": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "api-3": {"state": "rejected", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Store denied keys
    k.cache.store("denied_keys", "web-4", ["ssh-rsa DENIED-KEY test-denied-data"])
    k.cache.store("denied_keys", "api-4", ["ssh-rsa DENIED-KEY test-denied-data"])

    # Delete keys from specific state - all rejected keys
    match_dict = {"minions_rejected": ["web-3", "api-3"]}
    result = k.delete_key(match_dict=match_dict)
    assert result == {}

    # Verify only rejected keys were deleted
    result = k.list_keys()
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions_pre"]
    assert "web-3" not in result["minions_rejected"]
    assert "api-1" in result["minions"]
    assert "api-2" in result["minions_pre"]
    assert "api-3" not in result["minions_rejected"]

    # Delete denied keys
    result = k.delete_den()

    # Verify denied keys are gone
    result = k.list_keys()
    assert "web-4" not in result.get("minions_denied", [])
    assert "api-4" not in result.get("minions_denied", [])


def test_key_str(key):
    """Test retrieving key strings"""
    pub_key = "ssh-rsa AAAAB3NzaC1yc2EA test-key-data"
    minion_data = {
        "web-1": {"state": "accepted", "pub": pub_key},
        "web-2": {"state": "pending", "pub": pub_key},
    }
    k = key(minion_data)

    # Get key string for specific minion
    result = k.key_str("web-1")
    assert "minions" in result
    assert "web-1" in result["minions"]
    assert result["minions"]["web-1"] == pub_key

    # Get key strings with glob pattern
    result = k.key_str("web-*")
    assert "minions" in result
    assert "minions_pre" in result
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions_pre"]
    assert result["minions"]["web-1"] == pub_key
    assert result["minions_pre"]["web-2"] == pub_key


def test_key_str_all(key):
    """Test retrieving all key strings"""
    pub_key = "ssh-rsa AAAAB3NzaC1yc2EA test-key-data"
    minion_data = {
        "web-1": {"state": "accepted", "pub": pub_key},
        "web-2": {"state": "pending", "pub": pub_key},
        "web-3": {"state": "rejected", "pub": pub_key},
    }
    k = key(minion_data)

    result = k.key_str_all()
    assert "minions" in result
    assert "minions_pre" in result
    assert "minions_rejected" in result

    assert "web-1" in result["minions"]
    assert "web-2" in result["minions_pre"]
    assert "web-3" in result["minions_rejected"]

    assert result["minions"]["web-1"] == pub_key
    assert result["minions_pre"]["web-2"] == pub_key
    assert result["minions_rejected"]["web-3"] == pub_key


def test_finger(key):
    """Test generating key fingerprints"""
    # Generate a real key for proper fingerprinting
    pub_key = salt.crypt.gen_keys(2048)[1]
    fingerprint = salt.utils.crypt.pem_finger(key=pub_key.encode("utf-8"))

    minion_data = {
        "web-1": {"state": "accepted", "pub": pub_key},
        "web-2": {"state": "pending", "pub": pub_key},
    }
    k = key(minion_data)

    # Get fingerprint for specific minion
    result = k.finger("web-1")
    assert "minions" in result
    assert "web-1" in result["minions"]
    assert result["minions"]["web-1"] == fingerprint

    # Get fingerprints with glob pattern
    result = k.finger("web-*")
    assert "minions" in result
    assert "minions_pre" in result
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions_pre"]
    assert result["minions"]["web-1"] == fingerprint
    assert result["minions_pre"]["web-2"] == fingerprint


def test_finger_different_hash_types(key):
    """Test generating key fingerprints with different hash algorithms"""
    # Generate a real key for proper fingerprinting
    pub_key = salt.crypt.gen_keys(2048)[1]

    minion_data = {
        "web-1": {"state": "accepted", "pub": pub_key},
    }
    k = key(minion_data)

    # Get fingerprint with default algorithm (typically sha256)
    default_result = k.finger("web-1")
    default_fingerprint = default_result["minions"]["web-1"]

    # Get fingerprint with md5
    md5_result = k.finger("web-1", hash_type="md5")
    md5_fingerprint = md5_result["minions"]["web-1"]

    # Get fingerprint with sha1
    sha1_result = k.finger("web-1", hash_type="sha1")
    sha1_fingerprint = sha1_result["minions"]["web-1"]

    # Verify different hash types produce different fingerprints
    assert default_fingerprint != md5_fingerprint
    assert default_fingerprint != sha1_fingerprint
    assert md5_fingerprint != sha1_fingerprint

    # Verify each fingerprint matches the expected length pattern
    assert len("".join(default_fingerprint.split(":"))) == 64  # sha256 is 64 hex chars

    assert len("".join(md5_fingerprint.split(":"))) == 32  # md5 is 32 hex chars

    assert len("".join(sha1_fingerprint.split(":"))) == 40  # sha1 is 40 hex chars


def test_denied_keys(key):
    """Test handling of denied keys"""
    minion_data = {"web-1": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]}}
    k = key(minion_data)

    # Store a denied key
    k.cache.store("denied_keys", "denied-1", ["ssh-rsa DENIED-KEY test-denied-data"])

    # Verify denied key shows up in list_keys
    result = k.list_keys()
    assert "denied-1" in result["minions_denied"]

    # Test retrieving denied key with key_str
    result = k.key_str("denied-1")
    assert "minions_denied" in result
    assert "denied-1" in result["minions_denied"]
    assert "ssh-rsa DENIED-KEY test-denied-data" in result["minions_denied"]["denied-1"]


def test_dict_match(key):
    """Test matching keys with dictionary input"""
    minion_data = {
        "web-1": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Create a match dictionary similar to what would be returned by glob_match
    match_dict = {
        "minions": ["web-1"],
        "minions_pre": ["web-2"],
    }

    result = k.dict_match(match_dict)
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions_pre"]


def test_list_status(key):
    """Test listing keys by status category"""
    minion_data = {
        "web-1": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-3": {"state": "rejected", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Test accepted keys
    result = k.list_status("acc")
    assert "web-1" in result["minions"]
    assert len(result["minions"]) == 1
    assert "minions_pre" not in result

    # Test pending keys
    result = k.list_status("pre")
    assert "web-2" in result["minions_pre"]
    assert len(result["minions_pre"]) == 1
    assert "minions" not in result

    # Test rejected keys
    result = k.list_status("rej")
    assert "web-3" in result["minions_rejected"]
    assert len(result["minions_rejected"]) == 1

    # Test all keys
    result = k.list_status("all")
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions_pre"]
    assert "web-3" in result["minions_rejected"]


def test_list_match_vs_glob_match(key):
    """Test to demonstrate the difference between list_match and glob_match"""
    minion_data = {
        "prefix-1": {"state": "accepted"},
        "prefix-2": {"state": "accepted"},
        "other-1": {"state": "accepted"},
    }
    k = key(minion_data)

    # list_match does only exact matching or comma-separated exact matching
    result = k.list_match("prefix-1")
    assert "prefix-1" in result["minions"]
    assert "prefix-2" not in result["minions"]
    assert len(result["minions"]) == 1

    # list_match with comma-separated values
    result = k.list_match("prefix-1,prefix-2")
    assert "prefix-1" in result["minions"]
    assert "prefix-2" in result["minions"]
    assert len(result["minions"]) == 2

    # list_match doesn't support glob patterns
    result = k.list_match("prefix-*")
    assert (
        not result
    )  # Should be empty as it looks for a minion literally named "prefix-*"

    # For glob pattern matching, use glob_match instead
    result = k.glob_match("prefix-*")
    assert "prefix-1" in result["minions"]
    assert "prefix-2" in result["minions"]
    assert "other-1" not in result["minions"]
    assert len(result["minions"]) == 2


def test_accept_with_include_options(key):
    """Test accepting keys with include_rejected and include_denied options"""
    minion_data = {
        "web-1": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "rejected", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-3": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Store a denied key
    k.cache.store("denied_keys", "web-4", [salt.crypt.gen_keys(2048)[1]])

    # Attempt to accept with include_rejected=False
    result = k.accept(match="web-*", include_rejected=False, include_denied=False)
    assert "web-1" in result["minions"]
    assert "web-2" not in result.get("minions", [])
    assert "web-4" not in result.get("minions", [])

    # Now try with include_rejected=True
    result = k.accept(match="web-*", include_rejected=True, include_denied=False)
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions"]
    assert "web-4" not in result.get("minions", [])

    # Finally with include_denied=True
    result = k.accept(match="web-*", include_rejected=True, include_denied=True)
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions"]
    assert "web-4" in result["minions"]

    # Verify states are changed
    result = k.list_keys()
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions"]
    assert "web-3" in result["minions"]
    assert "web-4" in result["minions"]
    assert "web-4" not in result["minions_denied"]


def test_reject_with_include_options(key):
    """Test rejecting keys with include_accepted and include_denied options"""
    minion_data = {
        "web-1": {"state": "pending", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-3": {"state": "rejected", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Store a denied key
    k.cache.store("denied_keys", "web-4", [salt.crypt.gen_keys(2048)[1]])

    # Attempt to reject with include_accepted=False
    result = k.reject(match="web-*", include_accepted=False, include_denied=False)
    assert "web-1" in result["minions_rejected"]
    assert "web-2" not in result.get("minions_rejected", [])
    assert "web-4" not in result.get("minions_rejected", [])

    # Now try with include_accepted=True
    result = k.reject(match="web-*", include_accepted=True, include_denied=False)
    assert "web-1" in result["minions_rejected"]
    assert "web-2" in result["minions_rejected"]
    assert "web-4" not in result.get("minions_rejected", [])

    # Finally with include_denied=True
    result = k.reject(match="web-*", include_accepted=True, include_denied=True)
    assert "web-1" in result["minions_rejected"]
    assert "web-2" in result["minions_rejected"]
    assert "web-4" in result["minions_rejected"]

    # Verify states are changed
    result = k.list_keys()
    assert "web-1" in result["minions_rejected"]
    assert "web-2" in result["minions_rejected"]
    assert "web-3" in result["minions_rejected"]
    assert "web-4" in result["minions_rejected"]
    assert "web-4" not in result["minions_denied"]


def test_invalid_key_state_transitions(key):
    """Test handling of invalid key state transitions"""
    minion_data = {
        "web-1": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
        "web-2": {"state": "rejected", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Try to reject already rejected key
    result = k.reject(match="web-2")
    # Should still show up as rejected
    assert "web-2" in result["minions_rejected"]

    # Trying to accept already accepted key should be idempotent
    result = k.accept(match="web-1")
    # Should still show up as accepted
    assert "web-1" in result["minions"]

    # Verify no state changes
    result = k.list_keys()
    assert "web-1" in result["minions"]
    assert "web-2" in result["minions_rejected"]


def test_nonexistent_key_operations(key):
    """Test operations on nonexistent keys"""
    minion_data = {
        "web-1": {"state": "accepted", "pub": salt.crypt.gen_keys(2048)[1]},
    }
    k = key(minion_data)

    # Try to accept a nonexistent key
    result = k.accept(match="nonexistent-key")
    # Should return empty result
    assert "minions" not in result or len(result["minions"]) == 0

    # Try to reject a nonexistent key
    result = k.reject(match="nonexistent-key")
    # Should return empty result
    assert "minions_rejected" not in result or len(result["minions_rejected"]) == 0

    # Try to delete a nonexistent key
    result = k.delete_key(match="nonexistent-key")
    # Should return empty result
    assert "minions" not in result or len(result["minions"]) == 0

    # Try to get fingerprint of nonexistent key
    result = k.finger("nonexistent-key")
    # Should return empty result
    assert "minions" not in result or len(result["minions"]) == 0

    # Verify original key is still intact
    result = k.list_keys()
    assert "web-1" in result["minions"]


def test_invalid_key_content(key):
    """Test handling of keys with invalid content"""
    # Create a key with invalid content
    minion_data = {
        "invalid-key": {"state": "pending", "pub": "not-a-valid-key"},
    }
    k = key(minion_data)

    # Try to accept the invalid key - this might log an error but should not crash
    result = k.accept(match="invalid-key")
    # Key should not be accepted if invalid
    assert "invalid-key" in result["minions_pre"]

    # Try to generate a fingerprint for invalid key content
    try:
        result = k.finger("invalid-key")
        # Test passes if no exception, even if fingerprint is not valid
    except Exception as e:  # pylint: disable=broad-exception-caught
        pytest.fail(f"Fingerprinting invalid key content raised an exception: {e}")


def test_finger_all(key):
    """Test retrieving fingerprints for all keys at once"""
    # Generate a real key for proper fingerprinting
    pub_key = salt.crypt.gen_keys(2048)[1]
    fingerprint = salt.utils.crypt.pem_finger(key=pub_key.encode("utf-8"))

    minion_data = {
        "web-1": {"state": "accepted", "pub": pub_key},
        "web-2": {"state": "pending", "pub": pub_key},
        "web-3": {"state": "rejected", "pub": pub_key},
    }
    k = key(minion_data)

    # Store a denied key
    k.cache.store("denied_keys", "web-4", [pub_key])

    # Get fingerprints for all keys
    result = k.finger_all()

    # Verify result contains all key categories
    assert "minions" in result
    assert "minions_pre" in result
    assert "minions_rejected" in result
    assert "minions_denied" in result

    # Check fingerprints are correct
    assert result["minions"]["web-1"] == fingerprint
    assert result["minions_pre"]["web-2"] == fingerprint
    assert result["minions_rejected"]["web-3"] == fingerprint
    assert result["minions_denied"]["web-4"] == fingerprint

    # Test with a specified hash type
    result = k.finger_all(hash_type="md5")
    md5_fingerprint = salt.utils.crypt.pem_finger(
        key=pub_key.encode("utf-8"), sum_type="md5"
    )

    # Verify the hash type changed
    assert result["minions"]["web-1"] == md5_fingerprint
    assert result["minions"]["web-1"] != fingerprint
