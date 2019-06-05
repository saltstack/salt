A:
  cmd.wait:
    - name: 'true'
    - watch_any:
      - cmd: B
      - cmd: C

B:
  cmd.run:
    - name: 'false'

C:
  cmd.run:
    - name: 'false'
