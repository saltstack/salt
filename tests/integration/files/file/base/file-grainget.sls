{% if grains['kernel'] == 'Windows' %}
  {% set TMP = "C:\\Windows\\Temp\\" %}
{% else %}
  {% set TMP = "/tmp/" %}
{% endif %}

grain_create_file:
  file.managed:
    - name: {{ TMP }}file-grain-test
    - source: salt://file-grainget.tmpl
    - template: jinja

