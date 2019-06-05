{% set result = '192.168.1.0/30' | network_hosts() %}

{% include 'jinja_filters/common.sls' %}
