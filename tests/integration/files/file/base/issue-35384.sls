cmd_run_unless_multiple:
  cmd.run:
    - name: echo "hello"
    - unless:
      - /bin/true
      - /bin/false
