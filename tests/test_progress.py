"""进度存档与评分测试。"""

import json
import tempfile
import unittest
from pathlib import Path

from arrow_game.progress import ProgressData, ProgressStore, calculate_rating


class ProgressTests(unittest.TestCase):
    def test_record_unlocks_next_level_and_keeps_best_results(self) -> None:
        progress = ProgressData()
        progress.record_completion(0, 2, 900, 30.0, 5)
        progress.record_completion(0, 1, 700, 25.0, 5)
        record = progress.record_for(0)
        self.assertEqual(progress.unlocked_level, 1)
        self.assertEqual(record.stars, 2)
        self.assertEqual(record.best_score, 900)
        self.assertEqual(record.best_time, 25.0)

    def test_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.json"
            store = ProgressStore(path, 5)
            progress = ProgressData()
            progress.record_completion(0, 3, 1200, 18.5, 5)
            store.save(progress)
            loaded = store.load()
            self.assertEqual(loaded.unlocked_level, 1)
            self.assertEqual(loaded.record_for(0).best_score, 1200)
            self.assertEqual(loaded.record_for(0).stars, 3)

    def test_broken_save_file_falls_back_to_new_progress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.json"
            path.write_text("{broken", encoding="utf-8")
            loaded = ProgressStore(path, 5).load()
            self.assertEqual(loaded.unlocked_level, 0)
            self.assertEqual(loaded.records, {})

    def test_untrusted_values_are_clamped(self) -> None:
        raw = {
            "unlocked_level": 999,
            "records": {"0": {"stars": 9, "best_score": -3, "best_time": -1}},
        }
        progress = ProgressData.from_dict(raw, 5)
        self.assertEqual(progress.unlocked_level, 4)
        self.assertEqual(progress.record_for(0).stars, 3)
        self.assertEqual(progress.record_for(0).best_score, 0)
        self.assertIsNone(progress.record_for(0).best_time)

    def test_rating_penalizes_hints_mistakes_and_auto_solve(self) -> None:
        self.assertEqual(calculate_rating(3, 3, 20, 0, 30)[0], 3)
        self.assertEqual(calculate_rating(3, 2, 35, 1, 30)[0], 2)
        stars, score = calculate_rating(3, 3, 10, 0, 30, auto_used=True)
        self.assertEqual(stars, 1)
        self.assertLess(score, 1500)


if __name__ == "__main__":
    unittest.main()
