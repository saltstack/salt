# Client ACL Configuration Reference

## Overview

This document provides the complete technical reference for configuring Client Access Control Lists (ACLs) in Salt. Client ACLs provide workstation-based access control for remote CLI clients connecting to the Salt master.

## Configuration Location

Client ACL configuration is placed in the Salt master configuration:

- **Primary location**: `/etc/salt/master`
- **Drop-in directory**: `/etc/salt/master.d/*.conf`
- **Recommended**: `/etc/salt/master.d/client_acl.conf` (for organization)

## Configuration Schema

### Top-Level Structure

```yaml
# Boolean: Verify client IDs against system users
client_acl_verify: <boolean>

# Dictionary: Main ACL configuration
client_acl:
  <client-id>:
    minions: <list>
    modules: <list>
    runners: <list>
    wheel: <list>
```

### Configuration Options Reference

#### `client_acl_verify`

**Type**: Boolean
**Default**: `True`
**Location**: Master config top level

Controls whether the master verifies that client IDs correspond to actual system users.

**Values**:
- `True` (default): Master checks if client ID exists as system user. Provides additional validation.
- `False`: No verification. Client IDs are arbitrary strings.

**Use Cases**:
- Set to `True` when client IDs match system usernames (e.g., "alice", "bob")
- Set to `False` when using descriptive client IDs (e.g., "admin-workstation-1")

**Example**:
```yaml
# Verify against system users
client_acl_verify: True

# Don't verify (recommended for workstation-based IDs)
client_acl_verify: False
```

**Security Note**: Setting to `False` is actually more secure for workstation-based ACLs, as it separates workstation identity from user identity.

#### `client_acl`

**Type**: Dictionary
**Default**: `{}` (empty, no restrictions)
**Location**: Master config top level

Main ACL configuration mapping client IDs to their permissions.

**Structure**:
```yaml
client_acl:
  <client-id-1>:
    <permissions>
  <client-id-2>:
    <permissions>
```

**Default Behavior**: If `client_acl` is not defined or empty, all accepted client keys have full access (backward compatible).

#### Client ID

**Type**: String
**Format**: Alphanumeric with hyphens and underscores recommended
**Case Sensitive**: Yes

The unique identifier for a client workstation.

**Requirements**:
- Must match exactly with the client's key ID
- Should be descriptive and auditable
- Must be unique across all clients

**Best Practices**:
```yaml
# GOOD - descriptive, includes purpose and location
admin-alice-laptop-nyc
cicd-jenkins-prod-us-west
noc-monitoring-primary

# ACCEPTABLE - generic but organized
admin-workstation-1
client-webops-001

# BAD - not descriptive or auditable
client1
test
temp-client
```

#### `minions`

**Type**: List of strings
**Default**: `[]` (empty, no minion access)
**Required**: No

List of minion targeting patterns this client can target. This controls which minions a remote client can send commands to using the `salt` CLI.

**Pattern Types**:
- **Glob** (default): `'web*'`, `'db-[0-9]'`, `'app?'`
- **List**: Comma-separated in compound targets
- **Regex**: Use with compound matcher `E@`

**Values**:
- `['*']`: All minions
- `[]`: No minions (deny all)
- `['pattern1', 'pattern2']`: Multiple patterns (OR logic)

**Examples**:
```yaml
client_acl:
  # Access all minions
  full-access-client:
    minions: ['*']

  # Access specific minions
  web-client:
    minions: ['web-prod-1', 'web-prod-2']

  # Access by pattern
  webops-client:
    minions: ['web*', 'app*', 'lb*']

  # Access by environment
  dev-client:
    minions: ['dev-*']

  # No minion access (monitoring/runner only)
  monitoring-client:
    minions: []

  # Complex patterns
  multi-pattern-client:
    minions:
      - 'web-prod-*'
      - 'db-prod-[0-9]'
      - 'cache-*'

  # Geographic/datacenter restrictions
  datacenter-client:
    minions:
      - 'us-west-*'
      - 'us-east-*'

  # Role-based restrictions
  database-client:
    minions:
      - 'db-*'
      - 'postgres-*'
      - 'mysql-*'
      - 'redis-*'
```

**Pattern Matching Rules**:
- Patterns are glob-style by default
- `*` matches any number of characters
- `?` matches single character
- `[abc]` matches any character in brackets
- `[0-9]` matches any digit
- Patterns are OR'd together (match any pattern)

**Matching Examples**:

| Minion ID | Pattern | Matches? |
|-----------|---------|----------|
| `web-prod-1` | `web*` | Yes |
| `web-prod-1` | `web-prod-*` | Yes |
| `web-prod-1` | `web-*-1` | Yes |
| `web-prod-1` | `db*` | No |
| `app-staging-2` | `app-*-[0-9]` | Yes |
| `db-10` | `db-[0-9]` | No (two digits) |
| `db-10` | `db-*` | Yes |
| `test-minion` | `*-minion` | Yes |

