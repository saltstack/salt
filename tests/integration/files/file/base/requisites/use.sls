# None of theses states should run
A:
  cmd.run:
    - name: echo "A"
    - onlyif: 'false'

# issue #8235
#B:
#  cmd.run:
#    - name: echo "B"
#  # here used without "-"
#    - use:
#        cmd: A

C:
  cmd.run:
    - name: echo "C"
    - use:
        - cmd: A

D:
  cmd.run:
    - name: echo "D"
    - onlyif: 'false'
    - use_in:
        - cmd: E

E:
  cmd.run:
    - name: echo "E"

# issue 8235
#F:
#  cmd.run:
#    - name: echo "F"
#    - onlyif: return 0
#    - use_in:
#        cmd: G
#
#G:
#  cmd.run:
#    - name: echo "G"

# issue xxxx
#H:
#  cmd.run:
#    - name: echo "H"
#    - use:
#        - cmd: C
#I:
#  cmd.run:
#    - name: echo "I"
#    - use:
#        - cmd: E

