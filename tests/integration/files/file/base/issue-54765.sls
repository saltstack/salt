{% from "issue-54765-map.jinja" import defaults with context %}

issue-54765:
  file.managed:
    - name: {{ pillar['file_path'] }}
    - contents: {{ defaults['foo'] }}
