# issue #8785
# B <--+ ----r-+
#      |       |
# A -p-+ <-----+-- ERROR: cannot respect both require and prereq

A:
  cmd.run:
    - name: echo A
    - require_in:
      - cmd: B

# infinite recursion.....?
B:
  cmd.run:
    - name: echo B
    # will test A and be applied only if A changes,
    # and then will run before A
    - prereq:
        - cmd: A
