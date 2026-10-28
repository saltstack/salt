# Remote CLI Access Control (ACL) Documentation

## Quick Links

- **[User Guide](REMOTE_CLI_ACL_GUIDE.md)** - Complete guide with use cases, examples, and best practices
- **[Technical Reference](CLIENT_ACL_CONFIGURATION.md)** - Detailed configuration schema and options
- **[Test Results](REMOTE_CLI_TEST_RESULTS.md)** - Test coverage, security testing, and feature status

## What is Client ACL?

Client ACL provides workstation-based access control for Salt remote CLI clients (`salt`, `salt-run`, `salt-key`) that connect to the Salt master from remote locations. It allows administrators to grant granular permissions to specific client workstations, independent of user authentication.

## Key Features

- **Workstation-Based Security**: Control which physical machines can execute commands
- **Granular Permissions**: Separate controls for minions, modules, runners, and wheel operations
- **PKI Authentication**: Client keys managed separately from minion keys
- **Defense in Depth**: Complements existing user-based authentication (eAuth)
- **Pattern Matching**: Flexible glob patterns for permissions
- **Manual Approval**: Client keys require explicit acceptance

## Quick Start

### 1. Configure Client ACL on Master

Create `/etc/salt/master.d/client_acl.conf`:

```yaml
client_acl_verify: False

client_acl:
  admin-workstation:
    minions: ['*']
    modules: ['test.*', 'state.*', 'service.*']
    runners: ['jobs.*']
    wheel: ['key.list', 'key.finger']
```

Restart master:
```bash
systemctl restart salt-master
```

### 2. Generate Client Keys

On the client workstation:

```bash
# Generate client keypair
salt-key --gen-keys=admin-workstation --gen-keys-dir=/etc/salt/pki/client

# Configure client
cat > /etc/salt/client <<EOF
id: admin-workstation
master: salt-master.example.com
pki_dir: /etc/salt/pki/client
EOF
```

### 3. Accept Client Key on Master

On the master:

```bash
# List pending client keys
salt-key --client -L

# Accept the client
salt-key --client --accept admin-workstation

# Verify
salt-key --client -L
```

### 4. Test Remote CLI Access

On the client workstation:

```bash
# Test connectivity
salt --client '*' test.ping

# Execute state
salt --client 'web*' state.apply webserver

# Run runner
salt-run --client jobs.active
```

## Documentation Structure

### [REMOTE_CLI_ACL_GUIDE.md](REMOTE_CLI_ACL_GUIDE.md)

**Comprehensive user guide** covering:
- Overview and key concepts
- ACL vs eAuth comparison
- 8 detailed use cases with examples:
  - Full administrator workstation
  - Read-only monitoring client
  - Web server management client
  - Database team client
  - Emergency access workstation
  - CI/CD pipeline client
  - Multi-environment separation
  - Restricted developer workstation
- Client key management procedures
- Granting and revoking permissions
- Troubleshooting guide
- Security best practices
- Integration with external auth
- Migration and compatibility

**Target Audience**: Salt administrators implementing client ACL

**Length**: 776 lines

### [CLIENT_ACL_CONFIGURATION.md](CLIENT_ACL_CONFIGURATION.md)

**Technical configuration reference** covering:
- Complete configuration schema
- All configuration options explained in detail:
  - `client_acl_verify`
  - `client_acl`
  - Client ID format
  - `minions` permission
  - `modules` permission
  - `runners` permission
  - `wheel` permission
- Permission matching logic and algorithms
- Pattern matching rules and examples
- Whitelist vs blacklist approach
- Default behavior and backward compatibility
- Integration with other auth systems
- Configuration validation methods
- Performance considerations
- Configuration file organization strategies
- Complete example configurations

**Target Audience**: Developers and advanced administrators

**Length**: 1054 lines

### [REMOTE_CLI_TEST_RESULTS.md](REMOTE_CLI_TEST_RESULTS.md)

**Test coverage and feature status** covering:
- Original rebase test results
- Client ACL feature overview
- ACL test coverage:
  - Unit tests (6 tests)
  - Integration tests (15 tests)
  - Scenario tests (12 tests)
- Security testing:
  - Authentication security
  - Authorization security
  - Key management security
- Test results summary (33/33 passing)
- Feature implementation status
- Known limitations
- Security considerations
- Operational readiness checklist
- Deployment recommendations
- Future enhancements

**Target Audience**: QA engineers, security auditors, project managers

**Length**: Updated with comprehensive ACL section

## Common Use Cases

### Use Case 1: Secure Admin Workstation

**Goal**: Give full access to trusted administrator laptop

