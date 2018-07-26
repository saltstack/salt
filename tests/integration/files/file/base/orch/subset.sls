test subset:
  salt.state:
    - tgt: '*'
    - subset: 1
    - sls: test
