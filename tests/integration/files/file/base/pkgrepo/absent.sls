{% if grains['os'] == 'CentOS' %}

# START CentOS pkgrepo tests
epel-salttest:
  pkgrepo:
    - absent
# END CentOS pkgrepo tests

{% else %}

# No matching OS grain for pkgrepo management, just run something that will
# return a True result
date:
  cmd:
    - run

{% endif %}
