barrier:
  cmd.run:
    - name: sleep 1
  
{%- for x in range(1, 10) %}
blah-{{x}}:
  cmd.run:
    - name: sleep 5
    - require:
      - barrier
      - barrier2
    - parallel: true
{% endfor %}

barrier2:
  test.nop
