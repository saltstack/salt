cmd_run_unless_multiple:
  cmd.run:
    - name: echo "hello"
    - unless:
  {% if grains["os"] ==  "Windows" %}
      - "exit 0"
      - "exit 1"
      - "exit 0"
  {% else %}
      - "$(which true)"
      - "$(which false)"
      - "$(which true)"
  {% endif %}
