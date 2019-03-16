test:
  test.succeed_with_changes:
    - name: test

service:
  test.succeed_without_changes:
    - names:
      - nginx
      - crond
    - listen:
      - test: test
