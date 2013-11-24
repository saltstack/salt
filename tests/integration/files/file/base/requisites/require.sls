A:
  cmd.run:
    - name: echo A fifth
    - require:
      - cmd: C
B:
  cmd.run:
    - name: echo B second
    - require_in:
      - cmd: A
      # waiting for issue #8773 fix
      # this will generate a warning but will still be done
      # right syntax is cmd: C
      #- cmd.run: C
      - cmd: C

C:
  cmd.run:
    - name: echo C third

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

# will fail with "The following requisites were not found"
F:
  cmd.run:
    - name: echo F
    - require:
      - foobar: A
# will fail with "The following requisites were not found"
G:
  cmd.run:
    - name: echo G
    - require:
      - cmd: Z

