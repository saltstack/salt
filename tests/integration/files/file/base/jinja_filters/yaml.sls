{% set result = {"Question": "Quieres Café?"} %}

test:
  module.run:
    - name: test.echo
    - text: "{{ result | yaml }}"
