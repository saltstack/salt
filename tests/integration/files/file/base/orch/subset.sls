test subset:
  salt.state:
    - tgt: '*minion'
    - subset: 1
    - sls: test
