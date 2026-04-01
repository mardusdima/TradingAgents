import unittest

from cli.utils import _build_analyst_selection_app


class CheckboxShortcutTests(unittest.TestCase):
    def test_toggle_all_shortcuts_are_registered_on_custom_prompt(self):
        app = _build_analyst_selection_app()
        bindings = set()
        for binding in app.key_bindings.bindings:
            parts = tuple(str(key) for key in binding.keys)
            bindings.add(parts)

        self.assertIn(("a",), bindings)
        self.assertIn(("A",), bindings)
        self.assertIn(("Keys.ControlA",), bindings)


if __name__ == "__main__":
    unittest.main()
