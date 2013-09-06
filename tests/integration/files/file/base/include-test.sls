include:
  - to-include-test

{{ salt['runtests_helpers.get_sys_temp_dir_for_path']('include-test') }}:
  file:
    - managed
    - source: salt://testfile
