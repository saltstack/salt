{% if grains['os'] == 'Windows' %}
  {% set test_false = 'cmd.exe /c exit 1' %}
  {% set test_true = 'cmd.exe /c exit 0' %}
{% elif grains['os'] == 'MacOS' or grains['os'] == 'FreeBSD' %}
  {% set test_false = '/usr/bin/false' %}
  {% set test_true = '/usr/bin/true' %}
{% else %}
  {% set test_false = '/bin/false' %}
  {% set test_true = '/bin/true' %}
{% endif %}

unless_false_onlyif_true:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test.txt') }}
    - unless: {{ test_false }}
    - onlyif: {{ test_true }}

unless_true_onlyif_false:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test.txt') }}
    - unless: {{ test_true }}
    - onlyif: {{ test_false }}

unless_true_onlyif_true:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test.txt') }}
    - unless: {{ test_true }}
    - onlyif: {{ test_true }}

unless_false_onlyif_false:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test.txt') }}
    - contents: test
    - unless: {{ test_false }}
    - onlyif: {{ test_false }}
