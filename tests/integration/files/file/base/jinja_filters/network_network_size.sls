{% set result = '192.168.1.0/28' | network_size() %}

{% include 'jinja_filters/common.sls' %}
