{% for i in range(100) %}
/tmp/stress_file_{{ i }}:
  file.managed:
    - contents: "Stress test file content for index {{ i }}. This is repeated many times to increase state size. {{ 'A' * 100 }}"
    - makedirs: True
{% endfor %}
