"""原创关卡数据。坐标从 0 开始，格式为（行、列、方向）。"""

from __future__ import annotations

from dataclasses import dataclass

from .core import Arrow, Board, Direction


@dataclass(frozen=True, slots=True)
class Level:
    name: str
    rows: int
    cols: int
    arrows: tuple[Arrow, ...]
    mistakes: int = 3

    def create_board(self) -> Board:
        return Board(self.rows, self.cols, self.arrows, self.mistakes)


U, D, L, R = Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT


LEVELS: tuple[Level, ...] = (
    Level(
        "初识方向",
        7,
        7,
        (
            Arrow(1, 2, U),
            Arrow(3, 1, L),
            Arrow(3, 3, R),
            Arrow(3, 5, R),
            Arrow(5, 4, D),
        ),
    ),
    Level(
        "连锁反应",
        7,
        7,
        (
            Arrow(1, 3, D),
            Arrow(2, 1, L),
            Arrow(4, 3, R),
            Arrow(4, 5, U),
            Arrow(5, 1, L),
            Arrow(5, 5, D),
        ),
    ),
    Level(
        "回形迷阵",
        7,
        7,
        (
            Arrow(1, 1, R),
            Arrow(1, 3, D),
            Arrow(1, 5, U),
            Arrow(3, 1, D),
            Arrow(3, 3, L),
            Arrow(3, 5, R),
            Arrow(5, 2, L),
            Arrow(5, 4, D),
        ),
    ),
    Level(
        "十字挑战",
        7,
        7,
        (
            Arrow(0, 3, D),
            Arrow(2, 3, R),
            Arrow(3, 0, R),
            Arrow(3, 2, U),
            Arrow(3, 4, D),
            Arrow(3, 6, D),
            Arrow(4, 3, L),
            Arrow(6, 3, R),
        ),
    ),
    Level(
        "终极箭阵",
        7,
        7,
        (
            Arrow(0, 1, U),
            Arrow(0, 5, R),
            Arrow(1, 3, D),
            Arrow(2, 1, R),
            Arrow(2, 4, U),
            Arrow(3, 0, L),
            Arrow(3, 3, R),
            Arrow(3, 6, D),
            Arrow(4, 2, L),
            Arrow(5, 3, L),
            Arrow(6, 1, D),
            Arrow(6, 5, L),
        ),
        mistakes=4,
    ),
)
