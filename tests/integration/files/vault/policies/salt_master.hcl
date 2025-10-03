# Test minion token creation
path "auth/token/create" {
  capabilities = ["create", "read", "update"]
}

# Test minion token creation with token roles
path "auth/token/create/*" {
  capabilities = ["create", "read", "update"]
}

# AppRole/entity management testing
path "auth/salt-minions/role" {
  capabilities = ["list"]
}

path "auth/salt-minions/role/*" {
  capabilities = ["read", "create", "update", "delete"]
}

path "sys/auth/salt-minions" {
  capabilities = ["read", "sudo"]
}

path "identity/lookup/entity" {
  capabilities = ["create", "update"]
  allowed_parameters = {
    "alias_name" = []
    "alias_mount_accessor" = []
  }
}

path "identity/entity/name/salt_minion_*" {
  capabilities = ["read", "create", "update", "delete"]
}

path "identity/entity-alias" {
  capabilities = ["create", "update"]
  allowed_parameters = {
    "id" = []
    "canonical_id" = []
    "mount_accessor" = []
    "name" = []
  }
}
