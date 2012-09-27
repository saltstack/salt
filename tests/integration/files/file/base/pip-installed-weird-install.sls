/tmp/pip-installed-weird-install:
  virtualenv.managed:
    - no_site_packages: True
    - distribute: True

carbon-weird-setup:
  pip.installed:
    - name: carbon
    - no_deps: True
    - bin_env: /tmp/pip-installed-weird-install
    - mirrors: http://testpypi.python.org/pypi
    - require:
      - virtualenv: /tmp/pip-installed-weird-install
