{%- set config_dir = pillar['git_pillar']['config_dir'] %}

{{ config_dir }}/nginx.conf:
  file.managed:
    - source: salt://git_pillar/http/files/nginx.conf
    - user: root
    {%- if grains['os_family'] == 'FreeBSD' %}
    - group: wheel
    {%- else %}
    - group: root
    {%- endif %}
    - mode: 644
    - makedirs: True
    - template: jinja
