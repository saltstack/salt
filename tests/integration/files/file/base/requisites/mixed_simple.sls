# Simple mix between prereq and require
# C (1) <--+ <------+
#          |        |
# B (2) -p-+ <-+    |
#              |    |
# A (3) --r----+ -p-+

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

# infinite recursion.....?
C:
  cmd.run:
    - name: echo C
    # will test B and be applied only if B changes,
    # and then will run before B
    - prereq:
        - cmd: B
