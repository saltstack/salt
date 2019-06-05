somefile-exists:
  file:
    - managed
    - name: {{ pillar['name'] }}

somefile-blockreplace:
  file:
    - blockreplace
    - append_if_not_found: true
    - name: {{ pillar['name'] }}
    - template: jinja
    - source: salt://issue-49043
    - require:
      - file: somefile-exists
    - context:
        unicode_string: "\xe4\xf6\xfc"
