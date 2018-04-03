# B --+
#     |
# C <-+ ----+
#           |
# A <-------+

# runs after C
A:
  cmd.run:
    - name: echo A third
    # is running in test mode before C
    # C gets executed first if this states modify something
    - prereq_in:
      - C

# runs before C
B:
  cmd.run:
    - name: echo B first
    # will test C and be applied only if C changes,
    # and then will run before C
    - prereq:
      - C
C:
  cmd.run:
    - name: echo C second

# will fail with "The following requisites were not found"
I:
  cmd.run:
    - name: echo I
    - prereq:
      - Z
