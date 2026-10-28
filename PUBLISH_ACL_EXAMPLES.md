# Client ACL Publish - Usage Examples

## Example Scenarios

This document provides practical examples of Client ACL for publish operations.

## Scenario 1: Web Administration Client

### Configuration

```yaml
client_acl:
  web-admin:
    runners:
      - 'jobs.list_jobs'
      - 'jobs.lookup_jid'
    wheel: []
    minions:
      - 'web-*'
      - 'app-*'
      - 'lb-*'
    modules:
      - 'test.*'
      - 'service.*'
      - 'pkg.install'
      - 'pkg.upgrade'
      - 'file.managed'
```

### Allowed Operations

```bash
# Check connectivity
salt --client-auth --id=web-admin 'web-*' test.ping
# ✓ ALLOWED: Targets web-* (in minions), executes test.ping (matches test.*)

# Restart nginx on web servers
salt --client-auth --id=web-admin 'web-01' service.restart nginx
# ✓ ALLOWED: Targets web-01 (matches web-*), executes service.restart (matches service.*)

# Install package on app servers
salt --client-auth --id=web-admin 'app-*' pkg.install name=python3-redis
# ✓ ALLOWED: Targets app-* (in minions), executes pkg.install (in modules)

# Deploy config file
salt --client-auth --id=web-admin 'lb-*' file.managed /etc/nginx/nginx.conf source=salt://nginx.conf
# ✓ ALLOWED: Targets lb-* (in minions), executes file.managed (in modules)
```

### Denied Operations

```bash
# Try to target database servers
salt --client-auth --id=web-admin 'db-*' test.ping
# ✗ DENIED: Client "web-admin" is not authorized to target the following minion(s): db-01, db-02

# Try to execute state.apply
salt --client-auth --id=web-admin 'web-*' state.apply webserver
# ✗ DENIED: Client "web-admin" is not authorized to execute function "state.apply".

# Try to run arbitrary commands
salt --client-auth --id=web-admin 'web-*' cmd.run 'rm -rf /tmp/*'
# ✗ DENIED: Client "web-admin" is not authorized to execute function "cmd.run".
```

## Scenario 2: Monitoring Client (Read-Only)

### Configuration

```yaml
client_acl:
  monitoring:
    runners:
      - 'manage.*'
      - 'jobs.*'
    wheel:
      - 'key.list_all'
      - 'key.finger'
    minions:
      - '*'  # Can target all minions
    modules:
      - 'test.ping'
      - 'grains.items'
      - 'grains.item'
      - 'status.*'
      - 'disk.*'
      - 'network.*'
```

### Allowed Operations

```bash
# Check all minions
salt --client-auth --id=monitoring '*' test.ping
# ✓ ALLOWED: Targets * (in minions), executes test.ping (in modules)

# Get grains from specific minion
salt --client-auth --id=monitoring 'web-01' grains.items
# ✓ ALLOWED: Targets web-01 (matches *), executes grains.items (in modules)

# Check disk usage
salt --client-auth --id=monitoring 'db-*' disk.usage
# ✓ ALLOWED: Targets db-* (matches *), executes disk.usage (matches disk.*)

# Get network stats
salt --client-auth --id=monitoring 'web-*' network.interfaces
# ✓ ALLOWED: Targets web-* (matches *), executes network.interfaces (matches network.*)
```

### Denied Operations

```bash
# Try to modify anything
salt --client-auth --id=monitoring '*' service.restart apache2
# ✗ DENIED: Client "monitoring" is not authorized to execute function "service.restart".

# Try to install packages
salt --client-auth --id=monitoring '*' pkg.install htop
# ✗ DENIED: Client "monitoring" is not authorized to execute function "pkg.install".
```

## Scenario 3: CI/CD Pipeline Client

### Configuration

