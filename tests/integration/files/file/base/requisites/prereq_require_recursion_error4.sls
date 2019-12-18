# issue #8785
#
# Here it's more complex. Order SHOULD be ok.
# When B changes something the require is verified.
# What should happen if B does not chane anything?
# It should also run because of the require.
# Currently we have:
# RuntimeError: maximum recursion depth exceeded

# B (1) <---+ <--+
#           |    |
# A (2) -r--+ -p-+

A:
  cmd.run:
    - name: echo A
    # is running in test mode before B
    # B gets executed first if this states modify something
    # key of bug
    - prereq_in:
      - cmd: B
B:
  cmd.run:
    - name: echo B
    # B should run before A
    - require_in:
      - cmd: A

