{% set result = ['127.0.0.1', '::1'] | ipv6() %}

{% include 'jinja_filters/common_quotes.sls' %}
