{{ salt['runtests_helpers.get_sys_temp_dir_for_path']('issue-2028-pip-installed') }}:
  virtualenv.managed:
    - no_site_packages: True
    - distribute: True

supervisord-pip:
    pip.installed:
      - name: supervisor
      - bin_env: {{ salt['runtests_helpers.get_sys_temp_dir_for_path']('issue-2028-pip-installed') }}
      - mirrors: http://testpypi.python.org/pypi
      - require:
        - virtualenv: {{ salt['runtests_helpers.get_sys_temp_dir_for_path']('issue-2028-pip-installed') }}
