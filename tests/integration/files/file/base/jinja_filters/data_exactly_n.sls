{% set list = [True, False, False, True] %}

{% set result = list | exactly_n_true(2) %}

{% include 'jinja_filters/common.sls' %}
