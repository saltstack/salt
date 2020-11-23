monty: python
os: {{ grains['os'] }}
{% if grains['os'] == 'Fedora' %}
class: redhat
{% else %}
class: other
{% endif %}

knights:
  - Lancelot
  - Galahad
  - Bedevere
  - Robin

level1:
  level2: foo

companions:
  three:
    - liz
    - jo
    - sarah jane
