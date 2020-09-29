{%- set virtualenv_base = salt['runtests_helpers.get_salt_temp_dir_for_path']('issue-2028-pip-installed') %}

{{ virtualenv_base }}:
  virtualenv.managed:
    - system_site_packages: False
    - distribute: True
    {#- Provide the real path for the python executable in case tests are running inside a virtualenv #}
    {%- if salt.runtests_helpers.get_python_executable() %}
    - python: {{ salt.runtests_helpers.get_python_executable() }}
    {%- endif %}

install-working-setuptools:
  pip.installed:
    - name: 'setuptools<50.0.0'
    - bin_env: {{ virtualenv_base }}
    - require:
      - virtualenv: {{ virtualenv_base }}

pep8-pip:
  pip.installed:
    - name: pep8
    - bin_env: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('issue-2028-pip-installed') }}
    - require:
      - pip: install-working-setuptools
      - virtualenv: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('issue-2028-pip-installed') }}
