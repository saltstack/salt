{%- set virtualenv_base = salt['runtests_helpers.get_salt_temp_dir_for_path']('virtualenv-12-base-1') -%}
{%- set virtualenv_test = salt['runtests_helpers.get_salt_temp_dir_for_path']('issue-46127-pip-env-vars') -%}

{{ virtualenv_base }}:
  virtualenv.managed:
    - system_site_packages: False
    - distribute: True
    {#- Provide the real path for the python executable in case tests are running inside a virtualenv #}
    {%- if salt.runtests_helpers.get_python_executable() %}
    - python: {{ salt.runtests_helpers.get_python_executable() }}
    {%- endif %}

install_older_venv_1:
  pip.installed:
    - name: 'virtualenv < 13.0'
    - bin_env: {{ virtualenv_base }}
    - require:
      - virtualenv: {{ virtualenv_base }}

# For this test we need to make sure that the virtualenv used in the
# 'issue-46127-setup' pip.installed state below was created using
# virtualenv < 13.0. virtualenvs created using later versions make
# packages with custom setuptools prefixes relative to the virtualenv
# itself, which makes the use of env_vars obsolete.
# Thus, the two states above ensure that the 'base' venv has
# a version old enough to exhibit the behavior we want to test.

setup_test_virtualenv_1:
  cmd.run:
    - name: {{ virtualenv_base }}/bin/virtualenv {{ virtualenv_test }}
    - onchanges:
      - pip: install_older_venv_1

issue-46127-setup:
  pip.installed:
    - name: 'carbon < 1.3'
    - no_deps: True
    - env_vars:
        PYTHONPATH: "/opt/graphite/lib/:/opt/graphite/webapp/"
    - bin_env: {{ virtualenv_test }}
    - require:
      - cmd: setup_test_virtualenv_1
