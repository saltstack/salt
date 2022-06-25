import sys

import pytest
import salt.utils.decorators.dunder_utils as dunder_utils
from tests.conftest import CODE_DIR


def test_runtime_errors():
    func_alias_dict = {}

    with pytest.raises(RuntimeError) as exc:
        dunder_utils.deprecated("by", func_alias_dict)

    assert (
        str(exc.value)
        == "Only keyword arguments are acceptable when calling this function"
    )

    with pytest.raises(RuntimeError) as exc:
        dunder_utils.deprecated("foo", by="by")

    assert (
        str(exc.value)
        == "Only keyword arguments are acceptable when calling this function"
    )

    with pytest.raises(RuntimeError) as exc:
        dunder_utils.deprecated()

    assert (
        str(exc.value)
        == "The 'by' argument is mandatory and shall be passed as a keyword argument'"
    )

    with pytest.raises(RuntimeError) as exc:
        dunder_utils.deprecated(by="by")

    assert str(exc.value) == (
        "The 'by' argument needs to be passed the function reference that "
        "deprecates the decorated function"
    )


def test_decoration(tmp_path, shell):
    module = tmp_path / "custompkg"
    custom_module_contents = """
    import sys
    from salt.utils.decorators.dunder_utils import deprecated

    def new_func():
        print("new_func", file=sys.stderr)

    @deprecated(by=new_func)
    def old_func():
        print("old_func", file=sys.stderr)
        new_func()
    """
    call_module_contents = """
    import json
    import sys
    import warnings
    sys.path.insert(0, "{}")
    sys.path.insert(1, "{}")

    import custompkg.mod

    data = {{
        "__load__": list(custompkg.mod.__load__),
        "__load_type__": custompkg.mod.__load__.__class__.__name__,
        "__func_alias__": custompkg.mod.__func_alias__,
    }}

    # Call the new func
    with warnings.catch_warnings(record=True) as issued_warnings:
        # Cause all warnings to always be triggered.
        warnings.simplefilter("always")

        custompkg.mod.new_func()

    data["new_func_warnings"] = [
        {{
            "message": str(w.message),
            "category": w.message.__class__.__name__,
            "filename": w.filename,
            "lineno": w.lineno,
            "line": w.line,
        }}
        for w in issued_warnings
    ]

    # Call the deprecated function
    with warnings.catch_warnings(record=True) as issued_warnings:
        # Cause all warnings to always be triggered.
        warnings.simplefilter("always")

        custompkg.mod.old_func()

    data["old_func_warnings"] = [
        {{
            "message": str(w.message),
            "category": w.message.__class__.__name__,
            "filename": w.filename,
            "lineno": w.lineno,
            "line": w.line,
        }}
        for w in issued_warnings
    ]

    print(data, file=sys.stderr)

    print(json.dumps(data))
    """.format(
        CODE_DIR, tmp_path
    )
    with pytest.helpers.temp_file("callit.py", call_module_contents) as callit:
        with pytest.helpers.temp_file(module / "__init__.py", ""):
            with pytest.helpers.temp_file(module / "mod.py", custom_module_contents):
                proc = shell.run(sys.executable, str(callit), cwd=str(tmp_path))
                assert proc.returncode == 0
                assert proc.stdout
                data = proc.data
                assert data["__load__"] == ["old_func"]
                assert data["__func_alias__"]["old_func"] == "new_func"
                assert data["__load_type__"] == "LoadIterable"
                assert not data["new_func_warnings"]
                assert data["old_func_warnings"] == [
                    {
                        "category": "DeprecationWarning",
                        "filename": str(callit),
                        "line": None,
                        "lineno": 38,
                        "message": (
                            "The __utils__ loader functionality will be "
                            "removed in version 3008. Please import "
                            "'salt.utils.mod' and call "
                            "'salt.utils.mod.new_func()' directly. "
                            "Please note any required argument changes "
                            "for this new function call."
                        ),
                    }
                ]


def test_decoration_existing_dunder_load(tmp_path, shell):
    module = tmp_path / "custompkg"
    custom_module_contents = """
    import sys
    from salt.utils.decorators.dunder_utils import deprecated

    __load__ = ["foo"]

    def foo():
        pass

    def new_func():
        print("new_func", file=sys.stderr)

    @deprecated(by=new_func)
    def old_func():
        print("old_func", file=sys.stderr)
        new_func()
    """
    call_module_contents = """
    import json
    import sys
    import warnings
    sys.path.insert(0, "{}")
    sys.path.insert(1, "{}")

    import custompkg.mod

    data = {{
        "__load__": list(custompkg.mod.__load__),
        "__load_type__": custompkg.mod.__load__.__class__.__name__,
        "__func_alias__": custompkg.mod.__func_alias__,
    }}

    # Call the new func
    with warnings.catch_warnings(record=True) as issued_warnings:
        # Cause all warnings to always be triggered.
        warnings.simplefilter("always")

        custompkg.mod.new_func()

    data["new_func_warnings"] = [
        {{
            "message": str(w.message),
            "category": w.message.__class__.__name__,
            "filename": w.filename,
            "lineno": w.lineno,
            "line": w.line,
        }}
        for w in issued_warnings
    ]

    # Call the deprecated function
    with warnings.catch_warnings(record=True) as issued_warnings:
        # Cause all warnings to always be triggered.
        warnings.simplefilter("always")

        custompkg.mod.old_func()

    data["old_func_warnings"] = [
        {{
            "message": str(w.message),
            "category": w.message.__class__.__name__,
            "filename": w.filename,
            "lineno": w.lineno,
            "line": w.line,
        }}
        for w in issued_warnings
    ]

    print(data, file=sys.stderr)

    print(json.dumps(data))
    """.format(
        CODE_DIR, tmp_path
    )
    with pytest.helpers.temp_file("callit.py", call_module_contents) as callit:
        with pytest.helpers.temp_file(module / "__init__.py", ""):
            with pytest.helpers.temp_file(module / "mod.py", custom_module_contents):
                proc = shell.run(sys.executable, str(callit), cwd=str(tmp_path))
                assert proc.returncode == 0
                assert proc.stdout
                data = proc.data
                assert data["__load__"] == ["foo", "old_func"]
                assert data["__func_alias__"]["old_func"] == "new_func"
                assert data["__load_type__"] == "LoadIterable"
                assert not data["new_func_warnings"]
                assert data["old_func_warnings"] == [
                    {
                        "category": "DeprecationWarning",
                        "filename": str(callit),
                        "line": None,
                        "lineno": 38,
                        "message": (
                            "The __utils__ loader functionality will be "
                            "removed in version 3008. Please import "
                            "'salt.utils.mod' and call "
                            "'salt.utils.mod.new_func()' directly. "
                            "Please note any required argument changes "
                            "for this new function call."
                        ),
                    }
                ]
