{% set result = '192.168.0.12/24' | ip_host() %}

{% include 'jinja_filters/common.sls' %}
