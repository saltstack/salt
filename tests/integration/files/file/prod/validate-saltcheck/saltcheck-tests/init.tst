echo_test_prod_env:
  module_and_function: test.echo
  args:
    - "test-prod"
  kwargs:
  assertion: assertEqual
  expected_return:  'test-prod'
