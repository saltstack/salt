{{ salt['runtests_helpers.get_salt_temp_dir_for_path']('orch.req_test') }}:
  file.managed:
    - contents: 'Hello world!'
