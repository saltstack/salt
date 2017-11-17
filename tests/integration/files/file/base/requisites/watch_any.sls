A:
  cmd.wait:
    - name: 'true'
    - watch_any:
      - cmd: B
      - cmd: C
      - cmd: D

B:
  cmd.run:
    - name: 'true'

C:
  cmd.run:
    - name: 'false'

D:
  cmd.run:
    - name: 'true'

E:
  cmd.wait:
    - name: 'true'
    - watch_any:
      - cmd: F
      - cmd: G
      - cmd: H

F:
  cmd.run:
    - name: 'true'

G:
  cmd.run:
    - name: 'false'

H:
  cmd.run:
    - name: 'false'