**Security Notes**:
- Empty list `[]` denies all minion targeting (client can only run runners/wheel)
- Always use minimum necessary patterns (principle of least privilege)
- Consider separating production and non-production minions by pattern

#### `modules`

**Type**: List of strings
**Default**: `[]` (empty, no module access)
**Required**: No

List of execution module patterns this client can execute on minions. This controls which Salt execution modules can be invoked via the `salt` CLI on targeted minions.

**Format**: `<module>.<function>` or `<module>.*` or `*`

**Values**:
- `['*']`: All modules and functions
- `[]`: No execution modules (deny all)
- `['module.*']`: All functions in a module
- `['module.function']`: Specific function only

**Examples**:
```yaml
client_acl:
  # Full module access
  admin-client:
    modules: ['*']

  # Specific modules
  monitoring-client:
    modules:
      - 'test.ping'
      - 'test.version'
      - 'status.*'
      - 'grains.items'

  # Service management
  service-client:
    modules:
      - 'service.status'
      - 'service.start'
      - 'service.stop'
      - 'service.restart'

  # State application
  deploy-client:
    modules:
      - 'state.apply'
      - 'state.sls'
      - 'state.highstate'
      - 'saltutil.refresh_pillar'

  # Package management
  package-client:
    modules:
      - 'pkg.install'
      - 'pkg.remove'
      - 'pkg.upgrade'
      - 'pkg.list_upgrades'

  # File operations
  file-client:
    modules:
      - 'file.read'
      - 'file.write'
      - 'file.append'
      - 'file.remove'

  # Command execution (use with extreme caution)
  cmd-client:
    modules:
      - 'cmd.run'
      - 'cmd.script'
      - 'cmd.shell'

  # Database-specific operations
  database-client:
    modules:
      - 'postgres.*'
      - 'mysql.*'
      - 'redis.*'

  # Web server operations
  webops-client:
    modules:
      - 'apache.*'
      - 'nginx.*'
      - 'service.*'
      - 'pkg.*'

  # Read-only operations
  readonly-client:
    modules:
      - 'test.ping'
      - 'grains.items'
      - 'pillar.items'
      - 'status.*'
      - 'file.read'
```

**Common Module Patterns**:
- `test.*`: Testing and diagnostics (safe, read-only)
- `state.*`: State application (changes system)
- `service.*`: Service management (changes system)
- `pkg.*`: Package management (changes system)
- `file.*`: File operations (can change system)
- `cmd.*`: Command execution (dangerous, shell access)
- `grains.*`: Grains access (read-only)
- `pillar.*`: Pillar access (read-only)
- `saltutil.*`: Salt utility functions (various operations)
- `network.*`: Network diagnostics
- `disk.*`: Disk operations
- `user.*`: User management

**Module Pattern Matching Examples**:

| Module.Function | Pattern | Matches? |
|-----------------|---------|----------|
| `test.ping` | `test.*` | Yes |
| `test.ping` | `test.ping` | Yes |
| `test.ping` | `*.ping` | Yes |
| `test.version` | `test.ping` | No |
| `service.restart` | `service.*` | Yes |
| `pkg.install` | `service.*` | No |
| `cmd.run` | `*` | Yes |
| `state.apply` | `state.apply` | Yes |
| `state.sls` | `state.apply` | No |

**Combining Minions and Modules**:

Both `minions` and `modules` restrictions must be satisfied for a command to execute:

```yaml
client_acl:
  webops-client:
    minions: ['web*', 'app*']
    modules: ['service.*', 'state.apply']

# Allowed commands:
#   salt --client 'web-1' service.restart nginx      → ✓ web* minion, service.* module
#   salt --client 'app-2' state.apply webserver      → ✓ app* minion, state.apply module

# Denied commands:
#   salt --client 'db-1' service.restart postgresql  → ✗ db-1 not in minion patterns
#   salt --client 'web-1' pkg.install nginx          → ✗ pkg.install not in module patterns
#   salt --client 'db-1' pkg.install postgresql      → ✗ fails both checks
```

**Security Warnings**:
- `cmd.*` and `cmd.run` provide shell access - use with extreme caution
- `file.write` and `file.append` can modify any file on the system
- `user.*` can create/modify/delete system users
- `*` grants all module access - only for trusted admin workstations
- Empty list `[]` denies all module execution (minion targeting blocked)

**Best Practices**:
- Start with specific functions, expand to `module.*` only when needed
- Avoid `*` except for admin workstations
- Separate read-only operations from destructive operations
- Document why each module permission is needed

#### `runners`

