{% set result = '/etc/passwd' | file_hashsum() %}

{% include 'jinja_filters/common.sls' %}
