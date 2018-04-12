{% set result = '/etc/passwd' | is_text_file() %}

{% include 'jinja_filters/common.sls' %}