**Type**: List of strings
**Default**: `[]` (empty, no runner access)
**Required**: No

List of runner module patterns this client can execute on the master.

**Format**: `<module>.<function>` or `<module>.*` or `*`

**Values**:
- `['*']`: All runners
- `[]`: No runner access
- `['runner.*']`: All functions in a runner
- `['runner.function']`: Specific runner only

**Examples**:
```yaml
client_acl:
  # Full runner access
  admin-client:
    runners: ['*']

  # Job management
  monitoring-client:
    runners:
      - 'jobs.list_jobs'
      - 'jobs.lookup_jid'
      - 'jobs.active'

  # State orchestration
  deploy-client:
    runners:
      - 'state.orchestrate'
      - 'state.orch'

  # Testing
  test-client:
    runners:
      - 'test.ping'
      - 'test.arg'

  # Cache management
  cache-client:
    runners:
      - 'cache.clear_all'
      - 'cache.grains'

  # Manage operations
  manage-client:
    runners:
      - 'manage.up'
      - 'manage.down'
      - 'manage.status'

  # No runner access
  minion-only-client:
    runners: []
```

**Common Runner Patterns**:
- `jobs.*`: Job management
- `state.orchestrate`: Orchestration
- `manage.*`: Minion management
- `cache.*`: Cache operations
- `test.*`: Testing
- `survey.*`: Survey operations

#### `wheel`

**Type**: List of strings
**Default**: `[]` (empty, no wheel access)
**Required**: No

List of wheel module patterns this client can execute (master-side operations, including key management).

**Format**: `<module>.<function>` or `<module>.*` or `*`

**Values**:
- `['*']`: All wheel functions (full master control)
- `[]`: No wheel access (recommended for most clients)
- `['wheel.*']`: All functions in a wheel module
- `['wheel.function']`: Specific function only

**Examples**:
```yaml
client_acl:
  # Full wheel access (master admin)
  master-admin-client:
    wheel: ['*']

  # Key management only
  key-admin-client:
    wheel:
      - 'key.list'
      - 'key.finger'
      - 'key.accept'
      - 'key.reject'
      - 'key.delete'

  # Read-only key viewing
  key-viewer-client:
    wheel:
      - 'key.list'
      - 'key.finger'
      - 'key.print'

  # Config operations
  config-client:
    wheel:
      - 'config.values'
      - 'config.get'

  # No wheel access (most clients)
  standard-client:
    wheel: []
```

**Common Wheel Patterns**:
- `key.*`: Minion key management
- `config.*`: Master configuration
- `file.*`: Master file operations
- `pillar.*`: Pillar management

**Security Warning**: Wheel functions provide master-level control. Most clients should have `wheel: []`.

## Publish ACL (Minion Targeting and Module Execution)

### Overview

Publish ACL controls what commands remote clients can execute on minions using the `salt` CLI. This involves two separate checks:

1. **Minion Targeting Check**: Is the client allowed to target these specific minions?
2. **Module Execution Check**: Is the client allowed to execute this specific module function?

Both checks must pass for the command to execute.

### Publish ACL Enforcement Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Remote Client Command                                       │
│ salt --client 'web-prod-1' service.restart nginx            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Client Authentication (PKI)                         │
│ - Verify client key is accepted                             │
│ - Load client ACL configuration                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Minion Targeting Check                              │
│ - Target: 'web-prod-1'                                      │
│ - Allowed patterns: ['web*', 'app*']                        │
│ - Match: 'web-prod-1' matches 'web*' → PASS                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Module Execution Check                              │
│ - Module: 'service.restart'                                 │
│ - Allowed patterns: ['service.*', 'state.apply']            │
│ - Match: 'service.restart' matches 'service.*' → PASS       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Execute Command on Minion                           │
│ - Publish command to minion 'web-prod-1'                    │
│ - Execute 'service.restart nginx'                           │
└─────────────────────────────────────────────────────────────┘
```

### Publish ACL Examples

#### Example 1: Web Operations Team

**Requirement**: Web team can manage web and app servers with service/state operations.

```yaml
client_acl:
  webops-workstation:
    minions:
      - 'web-*'
      - 'app-*'
      - 'lb-*'
    modules:
      - 'service.*'
      - 'state.apply'
      - 'state.sls'
      - 'pkg.install'
      - 'pkg.upgrade'
      - 'test.*'
