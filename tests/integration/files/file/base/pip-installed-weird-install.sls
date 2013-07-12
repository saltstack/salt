{{ salt['runtests_helpers.get_sys_temp_dir_for_path']('pip-installed-weird-install') }}:
  virtualenv.managed:
    - system_site_packages: False
    - distribute: True

carbon-weird-setup:
  pip.installed:
    - name: carbon
    - no_deps: True
    - bin_env: {{ salt['runtests_helpers.get_sys_temp_dir_for_path']('pip-installed-weird-install') }}
    - mirrors: http://testpypi.python.org/pypi
    - require:
      - virtualenv: {{ salt['runtests_helpers.get_sys_temp_dir_for_path']('pip-installed-weird-install') }}
