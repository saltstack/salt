add_contents_pillar_sls:
  file.managed:
    - name: /tmp/test-lists-content-pillars
    - contents_pillar: companions:three