```

**Allowed Operations**:
- `salt --client 'web-prod-1' service.restart nginx` → ✓ PASS (web-* + service.*)
- `salt --client 'app-*' state.apply webserver` → ✓ PASS (app-* + state.apply)
- `salt --client 'lb-1' pkg.install haproxy` → ✓ PASS (lb-* + pkg.install)

**Denied Operations**:
- `salt --client 'db-1' service.restart postgresql` → ✗ DENY (db-1 not in minions)
- `salt --client 'web-1' cmd.run 'rm -rf /'` → ✗ DENY (cmd.run not in modules)
- `salt --client 'web-1' postgres.db_create` → ✗ DENY (postgres.* not in modules)

#### Example 2: Database Team

**Requirement**: DBA team can manage database servers with database-specific operations.

```yaml
client_acl:
  dba-workstation:
    minions:
      - 'db-*'
      - 'postgres-*'
      - 'mysql-*'
      - 'redis-*'
    modules:
      - 'postgres.*'
      - 'mysql.*'
      - 'redis.*'
      - 'service.status'
      - 'service.restart'
      - 'file.read'
      - 'test.*'
```

**Allowed Operations**:
- `salt --client 'postgres-1' postgres.db_create mydb` → ✓ PASS
- `salt --client 'mysql-*' mysql.query 'SHOW DATABASES'` → ✓ PASS
- `salt --client 'redis-1' service.restart redis` → ✓ PASS
- `salt --client 'db-2' file.read /etc/postgresql/postgresql.conf` → ✓ PASS

**Denied Operations**:
- `salt --client 'web-1' postgres.db_create` → ✗ DENY (web-1 not in minions)
- `salt --client 'db-1' pkg.install` → ✗ DENY (pkg.install not in modules)
- `salt --client 'db-1' file.write` → ✗ DENY (file.write not in modules)

#### Example 3: Monitoring System

**Requirement**: Monitoring can check all systems but make no changes.

```yaml
client_acl:
  monitoring-client:
    minions: ['*']
    modules:
      - 'test.ping'
      - 'test.version'
      - 'status.*'
      - 'grains.items'
      - 'pillar.get'
      - 'service.status'
      - 'disk.usage'
      - 'network.interfaces'
```

**Allowed Operations**:
- `salt --client '*' test.ping` → ✓ PASS (all minions + test.ping)
- `salt --client 'web-*' status.uptime` → ✓ PASS (web-* matches * + status.*)
- `salt --client 'db-1' disk.usage` → ✓ PASS (* + disk.usage)

**Denied Operations**:
- `salt --client '*' service.restart` → ✗ DENY (service.restart not in modules)
- `salt --client '*' state.apply` → ✗ DENY (state.apply not in modules)
- `salt --client '*' cmd.run` → ✗ DENY (cmd.run not in modules)

#### Example 4: CI/CD Deployment

**Requirement**: CI/CD can deploy to app/web servers only.

```yaml
client_acl:
  cicd-jenkins-prod:
    minions:
      - 'app-prod-*'
      - 'web-prod-*'
    modules:
      - 'state.apply'
      - 'state.sls'
      - 'state.highstate'
      - 'saltutil.refresh_pillar'
      - 'git.pull'
      - 'service.restart'
      - 'test.ping'
```

**Allowed Operations**:
- `salt --client 'app-prod-*' state.apply myapp` → ✓ PASS
- `salt --client 'web-prod-1' git.pull /var/www/myapp` → ✓ PASS
- `salt --client 'app-prod-2' service.restart myapp` → ✓ PASS

**Denied Operations**:
- `salt --client 'app-staging-*' state.apply` → ✗ DENY (staging not in minions)
- `salt --client 'db-prod-1' state.apply` → ✗ DENY (db-prod not in minions)
- `salt --client 'app-prod-1' pkg.install` → ✗ DENY (pkg.install not in modules)

#### Example 5: Environment Separation

**Requirement**: Separate access for dev, staging, and production.

```yaml
client_acl:
  # Development - permissive
  dev-workstation:
    minions: ['dev-*']
    modules: ['*']  # All modules allowed in dev
    runners: ['*']
    wheel: []

  # Staging - moderate restrictions
  staging-workstation:
    minions: ['staging-*']
    modules:
      - 'state.*'
      - 'service.*'
      - 'pkg.*'
      - 'test.*'
      - 'grains.*'
      - 'pillar.*'
    runners: ['jobs.*', 'state.orchestrate']
    wheel: []

  # Production - strict restrictions
  prod-workstation:
    minions: ['prod-*']
    modules:
      - 'state.apply'
      - 'state.sls'
      - 'service.restart'
      - 'service.reload'
      - 'test.ping'
    runners: ['state.orchestrate', 'jobs.*']
    wheel: []
