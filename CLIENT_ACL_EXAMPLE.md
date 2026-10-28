# Client ACL Configuration Example

## Overview

The Client ACL system allows administrators to control which remote CLI clients can execute specific runner and wheel functions on the Salt master.

## Configuration

Add the `client_acl` configuration to your master configuration file (`/etc/salt/master`):

```yaml
# Client ACL Configuration
# Format:
#   client_acl:
#     <client-id>:
#       runner: [list of allowed runner functions]
#       wheel: [list of allowed wheel functions]

client_acl:
  # Admin client - full access
  admin-client:
    runner:
      - '*'
    wheel:
      - '*'

  # Monitoring client - read-only operations
  monitor-client:
    runner:
      - 'jobs.list_jobs'
      - 'jobs.lookup_jid'
      - 'cache.grains'
      - 'cache.pillar'
      - 'manage.status'
      - 'manage.up'
      - 'manage.down'
    wheel:
      - 'key.list_all'
      - 'key.finger'

  # Key management client - limited to key operations
  keymgmt-client:
    runner:
      []  # No runner access
    wheel:
      - 'key.*'  # All key operations

  # CI/CD client - specific operations
  cicd-client:
    runner:
      - 'jobs.list_jobs'
      - 'jobs.lookup_jid'
      - 'state.orchestrate'
    wheel:
      - 'key.list_all'
      - 'key.accept'
```

## Behavior

### When client_acl is NOT configured
- **Default**: All authenticated clients have full access (backward compatible)
- No authorization checks are performed beyond authentication

### When client_acl IS configured
- **Whitelist approach**: Only explicitly listed clients can execute functions
- **Per-function control**: Each client can have different permissions for runner and wheel
- **Glob pattern support**: Use wildcards like `jobs.*` or `*` for broader access
- **Clear error messages**: Clients receive specific error messages when denied

## Authorization Flow

1. **Authentication**: Client authenticates using PKI (client.pem/client.pub)
2. **Identity verification**: Master verifies the client's identity
3. **ACL check**:
   - If client_acl is configured and client ID is in the ACL:
     - Check if the requested function matches allowed patterns
   - If client_acl is configured but client ID is NOT in the ACL:
     - **DENY** - Authorization error returned
   - If client_acl is NOT configured:
     - **ALLOW** - Backward compatible behavior
4. **Execution**: If authorized, the function is executed

## Error Messages

When a client is denied access, they receive a clear error message:

```python
{
    "error": {
        "name": "ClientAuthorizationError",
        "message": "Client \"monitor-client\" is not authorized to execute runner function \"state.orchestrate\"."
    }
}
```

## Usage Example

### Setup Client Keys

On the client machine:
```bash
# Initialize client with ID
salt-run --client-auth --id=monitor-client test.ping
```

On the master:
```bash
# Accept the client key
salt-key -a monitor-client --client
```

### Test Access Control

With the example configuration above:

```bash
# monitor-client: ALLOWED
salt-run --client-auth --id=monitor-client jobs.list_jobs

# monitor-client: DENIED
salt-run --client-auth --id=monitor-client state.orchestrate my.orchestration

# keymgmt-client: ALLOWED
salt-key --client-auth --id=keymgmt-client -L

# keymgmt-client: DENIED
salt-run --client-auth --id=keymgmt-client jobs.list_jobs
```

## Security Considerations

1. **Authentication is required**: Client ACL only controls authorization, not authentication
2. **Client key management**: Use `salt-key --client` commands to manage client keys
3. **Least privilege**: Grant only the minimum permissions needed
4. **Regular audits**: Review client_acl configuration periodically
5. **Rotation**: Rotate client keys regularly like you would minion keys

## Implementation Details

### Code Locations

- **ACL Class**: `salt/acl/__init__.py` - `ClientACL` class
- **Authorization Logic**: `salt/daemons/masterapi.py` - `LocalFuncs.runner()` and `LocalFuncs.wheel()`
- **Authentication**: `salt/master.py` - `AESFuncs.__verify_client()`

### Client Detection

The system determines if a request is from a client by:
1. Checking if auth_type is "user" (PKI authentication)
2. Looking up the username in the "client_keys" cache bank
3. If found, applying client ACL rules; otherwise, using standard authorization

## Migration Path

### Phase 1: Monitor (No ACL configured)
- Deploy client authentication without ACL
- Monitor which clients connect and what they execute
- Plan ACL rules based on actual usage

### Phase 2: Permissive ACL
- Configure client_acl with generous permissions
- Gradually tighten rules based on requirements

### Phase 3: Strict ACL
- Implement least-privilege rules
- Audit and adjust as needed

## Troubleshooting

### Client cannot execute any commands
- Check if client_acl is configured and client ID is listed
- Verify client key is accepted: `salt-key -L --client`
- Check master logs for authorization errors

### Client can execute everything despite ACL
- Verify client_acl is in the master config (not minion config)
- Check if client is listed in the ACL
- Ensure the master was restarted after config changes

### ACL not being enforced
- Verify the client is using `--client-auth` flag
- Check that client keys are in the right location (client_keys cache bank)
- Look for errors in master logs related to cache or ACL initialization
