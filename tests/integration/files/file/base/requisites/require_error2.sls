# issue #8772
# should fail with "Data failed to compile:"
B:
  cmd.run:
    - name: echo B last
    - require_in:
      # state foobar does not exists in A
      - foobar: A

A:
  cmd.run:
    - name: echo A first

