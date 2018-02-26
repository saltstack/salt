{%- set user = pillar['git_pillar']['user'] %}

{{ user }}:
  user.present:
    - gid_from_name: True
    - password: '$6$saYbZFw2$rtmvt2LOYchvlM22y34mCs7FiIN4Fq27rmv/whr/M.oPrgfCDhP5uJqnfe6uwFj90FvwA45rhZplnRNMgiY.J.'
    - require:
      - group: {{ user }}
  group.present: []

/home/{{ user }}/.ssh:
  file.directory:
    - user: {{ user }}
    - group: {{ user }}
    - dir_mode: 700
    - require:
      - user: {{ user }}
      - group: {{ user }}

/home/{{ user }}/.ssh/authorized_keys:
  file.managed:
    - source: salt://git_pillar/ssh/user/files/authorized_keys
    - user: {{ user }}
    - group: {{ user }}
    - mode: 600

# Custom SSH command
{{ pillar['git_pillar']['git_ssh'] }}:
  file.managed:
    - source: salt://git_pillar/ssh/user/files/git_ssh
    - user: {{ user }}
    - group: {{ user }}
    - mode: 755
    - template: jinja

/root/.ssh:
  file.directory:
    - dir_mode: 700
    - user: root

/root/.ssh/{{ pillar['git_pillar']['id_rsa_nopass'] }}:
  file.managed:
    - source: salt://git_pillar/ssh/user/files/id_rsa_nopass
    - user: root
    - group: root
    - mode: 600

/root/.ssh/{{ pillar['git_pillar']['id_rsa_nopass'] }}.pub:
  file.managed:
    - source: salt://git_pillar/ssh/user/files/id_rsa_nopass.pub
    - user: root
    - group: root
    - mode: 644

/root/.ssh/{{ pillar['git_pillar']['id_rsa_withpass'] }}:
  file.managed:
    - source: salt://git_pillar/ssh/user/files/id_rsa_withpass
    - user: root
    - group: root
    - mode: 600

/root/.ssh/{{ pillar['git_pillar']['id_rsa_withpass'] }}.pub:
  file.managed:
    - source: salt://git_pillar/ssh/user/files/id_rsa_withpass.pub
    - user: root
    - group: root
    - mode: 644
