test_cmd_too_long:
  cmd.run:
    - name: {{ pillar['long_command'] }}
    - parallel: True

test_cmd_not_found:
  cmd.run:
    - name: {{ pillar['short_command'] }}
    - parallel: True
