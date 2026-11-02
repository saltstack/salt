import salt.loader
import salt.matchers.compound_match as compound_match
from salt.matchers import grain_match
from salt.utils.context import func_globals_inject

opts = {
    "grains": {"example-grain": True},
    "pillar": {"example-pillar": True},
}
minion_id = "test-minion"
target = "G:example-grain:True and I:example-pillar:True or test-minion"


def salt_loader_matchers():
    current_matchers = salt.loader.matchers(opts)
    current_matchers["grain_match.match"](target, opts=opts, minion_id=minion_id)


def salt_matchers_dunder():
    grain_match.match(target, opts=opts, minion_id=minion_id)


def test_salt_loader_matchers(benchmark):
    with func_globals_inject(
        compound_match.match,
        __matchers__={},
        __opts__=opts,
        __salt__={},
        __grains__={},
        __pillar__={},
    ):
        benchmark.pedantic(salt_loader_matchers, iterations=10, rounds=5)


def test_salt_matchers_dunder(benchmark):
    with func_globals_inject(
        compound_match.match,
        __matchers__={
            "grain_match.match": grain_match.match,
            "compound_match.match": salt_loader_matchers,
        },
        __opts__=opts,
        __salt__={},
        __grains__={},
        __pillar__={},
    ):
        benchmark.pedantic(salt_matchers_dunder, iterations=10, rounds=5)
