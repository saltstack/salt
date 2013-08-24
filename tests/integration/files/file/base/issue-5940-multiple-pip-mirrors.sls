{{ salt['runtests_helpers.get_sys_temp_dir_for_path']('5940-multiple-pip-mirrors') }}:
  virtualenv.managed:
    - system_site_packages: False
    - distribute: True

pep8:
  pip.installed:
    - name: pep8
    - bin_env: {{ salt['runtests_helpers.get_sys_temp_dir_for_path']('5940-multiple-pip-mirrors') }}
    - mirrors:
      - http://g.pypi.python.org
      - http://c.pypi.python.org
      - http://pypi.crate.io
    - require:
      - virtualenv: {{ salt['runtests_helpers.get_sys_temp_dir_for_path']('5940-multiple-pip-mirrors') }}
