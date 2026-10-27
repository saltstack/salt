# Remote CLI Access Control (ACL) Guide

## Overview

The Remote CLI ACL system provides granular access control for Salt remote CLI clients (salt, salt-run, salt-key) that connect to the Salt master from remote workstations. This allows administrators to grant specific permissions to different client machines, enabling secure delegation of Salt operations across teams and locations.

Unlike traditional Salt access control which is user-based (external_auth/eAuth), client ACLs are workstation-based and tied to client PKI keys. This provides an additional layer of security by controlling which physical machines can execute which operations, independent of the user running the command.

## Key Concepts

### Client Authentication

Remote CLI clients authenticate using PKI keys similar to minions, but with a separate key namespace:
- **Client keys** are stored separately from minion keys
- **Client IDs** identify specific workstations (e.g., "admin-workstation-1")
- **Client roles** are identified by `__role="client"` in authentication payloads
- **Manual acceptance** - client keys must be manually accepted on the master (no auto-accept)

### ACL Scope

Client ACLs control four types of operations:
1. **Minion targeting** (`salt` command) - which minions can be targeted for execution
2. **Module execution** (`salt` command) - which execution modules can run on targeted minions
3. **Runner execution** (`salt-run` command) - which runner modules can execute
4. **Wheel operations** (`salt-key` command) - which wheel functions for master management

### ACL vs eAuth

| Feature | Client ACL | External Auth (eAuth) |
|---------|-----------|---------------------|
| **Authentication basis** | PKI keys tied to workstation | User credentials (PAM, LDAP, etc) |
| **Granularity** | Per-workstation | Per-user |
| **Use case** | Control which machines can execute commands | Control which users can execute commands |
| **Acceptance** | Manual key acceptance | Credential validation |
| **Typical deployment** | Physical workstation security | User-based permissions |

**Best Practice**: Use both together - eAuth for user authentication and client ACL for workstation authorization.

## Configuration

### Master Configuration

Client ACLs are configured in the Salt master configuration file (`/etc/salt/master` or `master.d/*.conf`).

#### Basic Structure

```yaml
client_acl:
  <client-id>:
    minions: [<minion-patterns>]
    modules: [<module-patterns>]
    runners: [<runner-patterns>]
    wheel: [<wheel-patterns>]
```

#### Configuration Options

- **client_acl**: Dictionary mapping client IDs to their permissions
- **client_acl_verify**: Boolean (default: True) - verify client IDs against system users
- **minions**: List of minion targeting patterns (glob, regex, etc)
- **modules**: List of execution module patterns allowed on minions
- **runners**: List of runner module patterns allowed
- **wheel**: List of wheel function patterns allowed

### Pattern Matching

All ACL patterns support glob-style wildcards:
- `*` - matches any characters
- `?` - matches single character
- `test.*` - matches all functions in test module
- `*.ping` - matches ping function in any module
- `[]` - character ranges (e.g., `web[0-9]`)

## Use Cases and Examples

### Use Case 1: Full Administrator Workstation

**Scenario**: Main administrator workstation needs unrestricted access to all operations.

```yaml
client_acl:
  admin-primary-workstation:
    minions: ['*']
    modules: ['*']
    runners: ['*']
    wheel: ['*']
```

**Security Note**: Use this sparingly. Even admin workstations should have restrictions if possible.

### Use Case 2: Read-Only Monitoring Client

**Scenario**: NOC monitoring system needs to check minion status but not make changes.

```yaml
client_acl:
  noc-monitoring-client:
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
      - 'test.ping'
    wheel: []  # No wheel access
```

### Use Case 3: Web Server Management Client

**Scenario**: Dedicated workstation for managing web servers only.

```yaml
client_acl:
  webops-workstation:
    minions:
      - 'web*'
      - 'app*'
      - 'lb*'
    modules:
      - 'service.*'
      - 'pkg.install'
      - 'pkg.remove'
      - 'pkg.list_upgrades'
      - 'cmd.run'
      - 'state.apply'
      - 'test.*'
    runners:
      - 'state.orchestrate'
      - 'jobs.*'
    wheel:
      - 'key.list'
      - 'key.finger'
```

