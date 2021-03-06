{% if grains['os'] == 'CentOS' %}

# START CentOS pkgrepo tests
epel-salttest:
  pkgrepo:
    - absent
# END CentOS pkgrepo tests

{% elif grains['os'] == 'Ubuntu' %}

firefox-beta:
  pkgrepo.absent:
    - name: deb http://ppa.launchpad.net/mozillateam/firefox-next/ubuntu {{ grains['oscodename'] }} main

kubuntu-ppa:
  pkgrepo.absent:
    - ppa: kubuntu-ppa/backports

{% else %}

# No matching OS grain for pkgrepo management, just run something that will
# return a True result
date:
  cmd:
    - run

{% endif %}
