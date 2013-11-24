# Complex require/require_in/prereq/preqreq_in graph
#
#
# D (1) <--------r-----+
#                      |
# C (2) <--+ <-----p-------+
#          |           |   |
# B (3) -p-+ <-+ <-+ --+   |
#              |   |       |
# E (4) ---r---|---+ <-+   |
#              |       |   |
# A (5) --r----+ ---r--+ --+
#

A:
  cmd.run:
    - name: echo A fifth
    # is running in test mode before C
    # C gets executed first if this states modify something
    - prereq_in:
      - cmd: C
B:
  cmd.run:
    - name: echo B third
    - require_in:
      - cmd: A

# infinite recursion.....
C:
  cmd.run:
    - name: echo C second
    # will test B and be applied only if B changes,
    # and then will run before B
    - prereq:
        - cmd: B

D:
  cmd.run:
    - name: echo D first
    # waiting for issue #8773 fix
    # this will generate a warning but will still be done
    # as in B, here testing the non-list form (no '-')
    - require_in:
        cmd: B
        # cmd.foo: B

E:
  cmd.run:
    - name: echo E fourth
    - require:
      - cmd: B
    - require_in:
      - cmd: A


