one:
  file.managed:
    - name: {{ pillar['file1'] }}
    - source: {{ pillar['source'] }}

# This should run because there were changes
two:
  test.succeed_without_changes:
    - {{ pillar['req'] }}:
      - file: one

# Run the same state as "one" again, this should not cause changes
three:
  file.managed:
    - name: {{ pillar['file2'] }}
    - source: {{ pillar['source'] }}

# This should not run because there should be no changes
four:
  test.succeed_without_changes:
    - {{ pillar['req'] }}:
      - file: three
