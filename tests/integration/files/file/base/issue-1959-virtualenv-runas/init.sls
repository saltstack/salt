{%- set venv_dir = salt['runtests_helpers.get_sys_temp_dir_for_path']('issue-1959-virtualenv-runas') %}

{{ venv_dir }}:
  virtualenv.managed:
    - requirements: salt://issue-1959-virtualenv-runas/requirements.txt
    - user: issue-1959
    {#- Provide the real path for the python executable in case tests are running inside a virtualenv #}
    - python: {{ salt.runtests_helpers.get_python_executable() }}
    {%- if grains.get('pythonversion')[0] != 2 %}
    {#- wheels are disabled because the pip cache dir will not be owned by the above issue-1959 user. Need to check this ASAP #}
    - no_binary: ':all:'
    {%- endif %}
    - env:
        XDG_CACHE_HOME: /tmp

install-working-setuptools:
  pip.installed:
    - name: 'setuptools<50.0.0'
    - bin_env: {{ venv_dir }}
    - require:
      - virtualenv: {{ venv_dir }}
