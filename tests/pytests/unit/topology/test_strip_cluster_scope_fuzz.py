"""
Property-based (hypothesis) tests for :func:`salt.topology.router.strip_cluster_scope`.

Invariant: for any well-formed compound expression that embeds at least one
``C@`` token, after calling :func:`strip_cluster_scope` the result MUST either

* re-parse cleanly as a valid compound expression AND each non-operator token
  parses via :func:`salt.utils.minions.parse_target`
  (``residual == stripped-but-valid``), OR
* be returned unchanged because the function took one of the documented
  skip-strip paths (``not`` present, or a ``C@`` token adjacent to ``or``).

These tests complement the hand-written cases in :mod:`test_router.py` by
driving at least 100 generated inputs per property via :mod:`hypothesis`.
``hypothesis`` is a declared test dep in ``requirements/pytest.txt`` so
the real path always runs in CI; the ``try/except ImportError`` fallback
below is a defence for devs running against a minimal local venv --
pytest emits "skipped" at collection time instead of crashing.
"""

import pytest

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True
except ImportError:  # pragma: no cover - hypothesis is an optional test dep
    HAS_HYPOTHESIS = False

    # Stub objects so module decorators do not crash during collection
    # when hypothesis is missing.  The pytestmark skip below guarantees
    # none of the stubbed decorators run; this is purely to let import
    # complete so pytest can emit the skip at collection time.
    class _NoopDecorator:
        def __call__(self, *args, **kwargs):
            def _inner(fn):
                return fn

            if args and callable(args[0]):
                return args[0]
            return _inner

    def given(*_a, **_kw):  # noqa: D401
        return _NoopDecorator()

    def settings(*_a, **_kw):  # noqa: D401
        return _NoopDecorator()

    class HealthCheck:  # noqa: D401
        too_slow = None
        filter_too_much = None

    class _DummyStrategy:
        """A null-object stand-in for ``hypothesis.strategies.SearchStrategy``.

        Supports arbitrary attribute access and chained method calls
        (``st.lists(...).map(" ".join)``) so class-body decorator
        arguments can be constructed without ``AttributeError`` or
        ``TypeError`` when ``hypothesis`` is missing.  The pytestmark
        skip above means these strategies are never actually consumed.
        """

        def __call__(self, *a, **kw):
            return self

        def __getattr__(self, _name):
            return self

    _DUMMY = _DummyStrategy()

    class _StStub:
        def composite(self, _fn):
            # @st.composite wraps a generator-style strategy builder.
            # The decorated function is called at class-collection time
            # as ``_fn(...)`` to produce a strategy; preserve callable
            # shape here so those calls return a dummy strategy instead
            # of raising ``TypeError: 'NoneType' object is not
            # callable`` (which fails the whole module to collect).
            def _strategy_factory(*_a, **_kw):
                return _DUMMY

            return _strategy_factory

        def __getattr__(self, _name):
            return lambda *a, **k: _DUMMY

    st = _StStub()

import salt.topology.router as router
import salt.utils.minions as minions

