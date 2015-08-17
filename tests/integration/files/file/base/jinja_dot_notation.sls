{# This syntax should be equivalent to salt['test.ping']() #}
{% set is_true = salt.test.ping() %}

always-passes:
  test.succeed_without_changes:
    - name: is_true_{{ is_true }}
