sync_minion:
  local.saltutil.sync_all:
    - tgt: {{ data['id'] }}
