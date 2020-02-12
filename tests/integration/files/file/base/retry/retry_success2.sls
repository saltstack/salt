file_test_a:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('retry_file_eventual_success') + '_a' }} 
    - content: 'a'

file_test_b:
  file.exists:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('retry_file_eventual_success') }} 
    - retry:
        until: True
        attempts: 20
        interval: 5
    - require:
      - file_test_a
