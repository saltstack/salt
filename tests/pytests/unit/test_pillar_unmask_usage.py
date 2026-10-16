"""
Guard against internal code calling the masking pillar functions without
saying whether it wants masked or unmasked output.

``__salt__["pillar.get"]`` (and friends) default to *masked* output outside of
the template/pillar renderers, so every scalar comes back as ``"**********"``.
Code that consumes the value (type checks, file contents, connection strings)
must pass ``unmask=True``; code that only displays it can opt out explicitly
via ``ALLOWED`` below.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SALT_DIR = REPO_ROOT / "salt"

MASKING_FUNCS = frozenset(
    {"pillar.get", "pillar.items", "pillar.item", "pillar.raw", "pillar.ext"}
)

# salt-ssh wrapper modules have their own pillar implementation which has no
# ``unmask`` argument and always returns real values.
EXEMPT_DIRS = (SALT_DIR / "client" / "ssh" / "wrapper",)

# (path relative to salt/, enclosing function) -> reason
ALLOWED = {
    ("modules/oracle.py", "show_dbs"): "display only; credentials stay masked",
    ("modules/oracle.py", "show_pillar"): "display only",
    ("modules/oracle.py", "version"): "only uses the keys for a membership test",
    ("modules/seed.py", "mkconfig"): "return value is ignored",
}


class _Finder(ast.NodeVisitor):
    """
    Collect masking pillar calls that don't pass ``unmask``, tracking the
    enclosing function name so display-only callers can be allowed.
    """

    def __init__(self, rel):
        self.rel = rel
        self.scope = []
        self.found = []

    def _visit_scope(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = _visit_scope

    def visit_Call(self, node):
        func = node.func
        if (
            isinstance(func, ast.Subscript)
            and isinstance(func.slice, ast.Constant)
            and func.slice.value in MASKING_FUNCS
            and not any(kw.arg == "unmask" for kw in node.keywords)
        ):
            name = self.scope[-1] if self.scope else "<module>"
            if (self.rel, name) not in ALLOWED:
                self.found.append(
                    f"salt/{self.rel}:{node.lineno} ({name}) {func.slice.value}"
                )
        self.generic_visit(node)


def _violations():
    found = []
    for path in sorted(SALT_DIR.rglob("*.py")):
        if any(parent in EXEMPT_DIRS for parent in path.parents):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        finder = _Finder(path.relative_to(SALT_DIR).as_posix())
        finder.visit(tree)
        found.extend(finder.found)
    return found


def test_internal_pillar_calls_choose_masking_explicitly():
    violations = _violations()
    assert not violations, (
        "Pass unmask=True (to consume the value) or add the call to ALLOWED "
        "with a reason (display only):\n" + "\n".join(violations)
    )