```

**Development Workstation**:
- `salt --client 'dev-web-1' cmd.run 'ls -la'` → ✓ PASS (dev-* + *)
- `salt --client 'dev-*' pkg.install` → ✓ PASS (dev-* + *)
- `salt --client 'staging-*' anything` → ✗ DENY (not dev-*)

**Staging Workstation**:
- `salt --client 'staging-app-1' state.apply` → ✓ PASS
- `salt --client 'staging-*' service.restart` → ✓ PASS
- `salt --client 'staging-1' cmd.run` → ✗ DENY (cmd.run not in modules)

**Production Workstation**:
- `salt --client 'prod-web-1' state.apply webserver` → ✓ PASS
- `salt --client 'prod-*' service.restart nginx` → ✓ PASS
- `salt --client 'prod-1' state.highstate` → ✗ DENY (state.highstate not allowed)
- `salt --client 'prod-1' pkg.install` → ✗ DENY (pkg.install not allowed)

### Publish ACL Security Considerations

#### Defense in Depth

Publish ACL is most effective when combined with minion-side controls:

```yaml
# Master side (client ACL)
client_acl:
  webops-client:
    minions: ['web*']
    modules: ['service.*', 'state.apply']

# Minion side (minion config)
# /etc/salt/minion on web-1
disable_modules:
  - cmd
  - file.write
```

**Result**: Even if client ACL is bypassed, minion refuses dangerous operations.

#### Common Attack Scenarios

**Scenario 1: Wildcard Bypass Attempt**
```yaml
# Misconfigured ACL
client_acl:
  client1:
    minions: ['web-*']  # Intended: web-prod-*
    modules: ['service.*']

# Attacker creates minion: 'web-malicious'
# salt --client 'web-malicious' service.* → ✓ PASS (unintended)
```
**Mitigation**: Use specific patterns, avoid overly broad wildcards.

**Scenario 2: Module Pattern Exploitation**
```yaml
# Misconfigured ACL
client_acl:
  client1:
    modules: ['*.*']  # Intended: specific modules

# Attacker uses:
# salt --client 'minion' cmd.run 'malicious command'
```
**Mitigation**: Never use `*.*` or `*`, list specific modules explicitly.

**Scenario 3: Cross-Environment Targeting**
```yaml
# Insufficient separation
client_acl:
  ops-client:
    minions: ['*']  # Intended: prod-*, allows dev-*, staging-*
    modules: ['state.apply']
```
**Mitigation**: Explicitly list environment prefixes, never use `*` for minions.

### Troubleshooting Publish ACL

#### Command Denied - Minion Check Failed

**Error Message**: "Minion targeting denied for client 'client-id'"

**Diagnosis**:
```bash
# Check client's minion patterns
salt-call --local config.get client_acl:client-id:minions

# List actual minion IDs
salt-key -L

# Verify pattern matching manually
# Pattern: 'web-*'
# Target: 'web-prod-1'
# Should match: Yes
```

**Solution**: Add or adjust minion patterns in ACL configuration.

#### Command Denied - Module Check Failed

**Error Message**: "Module execution denied for client 'client-id'"

**Diagnosis**:
```bash
# Check client's module patterns
salt-call --local config.get client_acl:client-id:modules

# Attempted module.function
# Example: service.restart
# Requires: 'service.restart' or 'service.*' or '*' in modules list
```

**Solution**: Add required module patterns to ACL configuration.

## Permission Matching Logic

### Pattern Evaluation

1. **Empty List**: `[]` denies all access
2. **Wildcard**: `['*']` allows all access
3. **Patterns**: List of patterns are OR'd (match any)
4. **Glob Syntax**: Standard shell glob patterns
5. **Case Sensitive**: Patterns are case-sensitive

### Match Algorithm

For each requested operation:

1. Load client's ACL configuration
2. Check if operation type has any allowed patterns
3. If empty list (`[]`), deny
4. If wildcard (`['*']`), allow
5. If patterns, check each pattern:
   - If any pattern matches, allow
   - If no pattern matches, deny

### Example Matching

```yaml
client_acl:
  example-client:
    minions: ['web*', 'db-[0-9]']
    modules: ['test.*', 'service.restart']
```

**Matching Examples**:

| Target | Matches | Result |
|--------|---------|--------|
| `web-1` | `web*` | Allow |
| `web-prod-1` | `web*` | Allow |
| `db-0` | `db-[0-9]` | Allow |
| `db-10` | `db-[0-9]` | Deny (10 is two digits) |
| `app-1` | (none) | Deny |

| Module | Matches | Result |
|--------|---------|--------|
| `test.ping` | `test.*` | Allow |
| `test.version` | `test.*` | Allow |
| `service.restart` | `service.restart` | Allow |
| `service.stop` | (none) | Deny |
| `pkg.install` | (none) | Deny |

## Whitelist vs Blacklist

Client ACL uses a **whitelist approach**:

- **Default Deny**: If not explicitly allowed, operation is denied
- **Explicit Allow**: Must be listed in ACL to be permitted
- **No Blacklist**: Cannot deny specific items (use narrow whitelists instead)

**Example**:
```yaml
# Correct: Whitelist specific operations
client_acl:
  client1:
    modules: ['test.ping', 'grains.items']
    # Everything else is implicitly denied

