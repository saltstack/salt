{% set result = 'abcd' | regex_search('^(.*)BC(.*)$', ignorecase=True) %}

{% include 'jinja_filters/common.sls' %}
