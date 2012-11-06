pep8-pip:
  pip.installed:
    - name: pep8
    - mirrors: http://testpypi.python.org/pypi
    - bin_env: {{ salt['runtests_helpers.get_sys_temp_dir_for_path']('issue-2087-missing-pip') }}
