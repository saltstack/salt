import tests.pytests.unit.utils._lazy_test_module as m
import tests.pytests.unit.utils._lazy_test_module.pkg.sub as child

m.evaluation_counts.setdefault(__name__, 0)
m.evaluation_counts[__name__] += 1

name = __name__
if not child.mutated_from_parent:  # Trigger the lazy module's __getattribute__.
    child.mutated_from_parent = True
