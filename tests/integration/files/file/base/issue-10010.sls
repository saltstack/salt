{# fail in the macro #}
{%- import "issue-10010-macro.sls" as mac with context %}

{i_am_a_test_which_fails:
  test.ping: []

