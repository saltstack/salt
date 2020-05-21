# archive-test
vault:
    archive.extracted:
        - name: {{ pillar['unzip_to'] }}
        - source: salt://issue-56131.zip
        - source_hash: sha256=4fc6f049d658a414aca066fb11c2109d05b59f082d707d5d6355b6c574d25720
        - archive_format: zip
        - enforce_toplevel: False
        - unless:
            - echo hello && 1
