include:
  - to-include-test

{{ salt['runtests_helpers.get_salt_temp_dir_for_path']('include-test') }}:
  file:
    - managed
    - source: salt://testfile
