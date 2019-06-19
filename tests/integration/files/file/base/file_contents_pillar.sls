add_contents_pillar_sls:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test-lists-content-pillars') }}
    - contents_pillar: companions:three