**Operations Allowed**:
- `salt --client 'web-prod-1' service.restart nginx` - ✓ Allowed (web* minion, service.* module)
- `salt --client 'app*' state.apply webserver` - ✓ Allowed (app* minion, state.apply module)
- `salt --client 'db-1' service.restart postgresql` - ✗ Denied (db-1 not in minion patterns)
- `salt --client 'web*' postgres.user_create` - ✗ Denied (postgres.* not in module patterns)

### Use Case 4: Database Team Client

**Scenario**: Database team needs access to database servers only.

```yaml
client_acl:
  dba-workstation:
    minions:
      - 'db-*'
      - 'postgres-*'
      - 'mysql-*'
    modules:
      - 'postgres.*'
      - 'mysql.*'
      - 'service.status'
      - 'service.restart'
      - 'cmd.run'
      - 'file.read'
      - 'file.write'
      - 'test.*'
    runners:
      - 'jobs.*'
    wheel: []
```

**Operations Allowed**:
- `salt --client 'db-prod-1' postgres.db_create mydb` - ✓ Allowed (db-* minion, postgres.* module)
- `salt --client 'mysql-*' mysql.query 'SHOW DATABASES'` - ✓ Allowed (mysql-* minion, mysql.* module)
- `salt --client 'postgres-1' service.restart postgresql` - ✓ Allowed (postgres-* minion, service.restart module)
- `salt --client 'web-1' postgres.db_create` - ✗ Denied (web-1 not in minion patterns)
- `salt --client 'db-1' pkg.install` - ✗ Denied (pkg.install not in module patterns)

### Use Case 5: Emergency Access Workstation

**Scenario**: Break-glass emergency access with full permissions, logged separately.

```yaml
client_acl:
  emergency-access-workstation:
    minions: ['*']
    modules: ['*']
    runners: ['*']
    wheel: ['*']
```

**Operational Note**: Keep this client key rejected by default. Only accept during emergencies, then reject immediately after.

### Use Case 6: CI/CD Pipeline Client

**Scenario**: Continuous deployment system needs to deploy application code.

```yaml
client_acl:
  cicd-deploy-client:
    minions:
      - 'app-*'
      - 'web-*'
    modules:
      - 'state.apply'
      - 'state.sls'
      - 'test.ping'
      - 'saltutil.refresh_pillar'
      - 'git.pull'
    runners:
      - 'state.orchestrate'
      - 'jobs.lookup_jid'
    wheel: []
```

### Use Case 7: Multi-Environment Separation

**Scenario**: Separate workstations for dev, staging, and production environments.

```yaml
client_acl:
  dev-ops-workstation:
    minions: ['dev-*']
    modules: ['*']
    runners: ['*']
    wheel: ['key.*']

  staging-ops-workstation:
    minions: ['staging-*']
    modules:
      - '*'
    runners:
      - '*'
    wheel:
      - 'key.list'
      - 'key.finger'

  prod-ops-workstation:
    minions: ['prod-*']
    modules:
      - 'state.apply'
      - 'test.*'
      - 'service.*'
      - 'pkg.*'
    runners:
      - 'state.orchestrate'
      - 'jobs.*'
    wheel: []
```

### Use Case 8: Restricted Developer Workstation

**Scenario**: Developer needs to test states on development minions only.

```yaml
client_acl:
  developer-workstation-alice:
    minions:
      - 'dev-*'
      - 'test-*'
    modules:
      - 'state.apply'
      - 'state.sls'
      - 'state.highstate'
      - 'test.*'
      - 'grains.*'
      - 'pillar.*'
    runners:
      - 'state.orchestrate'
    wheel: []
```

## Client Key Management

### Generating Client Keys

On the client workstation:

```bash
# Option 1: Using salt-key with --gen-keys
salt-key --gen-keys=admin-workstation-1 --gen-keys-dir=/etc/salt/pki/client

# Option 2: Using Python
python3 -c "import salt.crypt; salt.crypt.gen_keys('/etc/salt/pki/client', 'client', 4096)"
```

