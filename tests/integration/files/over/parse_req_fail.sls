fail_stage:
  match: '*'
  sls:
    - failparse
req_fail:
  match: '*'
  sls:
    - fail
  require:
    - fail_stage
