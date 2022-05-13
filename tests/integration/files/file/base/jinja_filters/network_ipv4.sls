{% set result = ['127.0.0.1', '::1'] | ipv4() %}

{% include 'jinja_filters/tojson.sls' %}
