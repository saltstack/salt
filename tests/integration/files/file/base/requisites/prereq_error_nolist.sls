# will fail with 'Cannot extend ID Z (...) not part of the high state.'
# and not "The following requisites were not found" like in yaml list syntax
I:
  cmd.run:
    - name: echo I
    - prereq:
        cmd: Z
