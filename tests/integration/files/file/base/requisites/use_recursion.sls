A:
  cmd.run:
    - name: echo "A"
    - onlyif: return False
    - use:
        cmd: B

B:
  cmd.run:
    - name: echo "B"
    - unless: return False
    - use:
        cmd: A

