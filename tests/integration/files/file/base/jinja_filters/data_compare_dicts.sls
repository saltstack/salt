{% set dict_one = {'a': 'b', 'c': 'd'} %}
{% set dict_two = {'a': 'c', 'c': 'd'} %}

{% set result = dict_one | compare_dicts(dict_two) %}

{% include 'jinja_filters/common.sls' %}
