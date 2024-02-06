This is a temporary fork that removes some optional dependencies while we await salt 3009. Only interested in darwin; for devenv poc.

```sh
pip-compile --output-file=requirements/static/pkg/py3.10/darwin.txt \
    requirements/darwin.txt \
    requirements/static/pkg/darwin.in

python setup.py bdist_wheel
```

removed:
- cherrypy (pulls in a LOT of stuff)
- setproctitle
- linode-python
- vultr
- apache-libcloud
- rpm-vercmp
