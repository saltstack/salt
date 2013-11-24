# will fail with "Data failed to compile:"
A:
  cmd.run:
    - name: echo A
    - require_in:
      - foobar: W