### Registering Client Keys

**Method 1: Manual file placement** (not recommended for remote clients)
```bash
# Copy client public key to master
scp /etc/salt/pki/client/client.pub master:/tmp/admin-workstation-1.pub

# On master, accept the key
salt-key --client --accept admin-workstation-1
```

**Method 2: Using cache API** (preferred for remote clients)
```python
import salt.key
import salt.config

opts = salt.config.master_config('/etc/salt/master')
with salt.key.ClientKey(opts) as ckey:
    ckey.cache.store(
        'client_keys',
        'admin-workstation-1',
        {'pub': public_key_data, 'state': 'pending'}
    )
```

### Accepting Client Keys

```bash
# List pending client keys
salt-key --client -L

# Accept specific client
salt-key --client --accept admin-workstation-1

# Accept multiple clients
salt-key --client --accept admin-workstation-*

# Accept all pending clients (use with caution)
salt-key --client --accept-all
```

### Rejecting Client Keys

```bash
# Reject pending client
salt-key --client --reject compromised-workstation

# Reject accepted client (requires --include-accepted)
salt-key --client --reject admin-workstation-1 --include-accepted

# Reject all clients matching pattern
salt-key --client --reject 'temp-*' --include-accepted
```

### Deleting Client Keys

```bash
# Delete specific client
salt-key --client --delete admin-workstation-1

# Delete multiple clients
salt-key --client --delete 'old-*'
```

### Viewing Client Keys

```bash
# List all client keys by state
salt-key --client -L

# View client key fingerprint
salt-key --client --finger admin-workstation-1

# Print client public key
salt-key --client --print admin-workstation-1
```

## Granting and Revoking Permissions

### Granting New Permissions

1. **Update master configuration** with new ACL rules:
```yaml
client_acl:
  new-workstation:
    minions: ['web*']
    modules: ['service.*', 'test.*']
    runners: ['jobs.*']
    wheel: []
```

2. **Restart or reload master**:
```bash
systemctl restart salt-master
# OR
salt-call service.restart salt-master
```

3. **Accept client key**:
```bash
salt-key --client --accept new-workstation
```

### Modifying Existing Permissions

1. **Edit master configuration**
2. **Restart master** to load new ACL rules
3. **No need to re-accept keys** - existing accepted keys continue working

### Revoking Permissions

**Temporary revocation** (reject key):
```bash
salt-key --client --reject compromised-workstation --include-accepted
```

**Permanent revocation** (delete key):
```bash
salt-key --client --delete compromised-workstation
```

**Emergency: Revoke all access for a client**:
```yaml
client_acl:
  compromised-workstation:
    minions: []
    modules: []
    runners: []
    wheel: []
```
Then restart master and reject the key.

## Troubleshooting

### Access Denied Errors

**Symptom**: Client receives "Authorization error occurred" when executing commands.

**Diagnosis**:
1. Check client key is accepted:
   ```bash
   salt-key --client -L
   ```

2. Verify client ID in ACL configuration:
   ```bash
   grep -A5 "client-id" /etc/salt/master
   ```

3. Check master logs for ACL denials:
   ```bash
   tail -f /var/log/salt/master | grep -i acl
   ```

**Resolution**:
- Ensure client ID in configuration matches key ID exactly
- Verify ACL patterns include required modules/minions
- Restart master after configuration changes

### Minion Targeting Denied

**Symptom**: Client receives "Minion targeting denied" or "No minions matched the target" when targeting specific minions.

**Diagnosis**:
1. Check minion patterns in ACL config:
   ```bash
   salt-call --local config.get client_acl
   ```

2. Test pattern matching:
   ```bash
   # List actual minion IDs
   salt-key -L

   # Verify client's target matches allowed patterns
   # Pattern: 'web*'  Target: 'web-prod-1'  → Should match
   # Pattern: 'db-[0-9]'  Target: 'db-10'  → Won't match (two digits)
   ```

