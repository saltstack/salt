supervisord-pip:
    pip.installed:
      - name: supervisor
      - bin_env: {{ salt['runtests_helpers.get_sys_temp_dir_for_path']('pip-installed-errors') }}
