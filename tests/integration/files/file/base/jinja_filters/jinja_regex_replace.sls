{% set result = 'lets replace spaces' | regex_replace('\s+', '__') %}

{% include 'jinja_filters/common.sls' %}
