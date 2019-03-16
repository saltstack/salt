{{ salt['runtests_helpers.get_salt_temp_dir_for_path']('issue-1879') }}:
  file:
    - touch
