{% if grains['os'] == 'Windows' %}
  {% set result = 'c:\salt\conf' | list_files() %}
{% else %}
  {% set result = '/bin' | list_files() %}
{% endif %}

{% include 'jinja_filters/common.sls' %}
