{{ salt['runtests_helpers.get_sys_temp_dir_for_path']('issue-1959-virtualenv-runas') }}:
  virtualenv.managed:
    - requirements: salt://issue-1959-virtualenv-runas/requirements.txt
    - user: issue-1959
