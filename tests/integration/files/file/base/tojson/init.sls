{%- set data = '{"Zucker": "süß", "Webseite": "https://saltstack.com"}'|load_json -%}
{{ pillar['tojson-file'] }}:
  file.managed:
    - source: salt://tojson/template.jinja
    - template: jinja
    - context:
        data: {{ data|tojson }}
