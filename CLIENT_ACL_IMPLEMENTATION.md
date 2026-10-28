# Client ACL Implementation Summary

## Overview

This implementation adds Access Control List (ACL) functionality for remote CLI clients using PKI authentication. The ACL system allows administrators to control which runner and wheel functions each client can execute.

## Implementation Components

### 1. ClientACL Class (`salt/acl/__init__.py`)

**Location**: `/home/dan/src/salt/salt/acl/__init__.py`

**Key Features**:
- Whitelist-based access control
- Per-client, per-function-type permissions
- Glob pattern support for function matching
- Backward compatibility (no ACL = allow all)
- Optional blacklist support

**Main Method**: `client_is_allowed(client_id, cmd, cmd_type)`
- Returns `True` if client is authorized
- Returns `False` if client is denied
- Supports wildcards via `salt.utils.stringutils.check_whitelist_blacklist()`

### 2. Authorization Logic (`salt/daemons/masterapi.py`)

**Location**: `/home/dan/src/salt/salt/daemons/masterapi.py`

**Modified Class**: `LocalFuncs`

**Initialization**:
```python
def __init__(self, opts, key):
    # ... existing code ...
    # Make a client ACL object
    self.client_acl = salt.acl.ClientACL(opts.get("client_acl", {}))
```

**Runner Method** (`LocalFuncs.runner()`):
- Authenticates the request (existing logic)
- Determines if request is from a client:
  - Checks if `auth_type == "user"`
  - Looks up username in `client_keys` cache bank
- If client: Enforces client ACL
- If not client: Uses existing authorization (ckminions.runner_check)
- Returns clear error message on denial

**Wheel Method** (`LocalFuncs.wheel()`):
- Same logic as runner method
- Enforces client ACL for wheel functions
- Maintains existing authorization for non-client requests

### 3. Client Detection Logic

**How it works**:
1. Check if `auth_type == "user"` (indicates PKI authentication)
2. Query the key cache for `client_keys/<username>`
3. If key exists, it's a client; if not, it's a regular user

**Code**:
```python
is_client = False
if auth_type == "user" and username:
    try:
        key_cache = salt.cache.Cache(
            self.opts, driver=self.opts["keys.cache_driver"]
        )
        client_key = key_cache.fetch("client_keys", username)
        if client_key:
            is_client = True
    except Exception:
        # If we can't check, assume not a client
        pass
```

## Configuration Format

```yaml
client_acl:
  <client-id>:
    runner:
      - <pattern1>
      - <pattern2>
    wheel:
      - <pattern1>
      - <pattern2>
```

**Examples**:
```yaml
client_acl:
  admin-client:
    runner: ['*']
    wheel: ['*']

  monitor-client:
    runner: ['jobs.*', 'cache.*', 'manage.*']
    wheel: ['key.list_all', 'key.finger']

  keymgmt-client:
    runner: []
    wheel: ['key.*']
```

## Authorization Flow

```
1. Client Request
   ↓
2. Authentication (PKI)
   ↓
3. Identity Check (username in client_keys?)
   ↓
4. If Client:
   ├─ Check client_acl configuration
   ├─ If not in ACL → DENY
   ├─ If in ACL → Check function pattern
   └─ Match → ALLOW, No Match → DENY

   If Not Client:
   └─ Use existing authorization (eauth/token/publisher_acl)
   ↓
5. Execute Function (if authorized)
```

## Error Messages

### Client Not in ACL
```python
{
    "error": {
        "name": "ClientAuthorizationError",
        "message": "Client \"my-client\" is not authorized to execute runner function \"state.orchestrate\"."
    }
}
```

### Function Not Allowed
Same error format, indicates which function was denied.

## Backward Compatibility

### No client_acl Configured
- **Behavior**: All clients can execute all functions
- **Rationale**: Maintains existing behavior for systems not using client ACL
- **Implementation**: `ClientACL.client_is_allowed()` returns `True` if `self.client_acl` is empty

### Mixed Environment
- Clients with ACL entries: Enforced
- Clients without ACL entries: Denied (if client_acl is configured)
- Regular users (eauth/token): Unaffected, use existing authorization

## Security Model

### Defense in Depth
1. **Authentication**: PKI-based client key verification
2. **Authorization**: Client ACL for function-level access control
3. **Least Privilege**: Whitelist approach, explicit permissions required

### Key Management
- Client keys stored in `client_keys` cache bank (separate from minion keys)
- Managed via `salt-key --client` commands
- Same key rotation practices as minion keys

## Testing Recommendations

### Unit Tests
1. `ClientACL.client_is_allowed()` with various configurations
2. Client detection logic (client_keys lookup)
3. Error message formatting

### Integration Tests
1. Client authentication + authorization flow
2. ACL enforcement for runner commands
3. ACL enforcement for wheel commands
4. Backward compatibility (no ACL configured)
5. Mixed authorization (clients + regular users)

### Scenario Tests
1. Admin client (full access)
2. Restricted client (limited functions)
3. Denied client (not in ACL)
4. Invalid function request
5. Glob pattern matching

## Code Locations

| Component | File | Lines |
|-----------|------|-------|
| ClientACL class | `salt/acl/__init__.py` | 15-116 |
| LocalFuncs.__init__ | `salt/daemons/masterapi.py` | ~1123 |
| LocalFuncs.runner() | `salt/daemons/masterapi.py` | ~1125-1201 |
| LocalFuncs.wheel() | `salt/daemons/masterapi.py` | ~1203-1287 |

## Design Decisions

### 1. Whitelist vs Blacklist
**Choice**: Whitelist (with optional blacklist support)
**Rationale**: More secure, explicit permissions required

### 2. Separate from PublisherACL
**Choice**: New ClientACL class
**Rationale**:
- Different use case (clients vs users)
- Different config structure
- Maintains separation of concerns

### 3. Client Detection via Cache Lookup
**Choice**: Check `client_keys` cache bank
**Rationale**:
- Reliable way to distinguish clients from users
- Uses existing infrastructure
- No new fields needed in load

### 4. No ACL = Allow All
**Choice**: Backward compatible default
**Rationale**:
- Doesn't break existing deployments
- Opt-in security model
- Easy migration path

### 5. Per-function Type Control
**Choice**: Separate runner and wheel permissions
**Rationale**:
- Fine-grained control
- Matches Salt's function organization
- Clear security boundaries

## Future Enhancements

1. **Targeting ACL**: Control which minions clients can target
2. **Time-based ACL**: Restrict execution to specific time windows
3. **Rate limiting**: Prevent abuse by limiting request frequency
4. **Audit logging**: Enhanced logging for ACL decisions
5. **Dynamic ACL**: Reload ACL without master restart
6. **ACL inheritance**: Group-based permissions

## Related Documentation

- Client Authentication: `REMOTE_CLI_IMPLEMENTATION.md`
- Configuration Examples: `CLIENT_ACL_EXAMPLE.md`
- PublisherACL: https://docs.saltproject.io/en/latest/ref/publisheracl.html
