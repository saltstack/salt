from sphinx.locale import l_, _

from sphinx.domains import python as python_domain


class SaltModuleIndex(python_domain.PythonModuleIndex):
    name = 'modindex'
    localname = l_('Salt Module Index')
    shortname = l_('all salt modules')


class SaltDomain(python_domain.PythonDomain):
    name = 'salt'
    label = 'Salt'
    data_version = 2

    indices = [
        SaltModuleIndex,
    ]


# Monkey-patch the Python domain remove the python module index
python_domain.PythonDomain.indices = []


def setup(app):
    app.add_domain(SaltDomain)
