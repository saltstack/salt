{%- set config_dir = pillar['git_pillar']['config_dir'] %}
{%- set git_dir = pillar['git_pillar']['git_dir'] %}
{%- set venv_dir = pillar['git_pillar']['venv_dir'] %}
{%- set root_dir = pillar['git_pillar']['root_dir'] %}

{{ config_dir }}/nginx.conf:
  file.managed:
    - source: salt://git_pillar/http/files/nginx.conf
    - user: root
    - group: root
    - mode: 644
    - makedirs: True
    - template: jinja

{{ config_dir }}/uwsgi.yml:
  file.managed:
    - source: salt://git_pillar/http/files/uwsgi.yml
    - user: root
    - group: root
    - mode: 644
    - makedirs: True
    - template: jinja

{{ root_dir }}:
  file.directory:
    - user: root
    - group: root
    - mode: 755

{{ git_dir }}/users:
  file.managed:
    - source: salt://git_pillar/http/files/users
    - user: root
    - group: root
    - makedirs: True
    - mode: 644

{{ venv_dir }}:
  virtualenv.managed:
    - system_site_packages: False

uwsgi:
  pip.installed:
    - name: 'uwsgi >= 2.0.13'
    - bin_env: {{ venv_dir }}
    - env_vars:
        UWSGI_PROFILE: cgi
    - require:
      - virtualenv: {{ venv_dir }}

start_uwsgi:
  cmd.run:
    - name: '{{ venv_dir }}/bin/uwsgi --yaml {{ config_dir }}/uwsgi.yml'
    - require:
      - pip: uwsgi
      - file: {{ config_dir }}/uwsgi.yml

start_nginx:
  cmd.run:
    - name: 'nginx -c {{ config_dir }}/nginx.conf'
    - require:
      - file: {{ config_dir }}/nginx.conf
