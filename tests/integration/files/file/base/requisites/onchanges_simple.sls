changing_state:
  cmd.run:
    - name: echo "Changed!"
    - onchanges:
      - cmd: state_to_run

state_to_run:
  cmd.run:
    - name: echo "Success!"