3. Check master logs:
   ```bash
   grep "Minion targeting denied" /var/log/salt/master
   ```

**Resolution**:
- Update `minions` list in ACL configuration to include required patterns
- Use broader patterns if needed (e.g., `'web*'` instead of `'web-prod-*'`)
- Test patterns with `salt-key -L` to verify minion IDs match expectations

### Module Execution Denied

**Symptom**: Client receives "Module execution denied" or "Command not permitted" when running execution modules.

**Diagnosis**:
1. Check module patterns in ACL config:
   ```bash
   salt-call --local config.get client_acl:<client-id>:modules
   ```

2. Verify exact module.function format:
   ```bash
   # Attempting: salt --client 'minion' service.restart nginx
   # Requires: 'service.restart' or 'service.*' in modules list
   ```

3. Check master logs for denied operations:
   ```bash
   grep "Module execution denied" /var/log/salt/master | tail -20
   ```

**Resolution**:
- Add required module patterns to `modules` list in ACL config
- Use `module.*` for all functions in a module
- Remember: `cmd.run` requires explicit permission (security sensitive)
- Restart master after configuration changes

**Common Module Denial Examples**:
```yaml
# Client attempts: salt --client 'web-1' pkg.install nginx
# ACL config has: modules: ['service.*', 'test.*']
# Result: DENIED (pkg.install not in modules list)

# Fix: Add pkg module
client_acl:
  client-id:
    modules:
      - 'service.*'
      - 'test.*'
      - 'pkg.*'  # Added
```

### Client Key Not Accepted

**Symptom**: Client key appears in pending but won't accept.

**Diagnosis**:
```bash
# Check key state
salt-key --client -L

# View fingerprint
salt-key --client --finger client-id

# Check master logs
journalctl -u salt-master -f
```

**Resolution**:
- Verify key file permissions (0400 for private, 0644 for public)
- Check client ID doesn't conflict with minion ID
- Ensure cache directory writable: `/var/cache/salt/master/`

### Authentication Failures

**Symptom**: Client cannot authenticate with master.

**Diagnosis**:
1. Verify client configuration:
   ```bash
   salt-call --client --local config.get master
   salt-call --client --local config.get id
   ```

2. Check network connectivity:
   ```bash
   telnet master-host 4506
   ```

3. Verify client keys exist:
   ```bash
   ls -l /etc/salt/pki/client/
   ```

**Resolution**:
- Ensure master hostname/IP is correct in client config
- Verify firewall allows port 4506
- Check client private key is readable by user running salt commands

### Permission Denied After Restart

**Symptom**: Client worked before master restart, now denied.

**Diagnosis**:
- Check if ACL configuration was modified
- Verify master loaded correct configuration file

**Resolution**:
```bash
# Verify master is using correct config
salt-call --local config.get file_roots

# Check for config syntax errors
salt-call --local config.valid

# Review master config includes
ls -la /etc/salt/master.d/
```

### Wildcard Patterns Not Matching

**Symptom**: Pattern like `web*` not matching expected minions.

**Diagnosis**:
Test pattern matching:
```bash
salt --client 'web*' test.ping
```

**Resolution**:
- Remember patterns are glob-style, not regex
- For regex patterns, use compound matching: `E@web.*`
- Check minion IDs match expected pattern

## Security Best Practices

### 1. Principle of Least Privilege

Grant only the minimum permissions required:
```yaml
# BAD - overly permissive
client_acl:
  monitoring-client:
    minions: ['*']
    modules: ['*']

# GOOD - minimal permissions
client_acl:
  monitoring-client:
    minions: ['*']
    modules: ['test.ping', 'status.uptime']
```

### 2. Separate Environments

Use different client workstations for different environments:
```yaml
client_acl:
  prod-admin:
    minions: ['prod-*']
    # Production-specific restrictions

  dev-admin:
    minions: ['dev-*']
    # More permissive for development
```

### 3. Audit and Logging

