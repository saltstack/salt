unless_false_onlyif_true:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test.txt') }}
    - unless: /bin/false
    - onlyif: /bin/true

unless_true_onlyif_false:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test.txt') }}
    - unless: /bin/true
    - onlyif: /bin/false

unless_true_onlyif_true:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test.txt') }}
    - unless: /bin/true
    - onlyif: /bin/true

unless_false_onlyif_false:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test.txt') }}
    - contents: test
    - unless: /bin/false
    - onlyif: /bin/false
