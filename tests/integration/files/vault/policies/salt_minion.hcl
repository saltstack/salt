# General KV v1 testing
path "secret/*" {
  capabilities = ["read", "list", "create", "update", "delete"]
}

# General KV v2 testing
path "kv-v2/*" {
  capabilities = ["read", "list", "create", "update", "delete", "patch"]
}

# ACL policy templating tests
path "salt/+/minions/{{identity.entity.metadata.minion-id}}" {
    capabilities = ["create", "read", "update", "delete", "list", "patch"]
}

# ACL policy templating tests with pillar values
path "salt/data/roles/{{identity.entity.metadata.role}}" {
    capabilities = ["read"]
}

# Test list policies
path "sys/policy" {
    capabilities = ["read"]
}

# Test managing policies
path "sys/policy/*" {
    capabilities = ["read", "create", "update", "delete"]
}
