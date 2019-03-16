{% set string = 'lmno' %}
{% set list = ['abcd','efgh','ijk','lmno','pqrs'] %}

{% set result = string | substring_in_list(list) %}

{% include 'jinja_filters/common.sls' %}
