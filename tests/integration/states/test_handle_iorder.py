"""
tests for host state
"""

from tests.support.case import ModuleCase


class HandleOrderTest(ModuleCase):
    """
    Validate that ordering works correctly
    """

    def test_handle_iorder(self):
        """
        Test the error with multiple states of the same type
        """
        ret = self.run_function("state.show_low_sls", mods="issue-7649-handle-iorder")

        sorted_chunks = [
            chunk["name"] for chunk in sorted(ret, key=lambda c: c.get("order"))
        ]

        expected = ["./configure", "make", "make install"]
        self.assertEqual(expected, sorted_chunks)
