file_test:
  file.exists:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('retry_file') }} 
    - retry:
        until: True
        attempts: 20
        interval: 5