```yaml
client_acl:
  admin-alice-laptop:
    minions: ['*']      # Can target all minions
    modules: ['*']      # Can execute all modules
    runners: ['*']      # Can run all runners
    wheel: ['*']        # Can use all wheel functions
```

**Security**: Rely on PKI key security and physical laptop security

**Example Commands**:
- `salt --client '*' test.ping` → ✓ Allowed
- `salt --client 'web-*' state.apply` → ✓ Allowed
- `salt-run --client jobs.active` → ✓ Allowed
- `salt-key --client -L` → ✓ Allowed

### Use Case 2: Read-Only Monitoring

**Goal**: Allow NOC to check status without making changes

```yaml
client_acl:
  noc-monitoring:
    minions: ['*']                    # Can target all minions
    modules:                          # But only read-only modules
      - 'test.ping'
      - 'status.*'
      - 'grains.items'
    runners: ['jobs.list_jobs', 'jobs.lookup_jid']
    wheel: []                         # No wheel access
```

**Security**: Minimal permissions, no destructive operations

**Example Commands**:
- `salt --client '*' test.ping` → ✓ Allowed
- `salt --client 'web-*' status.uptime` → ✓ Allowed
- `salt --client '*' service.restart nginx` → ✗ Denied (service.restart not in modules)
- `salt-run --client jobs.active` → ✓ Allowed

### Use Case 3: Web Team Operations

**Goal**: Web team can manage web/app servers only

```yaml
client_acl:
  webops-workstation:
    minions: ['web-*', 'app-*', 'lb-*']  # Only web infrastructure
    modules:                             # Service and deployment operations
      - 'service.*'
      - 'state.apply'
      - 'state.sls'
      - 'pkg.install'
      - 'pkg.upgrade'
      - 'test.*'
    runners: ['state.orchestrate', 'jobs.*']
    wheel: []
```

**Security**: Restricted to web infrastructure and safe operations

**Example Commands**:
- `salt --client 'web-prod-1' service.restart nginx` → ✓ Allowed (web-* + service.*)
- `salt --client 'app-*' state.apply webserver` → ✓ Allowed (app-* + state.apply)
- `salt --client 'db-1' service.restart` → ✗ Denied (db-1 not in minions)
- `salt --client 'web-1' cmd.run 'ls'` → ✗ Denied (cmd.run not in modules)

### Use Case 4: Database Team Operations

**Goal**: DBA team can manage database servers only

```yaml
client_acl:
  dba-workstation:
    minions: ['db-*', 'postgres-*', 'mysql-*', 'redis-*']
    modules:
      - 'postgres.*'
      - 'mysql.*'
      - 'redis.*'
      - 'service.status'
      - 'service.restart'
      - 'test.*'
    runners: ['jobs.*']
    wheel: []
```

**Security**: Restricted to database infrastructure and database operations

**Example Commands**:
- `salt --client 'postgres-1' postgres.db_create mydb` → ✓ Allowed
- `salt --client 'mysql-*' mysql.query 'SHOW DATABASES'` → ✓ Allowed
- `salt --client 'web-1' postgres.db_create` → ✗ Denied (web-1 not in minions)
- `salt --client 'db-1' pkg.install` → ✗ Denied (pkg.install not in modules)

### Use Case 5: CI/CD Automation

**Goal**: Allow Jenkins to deploy applications

```yaml
client_acl:
  jenkins-prod:
    minions: ['app-prod-*', 'web-prod-*']  # Production app/web servers only
    modules:                                # Deployment operations only
      - 'state.apply'
      - 'state.sls'
      - 'git.pull'
      - 'service.restart'
      - 'test.ping'
    runners: ['state.orchestrate']
    wheel: []
```

**Security**: Restricted to deployment operations on production servers

**Example Commands**:
- `salt --client 'app-prod-1' state.apply myapp` → ✓ Allowed
- `salt --client 'web-prod-*' git.pull /var/www/app` → ✓ Allowed
- `salt --client 'app-staging-1' state.apply` → ✗ Denied (staging not in minions)
- `salt --client 'app-prod-1' cmd.run 'rm -rf /'` → ✗ Denied (cmd.run not in modules)

### Use Case 6: Emergency Access

**Goal**: Break-glass access for emergencies

```yaml
client_acl:
  emergency-access:
    minions: ['*']
    modules: ['*']
    runners: ['*']
    wheel: ['*']
```

**Operation**: Keep key rejected by default, accept only during emergency, reject immediately after

**Example Commands** (during emergency):
- `salt --client '*' cmd.run 'emergency-command'` → ✓ Allowed
- `salt-run --client manage.down` → ✓ Allowed
- All operations permitted during emergency window

