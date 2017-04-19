{%- set sshd_config_dir = pillar['git_pillar']['sshd_config_dir'] %}

{{ sshd_config_dir }}/sshd_config:
  file.managed:
    - source: salt://git_pillar/ssh/server/files/sshd_config
    - user: root
    - group: root
    - mode: 644
    - template: jinja

{{ sshd_config_dir }}/ssh_host_rsa_key:
  file.managed:
    - source: salt://git_pillar/ssh/server/files/ssh_host_rsa_key
    - user: root
    - group: root
    - mode: 600
    - template: jinja

{{ sshd_config_dir }}/ssh_host_rsa_key.pub:
  file.managed:
    - source: salt://git_pillar/ssh/server/files/ssh_host_rsa_key.pub
    - user: root
    - group: root
    - mode: 644
    - template: jinja

start_sshd:
  cmd.run:
    - name: '{{ pillar['git_pillar']['sshd_bin'] }} -f {{ sshd_config_dir }}/sshd_config'
    - require:
      - file: {{ sshd_config_dir }}/sshd_config
      - file: {{ sshd_config_dir }}/ssh_host_rsa_key
      - file: {{ sshd_config_dir }}/ssh_host_rsa_key.pub
