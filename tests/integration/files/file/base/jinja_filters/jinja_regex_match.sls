{% set result = 'abcd' | regex_match('^(.*)BC(.*)$', ignorecase=True) %}

{% include 'jinja_filters/common.sls' %}
