# Minimal pillar top for the resiliency single topology.
# ``test_fs_pillar_flip_mid_run`` rewrites this file mid-run to
# verify the pillar refresh pipeline survives an edit while a state
# is in flight.  Content is intentionally trivial.
base:
  '*':
    - common
