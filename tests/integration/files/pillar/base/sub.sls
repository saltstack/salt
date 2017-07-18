sub: sub_minion
lowercase_knights:
{% for knight in pillar.get('knights') %}
  - {{ knight|lower }}
{% endfor %}
uppercase_knights:
{% for knight in salt['pillar.get']('knights') %}
  - {{ knight|upper }}
{% endfor %}
