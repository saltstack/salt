{%- set config_dir = pillar['git_pillar']['config_dir'] %}
{%- set git_dir = pillar['git_pillar']['git_dir'] %}
{%- set venv_dir = pillar['git_pillar']['venv_dir'] %}
{%- set root_dir = pillar['git_pillar']['root_dir'] %}

{{ config_dir }}/uwsgi.yml:
  file.managed:
    - source: salt://git_pillar/http/files/uwsgi.yml
    - user: root
    {%- if grains['os_family'] == 'FreeBSD' %}
    - group: wheel
    {%- else %}
    - group: root
    {%- endif %}
    - mode: 644
    - makedirs: True
    - template: jinja

{{ root_dir }}:
  file.directory:
    - user: root
    {%- if grains['os_family'] == 'FreeBSD' %}
    - group: wheel
    {%- else %}
    - group: root
    {%- endif %}
    - mode: 755

{{ git_dir }}/users:
  file.managed:
    - source: salt://git_pillar/http/files/users
    - user: root
    {%- if grains['os_family'] == 'FreeBSD' %}
    - group: wheel
    {%- else %}
    - group: root
    {%- endif %}
    - makedirs: True
    - mode: 644

{{ venv_dir }}:
  virtualenv.managed:
    - system_site_packages: False
    {#- Provide the real path for the python executable in case tests are running inside a virtualenv #}
    - python: {{ salt.runtests_helpers.get_python_executable() }}

install-working-setuptools:
  pip.installed:
    - name: 'setuptools<50.0.0'
    - bin_env: {{ venv_dir }}
    - require:
      - virtualenv: {{ venv_dir }}

uwsgi:
  pip.installed:
    - name: 'uwsgi == 2.0.18'
    - bin_env: {{ venv_dir }}
    {#- The env var bellow is EXTREMELY important #}
    - env_vars:
        UWSGI_PROFILE: cgi
    - require:
      - pip: install-working-setuptools
      - virtualenv: {{ venv_dir }}
