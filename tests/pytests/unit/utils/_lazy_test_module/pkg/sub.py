import tests.pytests.unit.utils._lazy_test_module as m

m.evaluation_counts.setdefault(__name__, 0)
m.evaluation_counts[__name__] += 1

mutated_from_parent = False
