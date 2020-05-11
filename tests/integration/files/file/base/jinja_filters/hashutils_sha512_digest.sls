{% set result = 'Salt Rocks!' | sha512() %}

{% include 'jinja_filters/common.sls' %}
