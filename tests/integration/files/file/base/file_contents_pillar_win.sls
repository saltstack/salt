add_contents_pillar_sls:
  file.managed:
    - name: C:\\Windows\\Temp\\test-lists-content-pillars
    - contents_pillar: companions:three