Enable comprehensive logging:
```yaml
# In master config
log_level: info
log_file: /var/log/salt/master

# Log all client authentications
log_granular_levels:
  'salt.master': debug
  'salt.auth': debug
```

### 4. Regular Key Rotation

Periodically rotate client keys:
```bash
# Generate new keys
salt-key --gen-keys=admin-workstation-2

# Accept new key
salt-key --client --accept admin-workstation-2

# Test new key works
salt --client 'test.ping'

# Delete old key
salt-key --client --delete admin-workstation-1
```

### 5. Emergency Revocation Procedures

Document and test emergency key revocation:
```bash
#!/bin/bash
# emergency-revoke.sh
CLIENT_ID=$1
salt-key --client --reject $CLIENT_ID --include-accepted -y
echo "Client $CLIENT_ID access revoked"
```

### 6. Protect Client Private Keys

On client workstations:
```bash
# Secure permissions
chmod 400 /etc/salt/pki/client/client.pem
chown root:root /etc/salt/pki/client/client.pem

# Consider encrypted storage
# Use TPM or HSM for high-security environments
```

### 7. Network Segmentation

Restrict master access at network level:
```bash
# Firewall: only allow specific client IPs
iptables -A INPUT -p tcp --dport 4506 -s 10.0.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 4506 -j DROP
```

### 8. Monitoring and Alerting

Monitor for suspicious activity:
```yaml
# Alert on unusual client activity
# Use beacons or returners to track:
# - Failed authentication attempts
# - Commands from unexpected clients
# - Access to sensitive minions
```

### 9. Client ID Naming Convention

Use descriptive, auditable client IDs:
```yaml
# GOOD naming
client_acl:
  admin-alice-laptop-2024:
  cicd-jenkins-prod:
  noc-monitoring-primary:

# BAD naming
client_acl:
  client1:
  test:
  temp:
```

### 10. Configuration Management

Version control your ACL configuration:
```bash
# Store master config in git
cd /etc/salt
git add master.d/client_acl.conf
git commit -m "Add monitoring client ACL"
git push
```

## Integration with External Auth

Client ACL and external auth (eAuth) can be used together for defense in depth:

```yaml
# Master config combining both
client_acl:
  admin-workstation:
    minions: ['*']
    modules: ['*']
    runners: ['*']
    wheel: ['*']

external_auth:
  pam:
    alice:
      - '*':
          - 'state.*'
          - 'cmd.run'
    bob:
      - 'web*':
          - 'service.*'
```

**Authentication flow**:
1. Client workstation authenticates via PKI (client ACL check)
2. User authenticates via PAM/LDAP (eAuth check)
3. Both must pass for command to execute

**Usage**:
```bash
# User must authenticate even on authorized workstation
salt --client -a pam 'web*' service.restart nginx
# Enter password for alice: ********
```

## Migration and Compatibility

### Backward Compatibility

Client ACL is **opt-in**:
- If `client_acl` is not configured, all accepted clients have full access
- Existing eAuth configurations continue to work
- No changes required to minion configurations

### Migrating from eAuth to Client ACL

**Step 1**: Document current eAuth permissions
```bash
grep -A20 "external_auth:" /etc/salt/master
```

**Step 2**: Create equivalent client ACL rules
```yaml
# Old eAuth
external_auth:
  pam:
    webops:
      - 'web*':
          - 'service.*'

# New client ACL
client_acl:
  webops-workstation:
    minions: ['web*']
    modules: ['service.*']
```

**Step 3**: Test in parallel
- Keep eAuth enabled
- Add client ACL for new clients
- Verify both work correctly

**Step 4**: Gradual migration
- Migrate low-risk clients first
- Monitor for issues
- Migrate critical clients last

## Advanced Configuration

### Dynamic ACL Updates

For dynamic environments, consider using Salt reactor patterns:
```yaml
# /etc/salt/master.d/reactor.conf
reactor:
  - 'salt/client/request':
    - /srv/reactor/approve_client.sls
```

