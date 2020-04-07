echo_test_hello:
  module_and_function: test.echo
  args:
    - "hello"
  kwargs:
  assertion: assertEqual
  expected_return:  'hello'

test_args:
  module_and_function: test.arg
  args:
    - "1"
    - "two"
  kwargs:
    a: "something"
    b: "hello"
  assertion_section: kwargs:b
  expected_return: hello
  assertion: assertIn
  print_result: True