# Incorrect: Cannot blacklist
# This syntax is NOT supported:
client_acl:
  client1:
    modules_deny: ['cmd.run']  # NOT SUPPORTED
```

**To deny specific operations**, use narrow whitelists:
```yaml
# Want to allow all test.* except test.fib?
# Solution: List allowed functions explicitly
client_acl:
  client1:
    modules:
      - 'test.ping'
      - 'test.version'
      - 'test.kwarg'
      # test.fib not listed = denied
```

## Default Behavior

### No ACL Configuration

If `client_acl` is not defined:
```yaml
# /etc/salt/master
# (no client_acl section)
```

**Behavior**: All accepted clients have **full access** (backward compatible).

### Empty ACL Configuration

```yaml
client_acl: {}
```

**Behavior**: All accepted clients have **full access**.

### Client Not in ACL

```yaml
client_acl:
  known-client:
    minions: ['*']
    modules: ['*']
```

If client `unknown-client` authenticates:
**Behavior**: Full access (not restricted).

**Recommendation**: Define explicit empty permissions for maximum security:
```yaml
client_acl:
  default:  # Catch-all
    minions: []
    modules: []
    runners: []
    wheel: []
```

### Missing Permission Keys

```yaml
client_acl:
  client1:
    minions: ['*']
    # modules not specified
```

**Behavior**: Missing keys are treated as `[]` (deny all for that type).

## Integration with Other Auth Systems

### Client ACL + External Auth

Client ACL and eAuth can work together:

```yaml
# Client workstation authorization
client_acl:
  admin-workstation:
    minions: ['*']
    modules: ['*']
    runners: ['*']
    wheel: ['*']

# User authentication
external_auth:
  pam:
    alice:
      - '*':
          - 'state.*'
    bob:
      - 'web*':
          - 'service.*'
```

**Authentication Flow**:
1. Client workstation authenticates via client PKI key (client ACL check)
2. User authenticates via PAM/LDAP (eAuth check)
3. **Both must pass** for operation to succeed
4. Most restrictive wins

**Example**:
- `admin-workstation` (client ACL) allows `cmd.run` on all minions
- User `bob` (eAuth) only allows `service.*` on `web*`
- Result: `bob` on `admin-workstation` can only run `service.*` on `web*`

### Client ACL + Publisher ACL

Publisher ACL provides user-based restrictions on LocalClient:

```yaml
# User-based restrictions (publisher_acl)
publisher_acl:
  alice:
    - test.ping
    - network.*

# Workstation-based restrictions (client_acl)
client_acl:
  alice-laptop:
    minions: ['*']
    modules: ['*']
```

**Behavior**: Publisher ACL applies to local execution, client ACL applies to remote execution.

### Client ACL + Peer

Peer system allows minions to execute commands:

```yaml
# Minion-to-minion (peer)
peer:
  web-.*:
    - test.ping
    - grains.*

# Remote client (client_acl)
client_acl:
  admin-workstation:
    minions: ['*']
    modules: ['*']
```

**Behavior**: Completely separate systems. Peer controls minion-to-minion, client ACL controls client-to-minion.

## Configuration Validation

### Syntax Validation

Validate master configuration syntax:

```bash
# Python validation
python3 -c "import yaml; yaml.safe_load(open('/etc/salt/master'))"

# Salt validation
salt-call --local config.valid

# Check specific config value
salt-call --local config.get client_acl
```

### Testing ACL Configuration

**Step 1**: Dry-run configuration reload
```bash
# Check for syntax errors
salt-master --config-dir=/etc/salt --log-level=debug --test-config
```

**Step 2**: Test pattern matching
```bash
# Test minion targeting
salt --client 'pattern' test.ping

# Test module execution
salt --client 'minion-id' module.function
```

**Step 3**: Verify ACL enforcement
```bash
# Should succeed
salt --client 'allowed-target' allowed.module

# Should fail
salt --client 'denied-target' allowed.module
salt --client 'allowed-target' denied.module
```

### Common Configuration Errors

#### Error 1: Client ID Mismatch

```yaml
# Config
client_acl:
  admin-workstation:
    minions: ['*']

# Key ID: admin-workstation-1
# Result: No ACL match, full access (default behavior)
```

**Fix**: Ensure client ID in config matches key ID exactly.

#### Error 2: YAML Syntax Error

```yaml
# Incorrect indentation
client_acl:
admin-workstation:  # Wrong indent
  minions: ['*']
```

**Fix**: Use consistent 2-space indentation.

#### Error 3: Pattern Typo

```yaml
client_acl:
  client1:
    minions: ['web*']
    modules: ['test,*']  # Comma instead of period
