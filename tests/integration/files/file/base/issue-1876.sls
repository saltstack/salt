/tmp/salttest/issue-1876:

  file:
    - managed
    - source: salt://testfile
    
  file.append:
    - text: foo

