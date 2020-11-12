test_ext_grain:
  file.managed:
    - name: {{ pillar['output_to_path'] }}
    - contents: {{ grains['my_grain'] }}
    - contents_newline: false
