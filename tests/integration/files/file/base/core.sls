{{ salt['runtests_helpers.get_salt_temp_dir_for_path']('testfile') }}:
  file:
    - managed
    - source: salt://testfile
    - makedirs: true
