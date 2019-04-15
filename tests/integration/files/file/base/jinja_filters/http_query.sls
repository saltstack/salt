{% set result = 'https://www.google.com' | http_query(test=True) %}

{% include 'jinja_filters/common.sls' %}
