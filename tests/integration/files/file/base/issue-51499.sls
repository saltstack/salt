{% if 'nonexistent_module.function' in salt %}
{% do salt.log.warning("Module is available") %}
{% endif %}
always-passes:
  test.succeed_without_changes:
    - name: foo
