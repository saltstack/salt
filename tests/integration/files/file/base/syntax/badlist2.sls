# C should fail with bad list error message
B:
  # ok
  file.exist:
    - name: /foo/bar/foobar
# ok
/foo/bar/foobar:
  file.exist

# nok
C:
  /foo/bar/foobar:
    file.exist
