pep8-pip:
    pip.installed:
      - name: pep8
      - bin_env: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('pip-installed-errors') }}