pytestmark = pytest.mark.skipif(
    not HAS_HYPOTHESIS, reason="hypothesis not installed in this environment"
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_CLUSTER_NAMES = ["east", "west", "north", "south", "central", "eu-1", "us-2"]
_PLAIN_TOKENS = [
    "*",
    "web-*",
    "db-*",
    "minion1",
    "G@os:ubuntu",
    "G@os:centos",
    "L@a,b",
    "L@m1,m2",
    "I@role:web",
    "E@^web-\\d+$",
]
_BINOPS = ["and", "or"]


@st.composite
def _c_token(draw):
    n = draw(st.integers(min_value=1, max_value=3))
    names = draw(
        st.lists(
            st.sampled_from(_CLUSTER_NAMES),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    return "C@" + ",".join(names)


@st.composite
def _atom(draw, allow_c=True):
    """A single compound atom; optionally a C@ cluster token, else a plain token."""
    if allow_c and draw(st.booleans()):
        tok = draw(_c_token())
    else:
        tok = draw(st.sampled_from(_PLAIN_TOKENS))
    # Optional paren-wrap for grammar coverage (occasionally doubled).
    paren_depth = draw(st.integers(min_value=0, max_value=2))
    tok = ("(" * paren_depth) + tok + (")" * paren_depth)
    return tok


@st.composite
def _expr_with_c(draw, allow_not=False):
    """
    Generate a well-formed compound expression containing >=1 ``C@`` token.

    Grammar (approximate):
        expr   := [not] atom (op atom)*
        atom   := C@... | plain | '(' atom ')'
    """
    size = draw(st.integers(min_value=1, max_value=6))
    tokens = []
    if allow_not and draw(st.booleans()):
        tokens.append("not")
    tokens.append(draw(_atom(allow_c=True)))
    for _ in range(size - 1):
        tokens.append(draw(st.sampled_from(_BINOPS)))
        tokens.append(draw(_atom(allow_c=True)))
    expr = " ".join(tokens)
    if "C@" not in expr:
        # Ensure the generated expression actually exercises the strip-path.
        expr = expr + " and " + draw(_c_token())
    return expr


# ---------------------------------------------------------------------------
# Grammar oracle (mirrors _check_compound_minions tokenisation)
# ---------------------------------------------------------------------------


def _tokens_well_formed(tokens):
    """
    Rough compound-grammar check: no empty parens, no doubled operators,
    no leading/trailing operator, balanced parens.
    """
    if not tokens:
        return False
    if tokens[0] in {"and", "or"}:
        return False
    if tokens[-1] in {"and", "or", "not"}:
        return False
    prev = None
    depth = 0
    for tok in tokens:
        if tok == "(":
            depth += 1
            if prev not in (None, "and", "or", "not", "("):
                return False
        elif tok == ")":
            depth -= 1
            if depth < 0:
                return False
            if prev in ("and", "or", "not", "("):
                return False
        elif tok in {"and", "or"}:
            if prev in (None, "and", "or", "not", "("):
                return False
        elif tok == "not":
            # ``not`` only after a binop or at the head or after '('.
            if prev not in (None, "and", "or", "("):
                return False
        prev = tok
    return depth == 0


def _non_operator_tokens_parse(tokens):
    """
    Every non-operator token must parse via :func:`salt.utils.minions.parse_target`.

    ``parse_target`` is designed to always succeed structurally (unknown engine
    → ``engine=None``), so we check only that each non-operator yields a dict
    with the three expected keys.  This is a parse-liveness check equivalent
    to what :meth:`_check_compound_minions` does when it dispatches to each
    engine.
    """
    for tok in tokens:
        if tok in router._COMPOUND_OPERATORS:
            continue
        parsed = minions.parse_target(tok)
        if not isinstance(parsed, dict):
            return False
        if set(parsed) != {"engine", "delimiter", "pattern"}:
            return False
    return True


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


_SETTINGS = settings(
    max_examples=500,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)


class TestStripClusterScopeFuzz:
    """
    For every generated well-formed compound containing ``C@``, the strip
    either returns a cleanly-parseable residual OR took a documented skip-
    strip path (identity return).
    """

    @_SETTINGS
    @given(expr=_expr_with_c(allow_not=False))
    def test_no_not_strip_residual_parses(self, expr):
        residual = router.strip_cluster_scope(expr)
        if residual == expr:
            # Skip-strip path: expression has an ``or``-adjacent C@ token.
            # The identity return is correct; verify the trigger.
            assert _c_is_or_adjacent(expr), (
                "Unexpected identity-return without ``or``-adjacency "
                f"trigger:\n  input: {expr!r}"
            )
            return
        # Normal strip path: no leaked C@, residual re-parses.
        assert "C@" not in residual, (
            f"strip_cluster_scope leaked a C@ token:\n"
            f"  input:    {expr!r}\n"
            f"  residual: {residual!r}"
        )
        tokens = router._tokenize(residual)
        assert tokens, "strip_cluster_scope returned an empty residual"
        if residual == "*":
            return
        assert _tokens_well_formed(tokens), (
            f"Residual failed grammar check:\n"
            f"  input:    {expr!r}\n"
            f"  residual: {residual!r}\n"
            f"  tokens:   {tokens!r}"
        )
        assert _non_operator_tokens_parse(tokens), (
            f"Residual non-op token did not parse:\n"
            f"  input:    {expr!r}\n"
            f"  residual: {residual!r}"
        )

    @_SETTINGS
    @given(expr=_expr_with_c(allow_not=True))
    def test_either_parse_or_skip_strip(self, expr):
        residual = router.strip_cluster_scope(expr)
        if residual == expr:
            # Skip-strip path: ``not`` present or ``or``-adjacent C@.  The
            # original expression stays verbatim for the receiver to evaluate.
            assert "not" in router._tokenize(expr) or _c_is_or_adjacent(expr), (
                f"Unexpected identity-return for expression without "
                f"documented skip-strip trigger:\n  input: {expr!r}"
            )
            return
        tokens = router._tokenize(residual)
        if residual == "*":
            return
        assert _tokens_well_formed(tokens), (
            f"Residual failed grammar check:\n"
            f"  input:    {expr!r}\n"
            f"  residual: {residual!r}\n"
            f"  tokens:   {tokens!r}"
        )
        assert _non_operator_tokens_parse(tokens), (
            f"Residual non-op token did not parse:\n"
            f"  input:    {expr!r}\n"
            f"  residual: {residual!r}"
        )
        assert "C@" not in residual, (
            f"strip_cluster_scope leaked a C@ token:\n"
            f"  input:    {expr!r}\n"
            f"  residual: {residual!r}"
        )

    @_SETTINGS
    @given(
        expr=st.lists(
            st.sampled_from(_PLAIN_TOKENS + _BINOPS),
            min_size=1,
            max_size=8,
        ).map(" ".join)
    )
    def test_no_C_identity(self, expr):
        """
        Expressions without any ``C@`` token are returned unchanged
        (string in, string out, exact equality).  Grammar-malformed
        garbage is still returned unchanged because strip_cluster_scope
        is only responsible for C@ removal, not grammar normalisation.
        """
        assert router.strip_cluster_scope(expr) == expr


def _c_is_or_adjacent(expr):
    """Mirror of the ``or``-adjacency guard inside :func:`strip_cluster_scope`."""
    toks = router._tokenize(expr)
    for i, tok in enumerate(toks):
        if not router._is_c_token(tok):
            continue
        if i > 0 and toks[i - 1] == "or":
            return True
        if i + 1 < len(toks) and toks[i + 1] == "or":
            return True
    return False
