a:
  test.show_notification:
    - name: a
    - text: message
    - require:
        - test: b
    - order: 1
    - failhard: True

b:
  test.fail_with_changes:
    - name: b
    - failhard: True
