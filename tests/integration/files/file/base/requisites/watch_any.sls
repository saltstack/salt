{% if grains['os'] == 'Windows' %}
    {% set cmd_true = 'exit' %}
    {% set cmd_false = 'exit /B 1' %}
{% else %}
    {% set cmd_true = 'true' %}
    {% set cmd_false = 'false' %}
{% endif %}
A:
  cmd.wait:
    - name: '{{ cmd_true }}'
    - watch_any:
      - cmd: B
      - cmd: C
      - cmd: D

B:
  cmd.run:
    - name: '{{ cmd_true }}'

C:
  cmd.run:
    - name: '{{ cmd_false }}'

D:
  cmd.run:
    - name: '{{ cmd_true }}'

E:
  cmd.wait:
    - name: '{{ cmd_true }}'
    - watch_any:
      - cmd: F
      - cmd: G
      - cmd: H

F:
  cmd.run:
    - name: '{{ cmd_true }}'

G:
  cmd.run:
    - name: '{{ cmd_false }}'

H:
  cmd.run:
    - name: '{{ cmd_false }}'
