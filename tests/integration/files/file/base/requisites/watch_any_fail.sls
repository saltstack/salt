A:
  cmd.wait:
    - name: 'true'
    - watch_any:
      - cmd: B
      - cmd: C
      - cmd: D

B:
  cmd.run:
    - name: 'false'

C:
  cmd.run:
    - name: 'false'

D:
  cmd.run:
    - name: 'false'