```yaml
# /srv/reactor/approve_client.sls
{% if data['client_id'].startswith('approved-') %}
approve_client:
  wheel.key.accept:
    - args:
      - match: {{ data['client_id'] }}
      - client: True
{% endif %}
```

### Conditional ACLs Based on Time

While not natively supported, you can use cron to rotate ACL configs:
```bash
# /etc/cron.d/salt-acl-rotation
0 9 * * * root cp /etc/salt/acl-business-hours.conf /etc/salt/master.d/client_acl.conf && systemctl reload salt-master
0 17 * * * root cp /etc/salt/acl-restricted.conf /etc/salt/master.d/client_acl.conf && systemctl reload salt-master
```

### Per-Client Logging

Configure separate log files per client:
```yaml
# Master config
log_granular_levels:
  'salt.master.client.admin-workstation': debug
```

## Publish ACL Deep Dive

### Understanding Publish ACL

Publish ACL controls what commands remote clients can execute on minions via the `salt` CLI. This is the most frequently used ACL type and requires understanding two separate but related restrictions:

1. **Minion Targeting (`minions`)**: Which minions can the client send commands to?
2. **Module Execution (`modules`)**: Which execution modules can the client run on those minions?

Both restrictions must pass for a command to execute.

### Publish ACL Examples by Role

#### Example 1: Web Operations Team

**Requirements**:
- Manage web servers, application servers, and load balancers
- Deploy applications via state.apply
- Manage services (nginx, apache, etc.)
- Install/upgrade packages
- No access to database or other infrastructure

```yaml
client_acl:
  webops-team-workstation:
    # Minion targeting: web infrastructure only
    minions:
      - 'web-*'          # All web servers
      - 'app-*'          # All application servers
      - 'lb-*'           # All load balancers
      - 'nginx-*'        # Nginx-specific servers
      - 'apache-*'       # Apache-specific servers

    # Module execution: deployment and service management
    modules:
      - 'state.apply'
      - 'state.sls'
      - 'service.*'      # All service operations
      - 'pkg.install'
      - 'pkg.upgrade'
      - 'pkg.remove'
      - 'test.*'         # Testing and diagnostics
      - 'grains.items'   # System information
      - 'saltutil.refresh_pillar'

    # Runner access: orchestration and job management
    runners:
      - 'state.orchestrate'
      - 'jobs.*'

    # No wheel access
    wheel: []
```

**What's Allowed**:
```bash
# Deploy web application
salt --client 'web-prod-*' state.apply webserver.nginx

# Restart services
salt --client 'web-*' service.restart nginx
salt --client 'app-*' service.reload myapp

# Update packages
salt --client 'web-prod-1' pkg.upgrade nginx

# Test connectivity
salt --client 'web-*' test.ping

# Orchestrate deployment
salt-run --client state.orchestrate deploy.webserver
```

**What's Denied**:
```bash
# Cannot target database servers
salt --client 'db-*' service.restart postgresql
# Error: Minion targeting denied

# Cannot execute commands
salt --client 'web-*' cmd.run 'whoami'
# Error: Module execution denied

# Cannot manage users
salt --client 'web-*' user.add hacker
# Error: Module execution denied

# Cannot write files arbitrarily
salt --client 'web-*' file.write /etc/passwd malicious
# Error: Module execution denied
```

#### Example 2: Database Administration Team

**Requirements**:
- Manage database servers only
- Execute database-specific operations
- Monitor database services
- No access to web or application infrastructure

```yaml
client_acl:
  dba-team-workstation:
    # Minion targeting: database infrastructure only
    minions:
      - 'db-*'           # Generic database servers
      - 'postgres-*'     # PostgreSQL servers
      - 'mysql-*'        # MySQL servers
      - 'redis-*'        # Redis servers
      - 'mongo-*'        # MongoDB servers

    # Module execution: database operations
    modules:
      - 'postgres.*'     # All PostgreSQL operations
      - 'mysql.*'        # All MySQL operations
      - 'redis.*'        # All Redis operations
      - 'mongodb.*'      # All MongoDB operations
      - 'service.status'
      - 'service.restart'
      - 'service.reload'
      - 'file.read'      # Read config files
      - 'test.*'
      - 'grains.items'

    # Runner access: job management only
    runners:
      - 'jobs.*'

    # No wheel access
    wheel: []
```

