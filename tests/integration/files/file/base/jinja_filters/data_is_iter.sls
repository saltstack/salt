{% set list = ['abcd','efgh','ijk','lmno','pqrs'] %}

{% set result = list | is_iter() %}

{% include 'jinja_filters/common.sls' %}
