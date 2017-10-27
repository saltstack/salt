{{ salt['runtests_helpers.get_sys_temp_dir_for_path']('issue-2028-pip-installed') }}:
  virtualenv.managed:
    - system_site_packages: False
    - distribute: True

supervisord-pip:
    pip.installed:
      - name: supervisor
      - bin_env: {{ salt['runtests_helpers.get_sys_temp_dir_for_path']('issue-2028-pip-installed') }}
      - require:
        - virtualenv: {{ salt['runtests_helpers.get_sys_temp_dir_for_path']('issue-2028-pip-installed') }}
