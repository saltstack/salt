include:
  - .other

first_state:
  cmd.run:
    - name: echo "Success!"
    - require:
      - sls: .other
