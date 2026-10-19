import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import storage


class PersistenceTests(unittest.TestCase):
    def test_default_scenario_keeps_a_new_rate_after_reload(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "loan.db"
            with patch.object(storage, "DB_PATH", database), patch.dict(
                os.environ, {"PASSWORD": "test-password"}
            ):
                app = AppTest.from_file(str(app_path)).run(timeout=30)
                self.assertFalse(app.exception)
                self.assertEqual(app.text_input(key="scenario_name").value, "current_save")

                app.number_input(key="rate_value").set_value(7.1)
                app.date_input(key="rate_date").set_value(date(2026, 10, 19))
                next(button for button in app.button if button.label == "Add Rate").click().run(timeout=30)

                next(field for field in app.text_input if field.label == "Enter password to enable saving").set_value(
                    "test-password"
                ).run(timeout=30)
                next(button for button in app.button if button.label == "💾 Save").click().run(timeout=30)

                self.assertFalse(app.exception)
                self.assertIn(
                    {"date": "2026-10-19", "rate": 7.1},
                    storage.load_scenario("current_save")["rates"],
                )

                reloaded = AppTest.from_file(str(app_path)).run(timeout=30)
                self.assertFalse(reloaded.exception)
                self.assertIn(
                    (date(2026, 10, 19), 7.1),
                    [(rate.effective_date, rate.rate) for rate in reloaded.session_state["rates"]],
                )


if __name__ == "__main__":
    unittest.main()
