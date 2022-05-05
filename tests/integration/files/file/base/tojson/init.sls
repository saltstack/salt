{%- set data = '{"Der Zucker": "süß", "Die Webseite": "https://saltproject.io"}'|load_json -%}
{{ pillar['tojson-file'] }}:
  file.managed:
    - source: salt://tojson/template.jinja
    - template: jinja
    - context:
        data: {{ data|tojson }}
