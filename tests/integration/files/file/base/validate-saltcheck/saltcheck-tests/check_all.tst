check_all_validate:
  module_and_function: test.echo
  args:
    - "check"
  kwargs:
  assertion: assertEqual
  expected_return:  'check'
