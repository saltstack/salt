{% set salt_foo_bar_exist = 'foo.bar' in salt %}
{% set salt_test_ping_exist = 'test.ping' in salt %}

test-ping-exist:
  test.succeed_without_changes:
    - name: salt_test_ping_exist_{{ salt_test_ping_exist }}

foo-bar-not-exist:
  test.succeed_without_changes:
    - name: salt_foo_bar_exist_{{ salt_foo_bar_exist }}
