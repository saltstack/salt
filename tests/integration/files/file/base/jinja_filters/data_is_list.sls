{% set list = ['abcd','efgh','ijk','lmno','pqrs'] %}

{% set result = list | is_list() %}

{% include 'jinja_filters/common.sls' %}