```yaml
client_acl:
  cicd-pipeline:
    runners:
      - 'jobs.*'
      - 'state.orchestrate'
    wheel: []
    minions:
      - 'staging-*'
      - 'test-*'
    modules:
      - 'state.apply'
      - 'state.sls'
      - 'state.highstate'
      - 'cmd.run'
      - 'test.*'
```

### Allowed Operations

```bash
# Deploy to staging
salt --client-auth --id=cicd-pipeline 'staging-*' state.apply deploy.staging
# ✓ ALLOWED: Targets staging-* (in minions), executes state.apply (in modules)

# Run tests on test environment
salt --client-auth --id=cicd-pipeline 'test-*' cmd.run '/opt/app/run_tests.sh'
# ✓ ALLOWED: Targets test-* (in minions), executes cmd.run (in modules)

# Apply specific state
salt --client-auth --id=cicd-pipeline 'staging-web-01' state.sls webserver.nginx
# ✓ ALLOWED: Targets staging-web-01 (matches staging-*), executes state.sls (in modules)

# Health check after deployment
salt --client-auth --id=cicd-pipeline 'staging-*' test.ping
# ✓ ALLOWED: Targets staging-* (in minions), executes test.ping (matches test.*)
```

### Denied Operations

```bash
# Try to deploy to production
salt --client-auth --id=cicd-pipeline 'prod-*' state.apply
# ✗ DENIED: Client "cicd-pipeline" is not authorized to target the following minion(s): prod-web-01, prod-db-01

# Try to access production even for read-only
salt --client-auth --id=cicd-pipeline 'prod-*' test.ping
# ✗ DENIED: Client "cicd-pipeline" is not authorized to target the following minion(s): prod-web-01, prod-db-01
```

## Scenario 4: Database Administrator Client

### Configuration

```yaml
client_acl:
  dba:
    runners:
      - 'jobs.*'
    wheel: []
    minions:
      - 'db-*'
      - 'redis-*'
      - 'memcached-*'
    modules:
      - 'service.*'
      - 'mysql.*'
      - 'postgres.*'
      - 'redis.*'
      - 'cmd.run'
      - 'test.ping'
      - 'file.managed'
```

### Allowed Operations

```bash
# Restart MySQL service
salt --client-auth --id=dba 'db-prod-01' service.restart mysql
# ✓ ALLOWED: Targets db-prod-01 (matches db-*), executes service.restart (matches service.*)

# Run MySQL query
salt --client-auth --id=dba 'db-*' mysql.query database='myapp' query='SHOW TABLES'
# ✓ ALLOWED: Targets db-* (in minions), executes mysql.query (matches mysql.*)

# Manage Redis config
salt --client-auth --id=dba 'redis-*' file.managed /etc/redis/redis.conf source=salt://redis.conf
# ✓ ALLOWED: Targets redis-* (in minions), executes file.managed (in modules)
```

### Denied Operations

```bash
# Try to access web servers
salt --client-auth --id=dba 'web-*' test.ping
# ✗ DENIED: Client "dba" is not authorized to target the following minion(s): web-01, web-02

# Try to install system packages
salt --client-auth --id=dba 'db-*' pkg.install name=vim
# ✗ DENIED: Client "dba" is not authorized to execute function "pkg.install".
```

## Scenario 5: Security Audit Client

### Configuration

```yaml
client_acl:
  security-audit:
    runners:
      - 'manage.*'
      - 'jobs.*'
    wheel:
      - 'key.*'
    minions:
      - '*'  # Can target all minions for auditing
    modules:
      - 'test.ping'
      - 'grains.items'
      - 'file.stats'
      - 'file.get_sum'
      - 'pkg.list_pkgs'
      - 'user.list_users'
      - 'group.getent'
      - 'service.get_all'
      - 'iptables.get_rules'
```

### Allowed Operations

