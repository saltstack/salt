{% if grains['os'] == 'Windows' %}
  {% set result = 'c:\Windows\system.ini' | is_text_file() %}
{% else %}
  {% set result = '/etc/passwd' | is_text_file() %}
{% endif %}

{% include 'jinja_filters/common.sls' %}
