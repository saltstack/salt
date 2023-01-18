{% set services_enabled = [] %}
{% set services_disabled = ['salt-master', 'salt-minion', 'salt-syndic', 'salt-api'] %}

{% for service in services_enabled %}
check_services_enabled_{{ service }}:
  service.enabled:
    - name: {{ service }}
{% endfor %}

{% for service in services_disabled %}
check_services_disabled_{{ service }}:
  service.disabled:
    - name: {{ service }}
{% endfor %}
