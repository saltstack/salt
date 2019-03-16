{{ salt['runtests_helpers.get_salt_temp_dir_for_path']('issue-1876') }}:
  file:
    - managed
    - source: salt://testfile

  file.append:
    - text: foo

