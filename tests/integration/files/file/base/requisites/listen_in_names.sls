test:
  test.succeed_with_changes:
    - name: test
    - listen_in:
      - test: service

service:
  test.succeed_without_changes:
    - names:
      - nginx
      - crond
