{% set list_one = ['a', 'b', 'c', 'd'] %}

{% set result = list_one | json_decode_list() %}

{% include 'jinja_filters/common.sls' %}
