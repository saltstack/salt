# issue #8211
#             expected rank
# B --+             1
#     |
# C <-+ ----+       2/3
#           |
# D ---+    |       3/2
#      |    |
# A <--+ <--+       4
#
#             resulting rank
# D --+
#     |
# A <-+ <==+
#          |
# B --+    +--> unrespected A prereq_in C (FAILURE)
#     |    |
# C <-+ ===+

# runs after C
A:
  cmd.run:
    - name: echo A fourth
    # is running in test mode before C
    # C gets executed first if this states modify something
    - prereq_in:
      - cmd: C

# runs before C
B:
  cmd.run:
    - name: echo B first
    # will test C and be applied only if C changes,
    # and then will run before C
    - prereq:
      - cmd: C

C:
  cmd.run:
    - name: echo C second
    # replacing A prereq_in C by theses lines
    # changes nothing actually
    #- prereq:
    #  - cmd: A

# Removing D, A gets executed after C
# as described in (A prereq_in C)
# runs before A
D:
  cmd.run:
    - name: echo D third
    # will test A and be applied only if A changes,
    # and then will run before A
    - prereq:
      - cmd: A

