bar state:
  cmd.wait:
    - name: 'echo bar'

echo foo:
  cmd.run:
    - watch_in:
      - cmd: 'echo bar'
