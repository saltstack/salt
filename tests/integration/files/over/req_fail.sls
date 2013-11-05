fail_stage:
  match: '*'
  sls:
    - fail
req_fail:
  match: '*'
  sls:
    - fail
  require:
    - fail_stage
