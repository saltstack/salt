cmd_run_unless_multiple:
  cmd.run:
    - name: echo "hello"
    - unless:
      - "$(which true)"
      - "$(which false)"
