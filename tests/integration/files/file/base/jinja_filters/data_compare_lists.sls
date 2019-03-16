{% set list_one = ['a', 'b', 'c', 'd'] %}
{% set list_two = ['a', 'c', 'd'] %}

{% set result = list_one | compare_lists(list_two) %}

{% include 'jinja_filters/tojson.sls' %}
