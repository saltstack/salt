barrier:
  test.nop
  
{%- for x in [1,2,3,4,5,6,7,8,9,10] %}
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
