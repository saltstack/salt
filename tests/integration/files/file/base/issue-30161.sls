unless_false_onlyif_true:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test.txt') }}
{% if grains['os'] == 'Windows' %}
    - unless: cmd.exe /c exit 1
    - onlyif: cmd.exe /c exit 0
{% else %}
    - unless: /bin/false
    - onlyif: /bin/true
{% endif %}

unless_true_onlyif_false:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test.txt') }}
{% if grains['os'] == 'Windows' %}
    - unless: cmd.exe /c exit 0
    - onlyif: cmd.exe /c exit 1
{% else %}
    - unless: /bin/true
    - onlyif: /bin/false
{% endif %}

unless_true_onlyif_true:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test.txt') }}
{% if grains['os'] == 'Windows' %}
    - unless: cmd.exe /c exit 0
    - onlyif: cmd.exe /c exit 0
{% else %}
    - unless: /bin/true
    - onlyif: /bin/true
{% endif %}

unless_false_onlyif_false:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test.txt') }}
    - contents: test
{% if grains['os'] == 'Windows' %}
    - unless: cmd.exe /c exit 1
    - onlyif: cmd.exe /c exit 1
{% else %}
    - unless: /bin/false
    - onlyif: /bin/false
{% endif %}
