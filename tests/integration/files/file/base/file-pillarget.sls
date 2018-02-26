{% if grains['kernel'] == 'Windows' %}
  {% set TMP = "C:\\Windows\\Temp\\" %}
{% else %}
  {% set TMP = "/tmp/" %}
{% endif %}

{% set file = salt['pillar.get']('monty', '') %}

create_file:
  file.managed:
    - name: {{ TMP }}filepillar-{{ file }}