```bash
# Audit package versions across all servers
salt --client-auth --id=security-audit '*' pkg.list_pkgs
# ✓ ALLOWED: Targets * (in minions), executes pkg.list_pkgs (in modules)

# Check file integrity
salt --client-auth --id=security-audit 'web-*' file.get_sum /etc/passwd md5
# ✓ ALLOWED: Targets web-* (matches *), executes file.get_sum (in modules)

# List users for security audit
salt --client-auth --id=security-audit '*' user.list_users
# ✓ ALLOWED: Targets * (in minions), executes user.list_users (in modules)

# Check firewall rules
salt --client-auth --id=security-audit 'web-*' iptables.get_rules
# ✓ ALLOWED: Targets web-* (matches *), executes iptables.get_rules (in modules)
```

### Denied Operations

```bash
# Try to modify files
salt --client-auth --id=security-audit '*' file.managed /etc/hosts source=salt://hosts
# ✗ DENIED: Client "security-audit" is not authorized to execute function "file.managed".

# Try to create users
salt --client-auth --id=security-audit '*' user.add testuser
# ✗ DENIED: Client "security-audit" is not authorized to execute function "user.add".
```

## Scenario 6: Emergency Admin (Full Access)

### Configuration

```yaml
client_acl:
  emergency-admin:
    runners:
      - '*'
    wheel:
      - '*'
    minions:
      - '*'
    modules:
      - '*'
```

### Allowed Operations

```bash
# Can do anything
salt --client-auth --id=emergency-admin '*' state.apply
salt --client-auth --id=emergency-admin 'db-*' cmd.run 'systemctl restart mysql'
salt --client-auth --id=emergency-admin '*' pkg.install name=emergency-tools
# ✓ ALL ALLOWED: Full access to all minions and all modules
```

## Scenario 7: Mixed Target Types

### Configuration

```yaml
client_acl:
  app-ops:
    runners: []
    wheel: []
    minions:
      - 'web-*'
      - 'app-*'
    modules:
      - 'test.*'
      - 'service.status'
```

### Target Type Examples

```bash
# Glob target (default)
salt --client-auth --id=app-ops 'web-*' test.ping
# ✓ ALLOWED: All web-* minions match the allowed pattern

# List target
salt --client-auth --id=app-ops -L 'web-01,web-02,app-01' test.ping
# ✓ ALLOWED: All listed minions match allowed patterns (web-*, app-*)

# Compound target
salt --client-auth --id=app-ops -C 'G@os:Ubuntu and ( web-* or app-* )' test.ping
# ✓ ALLOWED: All resolved minions match allowed patterns

# PCRE target
salt --client-auth --id=app-ops -E '^web-[0-9]+$' test.ping
# ✓ ALLOWED: All resolved minions (web-01, web-02, etc.) match allowed patterns

# Mixed with denied minion
salt --client-auth --id=app-ops -L 'web-01,db-01' test.ping
# ✗ DENIED: db-01 is not in the allowed minion patterns
```

## Scenario 8: No ACL Configured (Backward Compatible)

### Configuration

```yaml
# No client_acl section in master config
```

### Behavior

```bash
# Any authenticated client can do anything
salt --client-auth --id=any-client '*' state.apply
salt --client-auth --id=any-client 'db-*' cmd.run 'anything'
# ✓ ALLOWED: Backward compatible - no ACL means no restrictions
```

## Common Patterns

### Pattern 1: Environment-based Access

```yaml
client_acl:
  dev-ops:
    minions: ['dev-*', 'staging-*']
    modules: ['*']  # Full module access in dev/staging

  prod-ops:
    minions: ['prod-*']
    modules: ['service.*', 'test.*']  # Limited modules in production
```

### Pattern 2: Role-based Access

```yaml
client_acl:
  web-team:
    minions: ['web-*', 'lb-*']
    modules: ['service.*', 'test.*', 'pkg.install']

  db-team:
    minions: ['db-*', 'redis-*']
    modules: ['mysql.*', 'postgres.*', 'service.*']

  ops-team:
    minions: ['*']
    modules: ['test.*', 'grains.*', 'status.*']
```

### Pattern 3: Service-specific Access

