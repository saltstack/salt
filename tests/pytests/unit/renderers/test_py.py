import textwrap

import pytest

import salt.renderers.py as py


@pytest.fixture
def configure_loader_modules():
    return {
        py: {
            "__salt__": {
                "cp.get_file_str": lambda path, saltenv="base": f"contents:{path}"
            },
            "__grains__": {},
            "__pillar__": {},
            "__opts__": {"renderer": "py"},
        }
    }


def test_py_renderer_supports_salt_dot_notation(tmp_path):
    sls_path = tmp_path / "cp_fail.sls"
    sls_path.write_text(
        textwrap.dedent(
            """\
            #!py

            def run():
                return {"ret": __salt__.cp.get_file_str("salt://cp_fail.sls")}
            """
        ),
        encoding="utf-8",
    )

    rendered = py.render(
        str(sls_path),
        saltenv="base",
        sls="cp_fail",
        tmplpath=str(sls_path),
    )

    assert rendered == {"ret": "contents:salt://cp_fail.sls"}

