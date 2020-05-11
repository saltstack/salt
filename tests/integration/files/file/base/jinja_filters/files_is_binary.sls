{% if grains['os'] == 'Windows' %}
  {% set result = 'c:\Windows\System32\cmd.exe' | is_bin_file() %}
{% else %}
  {% set result = '/bin/ls' | is_bin_file() %}
{% endif %}

{% include 'jinja_filters/common.sls' %}
