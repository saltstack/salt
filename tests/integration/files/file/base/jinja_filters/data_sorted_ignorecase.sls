{% set list = ['lmno','efgh','Ijk','Pqrs','Abcd'] %}

{% set result = list | sorted_ignorecase() %}

{% include 'jinja_filters/common.sls' %}
