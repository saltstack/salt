{% set result = 'Salt Rocks!' | hmac(shared_secret='topsecret', challenge_hmac='nMgLxwHPFyRgGfunkXXAI3Z/ZR4p5lmPTUjk2eGDqks=') %}

{% include 'jinja_filters/common.sls' %}