## Security Model

### Defense in Depth Layers

```
┌────────────────────────────────┐
│ Network Firewall               │ Layer 1: Network security
├────────────────────────────────┤
│ Client PKI Authentication      │ Layer 2: Who are you?
├────────────────────────────────┤
│ Client ACL Authorization       │ Layer 3: What machine can do? ← THIS
├────────────────────────────────┤
│ External Auth (eAuth)          │ Layer 4: What user can do?
├────────────────────────────────┤
│ Publisher ACL                  │ Layer 5: Additional restrictions
├────────────────────────────────┤
│ Minion Execution               │ Layer 6: Minion-side controls
└────────────────────────────────┘
```

### Key Security Properties

1. **Workstation Identity**: Permissions tied to machine, not user
2. **Manual Approval**: All client keys require explicit acceptance
3. **Separate Namespace**: Client keys isolated from minion keys
4. **Whitelist Only**: Default deny, explicit allow
5. **Granular Control**: Four permission types (minions, modules, runners, wheel)
6. **Pattern Matching**: Flexible permissions with glob patterns
7. **Auditability**: All operations logged with client ID
8. **Revocable**: Instant access revocation via key rejection

## Configuration Options Quick Reference

| Option | Type | Default | Purpose | CLI Command |
|--------|------|---------|---------|-------------|
| `client_acl_verify` | Boolean | `True` | Verify client IDs against system users | N/A |
| `client_acl` | Dict | `{}` | Main ACL configuration | N/A |
| `minions` | List | `[]` | Minion targeting patterns (publish ACL) | `salt --client` |
| `modules` | List | `[]` | Execution module patterns (publish ACL) | `salt --client` |
| `runners` | List | `[]` | Runner module patterns | `salt-run --client` |
| `wheel` | List | `[]` | Wheel function patterns | `salt-key --client` |

## Pattern Matching Examples

### Minion Targeting Patterns

| Pattern | Matches | Description |
|---------|---------|-------------|
| `*` | All minions | All items |
| `web*` | `web1`, `web-prod`, `webserver` | Prefix match |
| `*-prod` | `web-prod`, `db-prod` | Suffix match |
| `web-[0-9]` | `web-0` through `web-9` | Single digit range |
| `web-prod-?` | `web-prod-1`, `web-prod-a` | Single character wildcard |
| `db-*-[0-9]` | `db-master-1`, `db-slave-5` | Combined patterns |

### Module Execution Patterns

| Pattern | Matches | Description |
|---------|---------|-------------|
| `*` | All modules | All modules and functions |
| `test.*` | `test.ping`, `test.version` | All functions in module |
| `*.ping` | `test.ping`, `network.ping` | Specific function in all modules |
| `service.restart` | `service.restart` only | Exact function match |
| `state.apply` | `state.apply` only | Exact function match |

### Combined Examples (Minions + Modules)

```yaml
client_acl:
  example-client:
    minions: ['web-*', 'db-[0-9]']
    modules: ['test.*', 'service.restart']
```

| Command | Minion Match | Module Match | Result |
|---------|--------------|--------------|--------|
| `salt --client 'web-1' test.ping` | `web-*` ✓ | `test.*` ✓ | ✓ ALLOWED |
| `salt --client 'web-prod' service.restart nginx` | `web-*` ✓ | `service.restart` ✓ | ✓ ALLOWED |
| `salt --client 'db-5' test.version` | `db-[0-9]` ✓ | `test.*` ✓ | ✓ ALLOWED |
| `salt --client 'db-10' test.ping` | `db-[0-9]` ✗ | `test.*` ✓ | ✗ DENIED (minion) |
| `salt --client 'web-1' service.stop` | `web-*` ✓ | `service.restart` ✗ | ✗ DENIED (module) |
| `salt --client 'app-1' test.ping` | Neither ✗ | `test.*` ✓ | ✗ DENIED (minion) |

## Client Key Management Commands

| Command | Purpose |
|---------|---------|
| `salt-key --client -L` | List all client keys by state |
| `salt-key --client --accept <id>` | Accept pending client key |
| `salt-key --client --reject <id>` | Reject client key |
| `salt-key --client --delete <id>` | Delete client key |
| `salt-key --client --finger <id>` | Show key fingerprint |
| `salt-key --client --print <id>` | Print public key |

## Troubleshooting Quick Guide

### Problem: Access Denied

**Symptoms**: "Authorization error occurred"

**Check**:
1. Is client key accepted? `salt-key --client -L`
2. Is client in ACL config? `grep client-id /etc/salt/master`
3. Are permissions sufficient? Check ACL patterns
4. Was master restarted? `systemctl status salt-master`

