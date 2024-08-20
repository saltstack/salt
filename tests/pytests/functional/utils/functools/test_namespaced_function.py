import logging
import sys
import warnings

import pytest

from salt.utils.functools import namespaced_function
from tests.conftest import CODE_DIR

log = logging.getLogger(__name__)


def preserve_context_ids(value):
    return f"preserve_context={value}"


@pytest.fixture(params=[True, False], ids=preserve_context_ids)
def preserve_context(request):
    return request.param


def test_namespacing(tmp_path, shell):
    pkgpath = tmp_path / "foopkg"
    mod1_contents = """
    import json
    import time

    def func_1():
        return time.time()

    def main():
        data = {
            "func1": func_1(),
            "module": func_1.__module__,
            "time_present": "time" in func_1.__globals__
        }
        print(json.dumps(data))

    if __name__ == "__main__":
        main()
    """
    mod2_contents = """
    import json
    from salt.utils.functools import namespaced_function
    from foopkg.mod1 import func_1

    func_1 = namespaced_function(func_1, globals())

    def main():
        data = {
            "func1": func_1(),
            "module": func_1.__module__,
            "time_present": "time" in func_1.__globals__
        }
        print(json.dumps(data))

    if __name__ == "__main__":
        main()
    """
    run1_contents = """
    import sys
    sys.path.insert(0, '{}')
    import foopkg.mod1

    foopkg.mod1.main()
    """.format(
        CODE_DIR
    )
    run2_contents = """
    import sys
    sys.path.insert(0, '{}')
    import foopkg.mod2

    foopkg.mod2.main()
    """.format(
        CODE_DIR
    )
    with pytest.helpers.temp_file(
        "run1.py", contents=run1_contents, directory=tmp_path
    ), pytest.helpers.temp_file(
        "run2.py", contents=run2_contents, directory=tmp_path
    ), pytest.helpers.temp_file(
        "__init__.py", contents="", directory=pkgpath
    ), pytest.helpers.temp_file(
        "mod1.py", mod1_contents, directory=pkgpath
    ), pytest.helpers.temp_file(
        "mod2.py", mod2_contents, directory=pkgpath
    ):
        ret = shell.run(sys.executable, str(tmp_path / "run1.py"), cwd=str(tmp_path))
        log.warning(ret)
        assert ret.returncode == 0
        assert ret.data["module"] == "foopkg.mod1"
        assert ret.data["time_present"] is True
        assert isinstance(ret.data["func1"], float)
        ret = shell.run(sys.executable, str(tmp_path / "run2.py"), cwd=str(tmp_path))
        log.warning(ret)
        assert ret.returncode == 0
        assert ret.data["module"] == "foopkg.mod2"
        assert isinstance(ret.data["func1"], float)
        assert ret.data["time_present"] is True


def test_deprecated_defaults_kwarg():
    def foo():
        pass

    with warnings.catch_warnings(record=True) as w:
        # Cause all warnings to always be triggered.
        warnings.simplefilter("always")
        namespaced_function(foo, globals(), defaults={"foo": 1})

    assert str(w[-1].message) == (
        "Passing 'defaults' to 'namespaced_function' is deprecated, slated "
        "for removal in 3008.0 (Argon) and no longer does anything for the function "
        "being namespaced."
    )


def test_deprecated_preserve_context_kwarg(preserve_context):
    def foo():
        pass

    with warnings.catch_warnings(record=True) as w:
        # Cause all warnings to always be triggered.
        warnings.simplefilter("always")
        namespaced_function(foo, globals(), preserve_context=preserve_context)

    assert str(w[-1].message) == (
        "Passing 'preserve_context' to 'namespaced_function' is deprecated, slated "
        "for removal in 3008.0 (Argon) and no longer does anything for the function "
        "being namespaced."
    )
