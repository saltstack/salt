{% set list_one = ['a', 'b', 'c', 'd'] %}

{% set result = list_one | json_encode_list() %}

{% include 'jinja_filters/common.sls' %}
