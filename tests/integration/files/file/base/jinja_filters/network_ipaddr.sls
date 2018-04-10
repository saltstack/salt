{% set result = ['127.0.0.1', '::1', 'random_junk'] | ipaddr() %}

{% include 'jinja_filters/common_quotes.sls' %}
