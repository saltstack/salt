# New Test Suite

Welcome to the *new* test suite for Salt!

Any test under this directory shall be written exploring the full capabilities of PyTest.
That means, no occurrences of the [TestCase](https://docs.python.org/3/library/unittest.html#unittest.TestCase) class
shall be used, neither our [customizations to it](../support/case.py).

## Purpose

While [PyTest](https://docs.pytest.org) can happily run unittest tests(withough taking advantage of most of PyTest's strengths),
this new path in the tests directory was created to provide a clear separation between the two approaches to writing tests.
Some(hopefully all) of the existing unittest tests might get ported to PyTest's style of writing tests, new tests should be added under
this directory tree, and, in the long run, this directoy shall become the top level tests directoy.