```yaml
client_acl:
  nginx-admin:
    minions: ['*']
    modules:
      - 'service.status nginx'
      - 'service.restart nginx'
      - 'service.reload nginx'
      - 'file.managed /etc/nginx/*'
```

## Error Message Examples

### Example 1: Client Not in ACL

```bash
$ salt --client-auth --id=unknown-client 'web-*' test.ping
{
  "error": {
    "name": "ClientAuthorizationError",
    "message": "Client \"unknown-client\" is not authorized to execute commands. No client_acl configuration found for this client."
  }
}
```

### Example 2: Minion Targeting Denied

```bash
$ salt --client-auth --id=web-admin 'db-*' test.ping
{
  "error": {
    "name": "ClientAuthorizationError",
    "message": "Client \"web-admin\" is not authorized to target the following minion(s): db-01, db-02, db-03"
  }
}
```

### Example 3: Module Execution Denied

```bash
$ salt --client-auth --id=monitoring '*' cmd.run 'whoami'
{
  "error": {
    "name": "ClientAuthorizationError",
    "message": "Client \"monitoring\" is not authorized to execute function \"cmd.run\"."
  }
}
```

## Best Practices

### 1. Principle of Least Privilege

```yaml
# ✓ GOOD: Grant only necessary permissions
client_acl:
  monitoring:
    minions: ['*']
    modules: ['test.ping', 'grains.items', 'status.*']

# ✗ BAD: Overly permissive
client_acl:
  monitoring:
    minions: ['*']
    modules: ['*']
```

### 2. Use Specific Patterns

```yaml
# ✓ GOOD: Specific patterns
client_acl:
  web-ops:
    minions: ['web-prod-*', 'web-staging-*']
    modules: ['service.restart', 'service.status', 'test.ping']

# ✗ BAD: Too broad
client_acl:
  web-ops:
    minions: ['*']
    modules: ['*']
```

### 3. Environment Separation

```yaml
# ✓ GOOD: Separate clients for different environments
client_acl:
  dev-admin:
    minions: ['dev-*']
    modules: ['*']

  prod-admin:
    minions: ['prod-*']
    modules: ['service.*', 'test.*']  # Limited in production
```

### 4. Regular Audits

- Review client_acl configuration regularly
- Remove unused client entries
- Tighten permissions as needed
- Document why each permission is granted

### 5. Testing Before Production

```bash
# Test ACL in staging first
salt --client-auth --id=new-client 'staging-*' test.ping

# Verify expected behavior
# Then apply to production
```

## Troubleshooting

### Issue: Client can't execute anything

**Check:**
1. Is client in `client_acl` configuration?
2. Is `minions` list configured?
3. Is `modules` list configured?

**Solution:**
```yaml
client_acl:
  my-client:
    minions: ['*']  # Add this
    modules: ['*']  # Add this
```

### Issue: Client can target some but not all minions

**Check:**
1. Review `minions` patterns
2. Check resolved minion list vs patterns

**Debug:**
```bash
# Check which minions are resolved
salt-run manage.up  # See all up minions
# Compare with allowed patterns in client_acl
```

### Issue: Client access is not being enforced

**Check:**
1. Is client using `--client-auth` flag?
2. Is client key in `client_keys` cache (not regular minion keys)?
3. Was master restarted after ACL config change?

## Migration from No ACL to ACL

### Step 1: Monitor Current Usage

```bash
# Enable detailed logging
tail -f /var/log/salt/master | grep "Client.*authorized"
```

### Step 2: Create Permissive ACL

```yaml
client_acl:
  existing-client:
    runners: ['*']
    wheel: ['*']
    minions: ['*']
    modules: ['*']
```

### Step 3: Gradually Restrict

```yaml
client_acl:
  existing-client:
    runners: ['*']
    wheel: ['*']
    minions: ['*']
    modules: ['test.*', 'grains.*', 'service.*']  # Start restricting
```

### Step 4: Fine-tune Based on Logs

Review denied operations in logs and adjust ACL accordingly.
