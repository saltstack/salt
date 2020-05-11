{% set list = [True, False, False, False] %}

{% set result = list | exactly_one_true() %}

{% include 'jinja_filters/common.sls' %}
