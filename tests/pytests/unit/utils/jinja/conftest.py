"""
Tests for salt.utils.jinja
"""
import pytest


class MockFileClient:
    """
    Does not download files but records any file request for testing
    """

    def __init__(self, loader=None):
        if loader:
            loader._file_client = self
        self.requests = []
        self.opts = {}

    def get_file(self, template, dest="", makedirs=False, saltenv="base"):
        self.requests.append(
            {"path": template, "dest": dest, "makedirs": makedirs, "saltenv": saltenv}
        )


@pytest.fixture
def mock_file_client(loader=None):
    return MockFileClient(loader)


@pytest.fixture
def template_dir(tmp_path):
    templates_dir = tmp_path / "files" / "test"
    templates_dir.mkdir(parents=True, exist_ok=True)
    return templates_dir


@pytest.fixture
def hello_import(macro_template, template_dir):
    contents = """{% from 'macro' import mymacro -%}
    {% from 'macro' import mymacro -%}
    {{ mymacro('Hey') ~ mymacro(a|default('a'), b|default('b')) }}
    """

    with pytest.helpers.temp_file(
        "hello_import", directory=template_dir, contents=contents
    ) as hello_import_filename:
        yield hello_import_filename


@pytest.fixture
def macro_template(template_dir):
    contents = """# macro
    {% macro mymacro(greeting, greetee='world') -%}
    {{ greeting ~ ' ' ~ greetee }} !
    {%- endmacro %}
    """

    with pytest.helpers.temp_file(
        "macro", directory=template_dir, contents=contents
    ) as macro_filename:
        yield macro_filename
