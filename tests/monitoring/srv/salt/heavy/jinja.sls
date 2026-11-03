generate_heavy_file:
  file.managed:
    - name: /tmp/heavy_jinja_output
    - source: salt://heavy/heavy_template.jinja
    - template: jinja
    - context:
        iterations: 500
        sub_iterations: 100