**What's Allowed**:
```bash
# Database operations
salt --client 'postgres-*' postgres.db_create myapp_db
salt --client 'mysql-1' mysql.query 'SHOW DATABASES'
salt --client 'redis-*' redis.info

# Service management
salt --client 'db-prod-1' service.restart postgresql

# Read configuration
salt --client 'postgres-1' file.read /etc/postgresql/postgresql.conf
```

**What's Denied**:
```bash
# Cannot target web servers
salt --client 'web-*' postgres.db_create
# Error: Minion targeting denied

# Cannot install packages (not in modules list)
salt --client 'db-*' pkg.install postgresql
# Error: Module execution denied

# Cannot write files
salt --client 'db-*' file.write /etc/postgresql/postgresql.conf
# Error: Module execution denied
```

#### Example 3: Monitoring/Observability System

**Requirements**:
- Check all systems
- Read-only access (no changes)
- Monitor service status
- Collect metrics

```yaml
client_acl:
  monitoring-system:
    # Minion targeting: all systems
    minions: ['*']

    # Module execution: read-only operations
    modules:
      - 'test.ping'
      - 'test.version'
      - 'status.*'       # All status checks
      - 'grains.items'
      - 'pillar.get'
      - 'service.status'
      - 'disk.usage'
      - 'network.interfaces'
      - 'ps.top'
      - 'saltutil.find_job'

    # Runner access: job and minion status
    runners:
      - 'jobs.list_jobs'
      - 'jobs.lookup_jid'
      - 'manage.up'
      - 'manage.down'
      - 'manage.status'

    # No wheel access
    wheel: []
```

**What's Allowed**:
```bash
# Check all minions
salt --client '*' test.ping

# Monitor services
salt --client 'web-*' service.status nginx
salt --client 'db-*' service.status postgresql

# Collect metrics
salt --client '*' status.uptime
salt --client '*' disk.usage
```

**What's Denied**:
```bash
# Cannot restart services (only status)
salt --client '*' service.restart nginx
# Error: Module execution denied

# Cannot execute commands
salt --client '*' cmd.run 'df -h'
# Error: Module execution denied
```

#### Example 4: Environment Separation (Dev/Staging/Prod)

**Requirements**:
- Separate workstations for each environment
- Production has strict restrictions
- Development is more permissive
- Staging is in-between

```yaml
client_acl:
  # Development workstation - permissive
  dev-ops-workstation:
    minions: ['dev-*']
    modules: ['*']       # All modules allowed in dev
    runners: ['*']
    wheel: []

  # Staging workstation - moderate restrictions
  staging-ops-workstation:
    minions: ['staging-*']
    modules:
      - 'state.*'
      - 'service.*'
      - 'pkg.*'
      - 'test.*'
      - 'grains.*'
      - 'pillar.*'
      - 'cmd.run'        # Allowed in staging for debugging
    runners: ['jobs.*', 'state.orchestrate']
    wheel: []

  # Production workstation - strict restrictions
  prod-ops-workstation:
    minions: ['prod-*']
    modules:
      - 'state.apply'    # Only state.apply, not state.sls
      - 'state.sls'
      - 'service.restart'
      - 'service.reload'
      - 'test.ping'
      - 'grains.items'
      # NO cmd.run
      # NO pkg.install (use states)
      # NO file.write (use states)
    runners: ['state.orchestrate', 'jobs.*']
    wheel: []
```

**Development Environment**:
```bash
# Anything goes in dev
salt --client 'dev-*' cmd.run 'ls -la'  → ✓ Allowed
salt --client 'dev-*' pkg.install nginx → ✓ Allowed
```

**Staging Environment**:
```bash
# Controlled changes in staging
salt --client 'staging-*' state.apply webserver → ✓ Allowed
salt --client 'staging-*' cmd.run 'debug command' → ✓ Allowed
salt --client 'staging-*' service.restart nginx → ✓ Allowed
```

