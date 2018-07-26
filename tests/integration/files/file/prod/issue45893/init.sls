test_non_base_env:
  archive.extracted:
    - name: {{ pillar['issue45893.name'] }}
    - source: salt://issue45893/custom.tar.gz
    - keep: False
