{{ salt['runtests_helpers.get_salt_temp_dir_for_path']('retry_file_option_success') }}:
  file:
    - touch

file_test:
  file.exists:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('retry_file_option_success') }} 
    - retry:
        until: True
        attempts: 5
        interval: 10
        splay: 0