```

**Fix**: Use `test.*` not `test,*`.

#### Error 4: List vs String

```yaml
# Incorrect: String instead of list
client_acl:
  client1:
    minions: 'web*'  # Wrong

# Correct: List
client_acl:
  client1:
    minions: ['web*']  # Correct
```

## Performance Considerations

### Configuration Size

- **Small**: < 50 clients, < 100 patterns per client
  - No performance impact

- **Medium**: 50-200 clients, < 500 patterns per client
  - Minimal performance impact (< 1ms per auth)

- **Large**: > 200 clients or > 1000 patterns per client
  - Consider optimization strategies

### Optimization Strategies

**1. Use Broad Patterns**
```yaml
# Less optimal: Many specific patterns
minions:
  - 'web-prod-1'
  - 'web-prod-2'
  - 'web-prod-3'
  # ... 100 more

# More optimal: Single pattern
minions: ['web-prod-*']
```

**2. Group Similar Clients**
```yaml
# Less optimal: Duplicate configs
client_acl:
  webops-1:
    minions: ['web*']
    modules: ['service.*']
  webops-2:
    minions: ['web*']
    modules: ['service.*']

# More optimal: Shared configuration (use naming convention)
client_acl:
  'webops-*':  # All webops clients
    minions: ['web*']
    modules: ['service.*']
```

**Note**: Pattern matching in client IDs is not currently supported. This is a conceptual example for future enhancement.

**3. Avoid Overlapping Patterns**
```yaml
# Less optimal: Overlapping patterns
minions: ['web*', 'web-prod-*', 'web-prod-1']

# More optimal: Single pattern covers all
minions: ['web*']
```

### Caching

Client ACL configuration is loaded at master startup and cached in memory:

- **Configuration Reload**: Requires master restart/reload
- **No Runtime Overhead**: ACL checks are in-memory pattern matching
- **Key Cache**: Client keys cached separately (see `key_cache` master option)

## Configuration File Organization

### Single File Approach

```yaml
# /etc/salt/master
client_acl_verify: False
client_acl:
  admin-workstation:
    minions: ['*']
    modules: ['*']
    runners: ['*']
    wheel: ['*']

  monitoring-client:
    minions: ['*']
    modules: ['test.ping', 'status.*']
    runners: ['jobs.*']
    wheel: []
```

**Pros**: Simple, all in one place
**Cons**: Large file, harder to manage

### Drop-in Directory Approach (Recommended)

```yaml
# /etc/salt/master
# (no client_acl section)

# /etc/salt/master.d/client_acl_verify.conf
client_acl_verify: False

# /etc/salt/master.d/client_acl_admin.conf
client_acl:
  admin-workstation-1:
    minions: ['*']
    modules: ['*']
    runners: ['*']
    wheel: ['*']

# /etc/salt/master.d/client_acl_monitoring.conf
client_acl:
  noc-monitoring-primary:
    minions: ['*']
    modules: ['test.ping', 'status.*']
    runners: ['jobs.*']
    wheel: []

# /etc/salt/master.d/client_acl_webops.conf
client_acl:
  webops-workstation:
    minions: ['web*', 'app*']
    modules: ['service.*', 'state.*']
    runners: ['state.orchestrate']
    wheel: []
```

**Pros**: Organized, easier to manage, version control friendly
**Cons**: Multiple files to track

**Note**: Salt merges all `client_acl` sections from all config files.

### Environment-Based Organization

```yaml
# /etc/salt/master.d/client_acl_prod.conf
client_acl:
  prod-admin:
    minions: ['prod-*']
    modules: ['state.*', 'service.*']

# /etc/salt/master.d/client_acl_dev.conf
client_acl:
  dev-admin:
    minions: ['dev-*']
    modules: ['*']  # More permissive for dev
```

### Role-Based Organization

```yaml
# /etc/salt/master.d/client_acl_role_admin.conf
client_acl:
  admin-workstation-1:
    minions: ['*']
    modules: ['*']

# /etc/salt/master.d/client_acl_role_deploy.conf
client_acl:
  cicd-jenkins-prod:
    minions: ['app-*', 'web-*']
    modules: ['state.*', 'git.*']

# /etc/salt/master.d/client_acl_role_monitor.conf
client_acl:
  noc-monitoring:
    minions: ['*']
    modules: ['test.ping', 'status.*']
```

## Migration and Versioning

### Version Compatibility

- **Salt 3009+**: Client ACL feature introduced (planned)
- **Salt 3008.x**: Not available
- **Backward Compatibility**: Disabled by default (opt-in)

### Migration from No ACL

**Phase 1**: Inventory current clients
```bash
# List all accepted client keys
salt-key --client -L
```

**Phase 2**: Create ACL configuration
```yaml
# Start with current state (full access)
client_acl:
  admin-workstation:
    minions: ['*']
    modules: ['*']
    runners: ['*']
    wheel: ['*']
