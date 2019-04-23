{% if grains['os'] == 'Windows' %}
  {% set result = 'c:\\empty_file' | is_empty() %}
{% else %}
  {% set result = '/dev/null' | is_empty() %}
{% endif %}

{% include 'jinja_filters/common.sls' %}
