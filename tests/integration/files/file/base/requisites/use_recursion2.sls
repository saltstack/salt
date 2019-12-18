#
# A <--+ ---u--+
#      |       |
# B -u-+ <-+   |
#          |   |
# C -u-----+ <-+

A:
  cmd.run:
    - name: echo "A"
    - use:
        cmd: C

B:
  cmd.run:
    - name: echo "B"
    - use:
        cmd: C

C:
  cmd.run:
    - name: echo "B"
    - use:
        cmd: A
