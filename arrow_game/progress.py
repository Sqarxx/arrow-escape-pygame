"""游戏进度、评分与 JSON 存档。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class LevelRecord:
    stars: int = 0
    best_score: int = 0
    best_time: float | None = None


@dataclass(slots=True)
class ProgressData:
    unlocked_level: int = 0
    records: dict[int, LevelRecord] = field(default_factory=dict)

    def is_unlocked(self, level_index: int) -> bool:
        return 0 <= level_index <= self.unlocked_level

    def record_for(self, level_index: int) -> LevelRecord:
        return self.records.get(level_index, LevelRecord())

    def record_completion(
        self,
        level_index: int,
        stars: int,
        score: int,
        elapsed_time: float,
        total_levels: int,
    ) -> None:
        previous = self.records.get(level_index, LevelRecord())
        best_time = previous.best_time
        if best_time is None or elapsed_time < best_time:
            best_time = round(elapsed_time, 2)
        self.records[level_index] = LevelRecord(
            stars=max(previous.stars, stars),
            best_score=max(previous.best_score, score),
            best_time=best_time,
        )
        if level_index + 1 < total_levels:
            self.unlocked_level = max(self.unlocked_level, level_index + 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "unlocked_level": self.unlocked_level,
            "records": {str(index): asdict(record) for index, record in self.records.items()},
        }

    @classmethod
    def from_dict(cls, raw: object, total_levels: int) -> ProgressData:
        if not isinstance(raw, dict):
            return cls()
        unlocked = raw.get("unlocked_level", 0)
        if not isinstance(unlocked, int):
            unlocked = 0
        unlocked = min(max(0, unlocked), max(0, total_levels - 1))

        records: dict[int, LevelRecord] = {}
        raw_records = raw.get("records", {})
        if isinstance(raw_records, dict):
            for key, value in raw_records.items():
                try:
                    index = int(key)
                except (TypeError, ValueError):
                    continue
                if not 0 <= index < total_levels or not isinstance(value, dict):
                    continue
                stars = value.get("stars", 0)
                score = value.get("best_score", 0)
                best_time = value.get("best_time")
                records[index] = LevelRecord(
                    stars=min(3, max(0, stars if isinstance(stars, int) else 0)),
                    best_score=max(0, score if isinstance(score, int) else 0),
                    best_time=(
                        float(best_time)
                        if isinstance(best_time, (int, float)) and best_time >= 0
                        else None
                    ),
                )
        return cls(unlocked_level=unlocked, records=records)


class ProgressStore:
    def __init__(self, path: str | Path, total_levels: int) -> None:
        self.path = Path(path)
        self.total_levels = total_levels

    def load(self) -> ProgressData:
        if not self.path.exists():
            return ProgressData()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return ProgressData()
        return ProgressData.from_dict(raw, self.total_levels)

    def save(self, progress: ProgressData) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(progress.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)


def calculate_rating(
    max_mistakes: int,
    mistakes_left: int,
    elapsed_time: float,
    hints_used: int,
    target_seconds: float,
    auto_used: bool = False,
) -> tuple[int, int]:
    """根据失误、用时、提示次数计算星级和得分。"""

    mistakes_used = max(0, max_mistakes - mistakes_left)
    score = max(
        100,
        1500
        - int(elapsed_time) * 10
        - mistakes_used * 220
        - hints_used * 150
        - (400 if auto_used else 0),
    )
    if auto_used:
        stars = 1
    elif mistakes_used == 0 and hints_used == 0 and elapsed_time <= target_seconds:
        stars = 3
    elif mistakes_used <= 1 and hints_used <= 1 and elapsed_time <= target_seconds * 1.8:
        stars = 2
    else:
        stars = 1
    return stars, score
