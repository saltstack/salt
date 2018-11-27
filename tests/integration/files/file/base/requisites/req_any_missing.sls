changing_state:
  cmd.run:
    - name: echo "Changed!"

missing_prereq:
  cmd.run:
    - name: echo "Changed!"
    - onchanges_any:
      - this: is missing
    - onchanges:
      - also: missing
