{% set services_enabled = ['salt-master', 'salt-minion', 'salt-syndic', 'salt-api'] %}
{% set services_disabled = [] %}

{% for service in services_enabled %}
check_services_enabled_{{ service }}:
  service.enabled:
    - name: {{ service }}
run_if_changes_{{ service }}:
  cmd.run:
    - name: failtest service is enabled
    - onchanges:
      - service: check_services_enabled_{{ service }}
{% endfor %}

{% for service in services_disabled %}
check_services_disabled_{{ service }}:
  service.disabled:
    - name: {{ service }}
run_if_changes_{{ service }}:
  cmd.run:
    - name: failtest service is disabled
    - onchanges:
      - service: check_services_disabled_{{ service }}
{% endfor %}