**Production Environment**:
```bash
# Strict control in production
salt --client 'prod-*' state.apply webserver → ✓ Allowed
salt --client 'prod-*' service.restart nginx → ✓ Allowed

# Dangerous operations denied
salt --client 'prod-*' cmd.run 'rm -rf' → ✗ Denied
salt --client 'prod-*' pkg.install nginx → ✗ Denied (use states)
salt --client 'prod-*' file.write /etc/config → ✗ Denied (use states)
```

### Publish ACL Best Practices

#### 1. Start Restrictive, Expand as Needed

```yaml
# Start with minimal permissions
client_acl:
  new-client:
    minions: ['test-*']      # Only test minions
    modules: ['test.ping']   # Only ping

# Expand based on actual needs
client_acl:
  new-client:
    minions: ['test-*', 'dev-*']
    modules: ['test.*', 'state.apply']
```

#### 2. Use Specific Patterns Over Wildcards

```yaml
# Less secure - overly broad
client_acl:
  client1:
    minions: ['*']
    modules: ['*']

# More secure - specific patterns
client_acl:
  client1:
    minions: ['web-prod-*', 'app-prod-*']
    modules: ['service.*', 'state.apply', 'test.*']
```

#### 3. Separate Read-Only from Destructive Operations

```yaml
# Read-only client
client_acl:
  monitoring:
    minions: ['*']
    modules: ['test.ping', 'status.*', 'grains.items']

# Deployment client
client_acl:
  deploy:
    minions: ['app-*']
    modules: ['state.apply', 'service.restart']
```

#### 4. Document Why Each Permission Exists

```yaml
client_acl:
  webops-client:
    minions:
      - 'web-*'      # All web servers
      - 'app-*'      # Application servers hosting web apps
      - 'lb-*'       # Load balancers for web tier
    modules:
      - 'service.*'  # Required for nginx/apache management
      - 'state.apply'  # Required for deployments
      - 'test.*'     # Required for connectivity testing
```

#### 5. Test ACL Changes in Non-Production First

```bash
# Test on dev first
salt --client 'dev-web-1' new.module

# Verify no unintended access
salt --client 'dev-db-1' new.module  # Should deny

# Then apply to production
```

### Common Publish ACL Patterns

#### Pattern: Read-Only Access

```yaml
modules:
  - 'test.ping'
  - 'test.version'
  - 'status.*'
  - 'grains.items'
  - 'pillar.get'
  - 'service.status'  # Note: .status not .restart
  - 'file.read'       # Note: .read not .write
```

#### Pattern: Service Management

```yaml
modules:
  - 'service.status'
  - 'service.start'
  - 'service.stop'
  - 'service.restart'
  - 'service.reload'
  - 'service.enable'
  - 'service.disable'
```

#### Pattern: Deployment Operations

```yaml
modules:
  - 'state.apply'
  - 'state.sls'
  - 'state.highstate'
  - 'saltutil.refresh_pillar'
  - 'git.pull'
  - 'service.restart'
  - 'test.ping'
```

#### Pattern: Package Management

```yaml
modules:
  - 'pkg.install'
  - 'pkg.remove'
  - 'pkg.upgrade'
  - 'pkg.list_upgrades'
  - 'pkg.list_pkgs'
  - 'pkg.version'
```

## Reference Configuration Examples

See `CLIENT_ACL_CONFIGURATION.md` for complete technical reference and configuration schema.

## See Also

- [CLIENT_ACL_CONFIGURATION.md](CLIENT_ACL_CONFIGURATION.md) - Technical configuration reference
- [Salt Publisher ACL](https://docs.saltproject.io/en/latest/ref/publisheracl.html) - User-based ACL
- [External Authentication](https://docs.saltproject.io/en/latest/topics/eauth/index.html) - eAuth system
- [Salt Security](https://docs.saltproject.io/en/latest/topics/hardening.html) - General security hardening
