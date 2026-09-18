import json
import tempfile
import unittest
from pathlib import Path

from dashboard import create_app
from module.memory import SecondBrain


class DashboardMemoryTests(unittest.TestCase):
    def test_dashboard_endpoints_without_mt5(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(root=directory)
            client = app.test_client()
            self.assertEqual(client.get("/api/status").status_code, 200)
            self.assertEqual(client.get("/api/positions").get_json()["source"], "paper")
            self.assertEqual(client.get("/api/logs").status_code, 200)
            self.assertEqual(client.get("/api/memory").status_code, 200)
            self.assertEqual(client.get("/api/performance").status_code, 200)

    def test_dashboard_token_protection(self):
        import os
        old = os.environ.get("DASHBOARD_TOKEN")
        os.environ["DASHBOARD_TOKEN"] = "test-token"
        try:
            app = create_app(root=tempfile.mkdtemp())
            client = app.test_client()
            self.assertEqual(client.get("/api/status").status_code, 401)
            self.assertEqual(client.get("/api/status", headers={"X-Dashboard-Token": "test-token"}).status_code, 200)
        finally:
            if old is None:
                os.environ.pop("DASHBOARD_TOKEN", None)
            else:
                os.environ["DASHBOARD_TOKEN"] = old

    def test_remote_dashboard_requires_token(self):
        import os
        old_host = os.environ.get("DASHBOARD_HOST")
        old_token = os.environ.pop("DASHBOARD_TOKEN", None)
        os.environ["DASHBOARD_HOST"] = "0.0.0.0"
        try:
            with self.assertRaises(RuntimeError):
                create_app(root=tempfile.mkdtemp())
        finally:
            if old_host is None:
                os.environ.pop("DASHBOARD_HOST", None)
            else:
                os.environ["DASHBOARD_HOST"] = old_host
            if old_token is not None:
                os.environ["DASHBOARD_TOKEN"] = old_token

    def test_second_brain_records_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            brain = SecondBrain(path)
            brain.record("lesson", "Spread too high", "Skip signal", symbol="XAUUSD")
            rows = brain.recent()
            self.assertEqual(rows[0]["kind"], "lesson")
            self.assertEqual(rows[0]["metadata"]["symbol"], "XAUUSD")


if __name__ == "__main__":
    unittest.main()
