supervisord-pip:
    pip.installed:
      - name: supervisor
      - mirrors: http://testpypi.python.org/pypi
      - bin_env: {{ salt['runtests_helpers.get_sys_temp_dir_for_path']('pip-installed-errors') }}
