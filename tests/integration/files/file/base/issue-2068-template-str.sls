/tmp/issue-2068-template-str:
  virtualenv.managed:
    - no_site_packages: True
    - distribute: True

pep8-pip:
  pip.installed:
    - name: pep8
    - bin_env: /tmp/issue-2068-template-str
    - mirrors: http://testpypi.python.org/pypi
    - require:
      - virtualenv: /tmp/issue-2068-template-str
