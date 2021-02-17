{%- set virtualenv_base = salt['runtests_helpers.get_salt_temp_dir_for_path']('virtualenv-12-base') -%}
{%- set virtualenv_test = salt['runtests_helpers.get_salt_temp_dir_for_path']('pip-installed-weird-install') -%}

{{ virtualenv_base }}:
  virtualenv.managed:
    - system_site_packages: False
    - distribute: True
    {#- Provide the real path for the python executable in case tests are running inside a virtualenv #}
    - python: {{ salt.runtests_helpers.get_python_executable() }}

install-working-setuptools:
  pip.installed:
    - name: 'setuptools<50.0.0'
    - bin_env: {{ virtualenv_base }}
    - require:
      - virtualenv: {{ virtualenv_base }}

install_older_venv:
  pip.installed:
    - name: 'virtualenv < 13.0'
    - bin_env: {{ virtualenv_base }}
    - require:
      - pip: install-working-setuptools
      - virtualenv: {{ virtualenv_base }}

# For this test we need to make sure that the virtualenv used in the
# 'carbon-weird-setup' pip.installed state below was created using
# virtualenv < 13.0. virtualenvs created using later versions make
# packages with custom setuptools prefixes relative to the virtualenv
# itself, which makes the 'weird' behavior we are trying to confirm
# obsolete. Thus, the two states above ensure that the 'base' venv has
# a version old enough to exhibit the behavior we want to test.

setup_test_virtualenv:
  cmd.run:
    - name: {{ virtualenv_base }}/bin/virtualenv {{ virtualenv_test }}
    - onchanges:
      - pip: install_older_venv

carbon-weird-setup:
  pip.installed:
    - name: 'carbon < 1.1'
    - no_deps: True
    - bin_env: {{ virtualenv_test }}
    - onchanges:
      - cmd: setup_test_virtualenv
