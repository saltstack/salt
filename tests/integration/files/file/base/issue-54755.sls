issue-54755:
  file.managed:
    - name: {{ pillar['file_path'] }}
    - contents: issue-54755
    - unless: /bin/bash -c false
