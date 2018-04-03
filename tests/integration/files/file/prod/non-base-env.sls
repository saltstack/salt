test_file:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('nonbase_env') }}
    - source: salt://nonbase_env
