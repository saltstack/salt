{{ pillar['name'] }}:
  file.managed:
    - contents_pillar: issue-50221
