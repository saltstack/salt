{%- set sshd_config_dir = pillar['git_pillar']['sshd_config_dir'] %}

{{ sshd_config_dir }}/sshd_config:
  file.managed:
    - source: salt://git_pillar/ssh/server/files/sshd_config
    - user: root
    {% if grains['os_family'] == 'FreeBSD' %}
    - group: wheel
    {% else %}
    - group: root
    {% endif %}
    - mode: 644
    - template: jinja

{{ sshd_config_dir }}/ssh_host_rsa_key:
  file.managed:
    - source: salt://git_pillar/ssh/server/files/ssh_host_rsa_key
    - user: root
    {% if grains['os_family'] == 'FreeBSD' %}
    - group: wheel
    {% else %}
    - group: root
    {% endif %}
    - mode: 600
    - template: jinja

{{ sshd_config_dir }}/ssh_host_rsa_key.pub:
  file.managed:
    - source: salt://git_pillar/ssh/server/files/ssh_host_rsa_key.pub
    - user: root
    {% if grains['os_family'] == 'FreeBSD' %}
    - group: wheel
    {% else %}
    - group: root
    {% endif %}
    - mode: 644
    - template: jinja

{%- if grains['os_family'] == 'Debian' %}
/var/run/sshd:
  file.directory:
    - user: root
    - group: root
    - mode: 755
{%- endif %}
