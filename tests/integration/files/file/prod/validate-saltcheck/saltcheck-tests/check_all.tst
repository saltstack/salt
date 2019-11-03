check_all_validate_prod:
  module_and_function: test.echo
  args:
    - "check-prod"
  kwargs:
  assertion: assertEqual
  expected-return: 'check-prod'
