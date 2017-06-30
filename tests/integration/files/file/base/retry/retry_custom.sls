file_test:
  file.exists:
    - name: /path/to/a/non-existent/file.txt
    - retry:
        until: True
        attempts: 5
        interval: 10
        splay: 0