```

**Phase 3**: Gradually restrict
```yaml
# Narrow permissions over time
client_acl:
  admin-workstation:
    minions: ['*']
    modules: ['state.*', 'service.*', 'test.*']
    runners: ['jobs.*']
    wheel: ['key.list', 'key.finger']
```

**Phase 4**: Add new restricted clients
```yaml
client_acl:
  new-monitoring-client:
    minions: ['*']
    modules: ['test.ping', 'status.*']
    runners: []
    wheel: []
```

## Security Model

### Defense in Depth

Client ACL is one layer in Salt's security model:

```
┌─────────────────────────────────────┐
│ Network Firewall                    │
│ (Port 4506 restricted)              │
├─────────────────────────────────────┤
│ Client PKI Authentication           │
│ (Client key must be accepted)       │
├─────────────────────────────────────┤
│ Client ACL Authorization ←── THIS   │
│ (Workstation-based permissions)     │
├─────────────────────────────────────┤
│ External Auth (eAuth)               │
│ (User-based permissions)            │
├─────────────────────────────────────┤
│ Publisher ACL                       │
│ (Additional user restrictions)      │
├─────────────────────────────────────┤
│ Minion ACL / Execution              │
│ (Minion-side controls)              │
└─────────────────────────────────────┘
```

### Trust Model

**Assumptions**:
- Master configuration is trusted and protected
- Client private keys are protected on client workstations
- Network between client and master is assumed hostile (use TLS)
- Client IDs are meaningful and tracked

**Not Protected Against**:
- Compromised client private key (revoke key immediately)
- Malicious master configuration (protect master config)
- Network-level attacks on master (use firewall)

## Complete Configuration Example

```yaml
# /etc/salt/master or /etc/salt/master.d/client_acl.conf

# Verification settings
client_acl_verify: False

# Client ACL configuration
client_acl:
  # Master administrator workstation
  admin-primary-workstation:
    minions: ['*']
    modules: ['*']
    runners: ['*']
    wheel: ['*']

  # Secondary administrator (limited wheel access)
  admin-secondary-workstation:
    minions: ['*']
    modules: ['*']
    runners: ['*']
    wheel: ['key.list', 'key.finger', 'key.print']

  # Web operations team
  webops-workstation:
    minions: ['web-*', 'app-*', 'lb-*']
    modules:
      - 'state.*'
      - 'service.*'
      - 'pkg.install'
      - 'pkg.upgrade'
      - 'test.*'
      - 'cmd.run'
    runners:
      - 'state.orchestrate'
      - 'jobs.*'
    wheel: []

  # Database operations team
  dba-workstation:
    minions: ['db-*', 'postgres-*', 'mysql-*']
    modules:
      - 'postgres.*'
      - 'mysql.*'
      - 'service.status'
      - 'service.restart'
      - 'test.*'
    runners: ['jobs.*']
    wheel: []

  # CI/CD deployment system
  cicd-jenkins-prod:
    minions: ['app-*', 'web-*']
    modules:
      - 'state.apply'
      - 'state.sls'
      - 'saltutil.refresh_pillar'
      - 'git.pull'
      - 'test.ping'
    runners:
      - 'state.orchestrate'
      - 'jobs.lookup_jid'
    wheel: []

  # Monitoring system
  noc-monitoring-primary:
    minions: ['*']
    modules:
      - 'test.ping'
      - 'test.version'
      - 'status.*'
      - 'grains.items'
      - 'saltutil.find_job'
    runners:
      - 'jobs.list_jobs'
      - 'jobs.lookup_jid'
      - 'manage.up'
      - 'manage.down'
    wheel: []

  # Read-only audit workstation
  audit-workstation:
    minions: ['*']
    modules:
      - 'test.ping'
      - 'grains.items'
    runners:
      - 'jobs.list_jobs'
    wheel: ['key.list', 'key.finger']

  # Development workstation
  dev-workstation-alice:
    minions: ['dev-*', 'test-*']
    modules: ['*']
    runners: ['*']
    wheel: []

  # Emergency access (normally rejected)
  emergency-break-glass:
    minions: ['*']
    modules: ['*']
    runners: ['*']
    wheel: ['*']
```

## See Also

- [REMOTE_CLI_ACL_GUIDE.md](REMOTE_CLI_ACL_GUIDE.md) - User guide with use cases and examples
- [Salt Configuration Reference](https://docs.saltproject.io/en/latest/ref/configuration/master.html)
- [Salt Publisher ACL](https://docs.saltproject.io/en/latest/ref/publisheracl.html)
- [Salt External Authentication](https://docs.saltproject.io/en/latest/topics/eauth/index.html)
