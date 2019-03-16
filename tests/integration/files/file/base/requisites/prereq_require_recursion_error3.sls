# issue #8785 RuntimeError: maximum recursion depth exceeded
# C <--+ <------+ -r-+
#      |        |    |
# B -p-+ <-+    | <--+-- ERROR: cannot respect both require and prereq
#          |    |
# A --r----+ -p-+

A:
  cmd.run:
    - name: echo A
    # is running in test mode before C
    # C gets executed first if this states modify something
    - prereq_in:
      - cmd: C
B:
  cmd.run:
    - name: echo B
    - require_in:
      - cmd: A
      # this should raise the error
      - cmd: C

# infinite recursion.....?
C:
  cmd.run:
    - name: echo C
    # will test B and be applied only if B changes,
    # and then will run before B
    - prereq:
        - cmd: B
