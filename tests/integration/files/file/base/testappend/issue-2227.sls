issue-2227:
  file.append:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test.append') }}
    - text: HISTTIMEFORMAT='%F %T '
