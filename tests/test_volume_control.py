import json
import tempfile
import unittest
from pathlib import Path

from module.volume_control import VolumeController, calculate_risk_volume, risk_corrected_percent


class VolumeControlTests(unittest.TestCase):
    def test_risk_corrector_never_below_base_or_above_max(self):
        self.assertEqual(risk_corrected_percent(1, 1000, 2, 1, 1000, 2), 1)
        self.assertLessEqual(risk_corrected_percent(1, 1000, 2, 100, -1000, 2), 2)

    def test_volume_uses_stop_distance_and_hard_cap(self):
        volume = calculate_risk_volume(1000, 1, 2000, 1990, 1, 1, max_target=0.01)
        self.assertEqual(volume, 0.01)

    def test_change_is_logged_and_rollback_is_possible(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = VolumeController(Path(directory) / "state.json", Path(directory) / "volume_changes.log", max_target=0.1, min_observation_days=0)
            change = controller.record_change(0.02, 1.0, "stable PAPER", "operator")
            self.assertEqual(change.new_volume, 0.02)
            self.assertEqual(len(Path(directory, "volume_changes.log").read_text().splitlines()), 1)
            rollback = controller.rollback(0.01, "drawdown increase", "operator")
            self.assertEqual(rollback.status, "ROLLBACK")
            self.assertEqual(json.loads(Path(directory, "state.json").read_text())["current_volume"], 0.01)

    def test_hard_target_rejects_above_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = VolumeController(Path(directory) / "state.json", Path(directory) / "volume_changes.log", max_target=0.02, min_observation_days=0)
            change = controller.record_change(0.10, 1.0, "attempt", "operator")
            self.assertEqual(change.new_volume, 0.02)


if __name__ == "__main__":
    unittest.main()
