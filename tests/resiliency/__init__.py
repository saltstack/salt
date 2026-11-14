# Marker for importability.  The resiliency suite is intentionally NOT
# under tests/pytests/ because it requires live docker infrastructure and
# must not run during normal pytest collection.  Pytest's auto-rootdir
# discovery picks up tests/resiliency/pytest.ini as the stop point.
