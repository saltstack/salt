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
