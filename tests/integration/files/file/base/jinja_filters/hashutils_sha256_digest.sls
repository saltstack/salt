{% set result = 'Salt Rocks!' | sha256() %}

{% include 'jinja_filters/common.sls' %}
