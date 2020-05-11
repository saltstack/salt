{% set dict_one = {'a': 'b', 'c': 'd'} %}

{% set result = dict_one | json_encode_dict() %}

{% include 'jinja_filters/common.sls' %}
