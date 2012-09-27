/tmp/issue-2028-pip-installed:
  virtualenv.managed:
    - no_site_packages: True
    - distribute: True

supervisord-pip:
    pip.installed:
      - name: supervisor
      - bin_env: /tmp/issue-2028-pip-installed
      - mirrors: http://testpypi.python.org/pypi
      - require:
        - virtualenv: /tmp/issue-2028-pip-installed