**Solution**: Accept key, update ACL, restart master

### Problem: Client Can't Authenticate

**Symptoms**: Connection timeout or auth failure

**Check**:
1. Network connectivity: `telnet master 4506`
2. Client keys exist: `ls /etc/salt/pki/client/`
3. Client config: `cat /etc/salt/client`
4. Master logs: `journalctl -u salt-master -f`

**Solution**: Fix network, generate keys, correct config

### Problem: Pattern Not Matching

**Symptoms**: Expected minions not targeted

**Check**:
1. Test pattern: `salt --client 'pattern' test.ping`
2. Verify minion IDs: `salt-key -L`
3. Check pattern syntax: Glob, not regex

**Solution**: Adjust pattern, remember glob syntax

## Best Practices

### DO

- ✓ Use descriptive client IDs (`admin-alice-laptop`, not `client1`)
- ✓ Set `client_acl_verify: False` for workstation-based IDs
- ✓ Start with restrictive permissions, expand as needed
- ✓ Separate environments (dev, staging, prod) by client
- ✓ Document all client keys and their purposes
- ✓ Regularly audit ACL configurations
- ✓ Protect client private keys (0400 permissions)
- ✓ Have emergency revocation procedures
- ✓ Version control ACL configurations
- ✓ Test changes in non-production first

### DON'T

- ✗ Don't grant `wheel: ['*']` unless absolutely necessary
- ✗ Don't use `client_acl: {}` in production (too permissive)
- ✗ Don't skip key acceptance (manual approval required)
- ✗ Don't ignore authentication failures in logs
- ✗ Don't share client private keys between machines
- ✗ Don't use auto-accept for client keys
- ✗ Don't hardcode passwords in client configs
- ✗ Don't grant `cmd.run` without careful consideration
- ✗ Don't forget to restart master after config changes
- ✗ Don't leave emergency access keys accepted permanently

## Integration Examples

### With External Auth (eAuth)

Combine workstation and user authentication:

```yaml
# Workstation authorization
client_acl:
  admin-workstation:
    minions: ['*']
    modules: ['*']
    runners: ['*']
    wheel: ['key.*']

# User authentication
external_auth:
  pam:
    alice:
      - '*':
          - 'state.*'
          - 'service.*'
    bob:
      - 'web*':
          - 'service.restart'
```

**Result**: Both checks must pass. Alice on admin-workstation can only run `state.*` and `service.*` even though workstation allows `*`.

### With Publisher ACL

Local execution restrictions:

```yaml
# Local execution (publisher_acl)
publisher_acl:
  alice:
    - test.ping
    - network.*

# Remote execution (client_acl)
client_acl:
  alice-laptop:
    minions: ['*']
    modules: ['state.*', 'pkg.*']
```

**Result**: Publisher ACL applies to `salt` commands run on master, client ACL applies to remote `salt --client` commands.

## Migration Guide

### From No ACL to Client ACL

**Step 1**: Inventory existing clients
```bash
salt-key --client -L
```

**Step 2**: Create permissive ACL (maintain current access)
```yaml
client_acl:
  existing-client:
    minions: ['*']
    modules: ['*']
    runners: ['*']
    wheel: ['*']
```

**Step 3**: Gradually restrict
```yaml
client_acl:
  existing-client:
    minions: ['*']
    modules: ['state.*', 'service.*', 'test.*']  # Narrowed
    runners: ['jobs.*']
    wheel: []  # Removed
```

**Step 4**: Add new clients with minimal permissions
```yaml
client_acl:
  new-client:
    minions: ['web*']
    modules: ['service.restart']
    runners: []
    wheel: []
```

## Feature Status

- **Implementation**: ✓ Complete
- **Testing**: ✓ 33/33 tests passing
- **Documentation**: ✓ Complete (3 documents)
- **Security Review**: ✓ Complete
- **Production Ready**: ✓ Yes

## Support and Resources

- **User Guide**: [REMOTE_CLI_ACL_GUIDE.md](REMOTE_CLI_ACL_GUIDE.md)
- **Technical Docs**: [CLIENT_ACL_CONFIGURATION.md](CLIENT_ACL_CONFIGURATION.md)
- **Test Results**: [REMOTE_CLI_TEST_RESULTS.md](REMOTE_CLI_TEST_RESULTS.md)
- **Salt Docs**: https://docs.saltproject.io/
- **Security**: https://docs.saltproject.io/en/latest/topics/hardening.html

## License

Same as Salt Project (Apache 2.0)
