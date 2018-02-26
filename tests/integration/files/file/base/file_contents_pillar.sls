{% if grains['kernel'] == 'Windows' %}
  {% set TMP = "C:\\Windows\\Temp\\" %}
{% else %}
  {% set TMP = "/tmp/" %}
{% endif %}

add_contents_pillar_sls:
  file.managed:
    - name: {{ TMP }}test-lists-content-pillars
    - contents_pillar: companions:three
