file_test:
  file.exists:
    - name: /path/to/a/non-existent/file.txt
    - retry: True
