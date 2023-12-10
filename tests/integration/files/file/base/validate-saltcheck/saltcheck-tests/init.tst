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
    - 1
    - "two"
  kwargs:
    a: "something"
    b: "hello"
  assertions:
    - assertion_section: kwargs:b
      expected_return: hello
      assertion: assertIn
    - assertion: assertEqual
      assertion_section: kwargs:a
      expected_return: something
    - assertion: assertIn
      assertion_section: args
      expected_return: "two"
    - assertion: assertIn
      assertion_section: args
      expected_return: 1
  print_result: True
