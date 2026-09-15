"""与图形界面无关的棋盘规则和自动求解逻辑。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Iterable


class Direction(Enum):
    """箭头方向，以及对应的行、列增量。"""

    UP = (-1, 0)
    DOWN = (1, 0)
    LEFT = (0, -1)
    RIGHT = (0, 1)

    @property
    def delta(self) -> tuple[int, int]:
        return self.value


@dataclass(frozen=True, slots=True)
class Arrow:
    row: int
    col: int
    direction: Direction

    @property
    def position(self) -> tuple[int, int]:
        return self.row, self.col


class ClickResult(Enum):
    EMPTY = "empty"
    EXITED = "exited"
    BLOCKED = "blocked"


class Board:
    """保存当前关卡状态，并实现点击和路径检测。"""

    def __init__(
        self,
        rows: int,
        cols: int,
        arrows: Iterable[Arrow],
        mistakes: int = 3,
    ) -> None:
        if rows <= 0 or cols <= 0:
            raise ValueError("棋盘行列数必须为正数")
        if mistakes <= 0:
            raise ValueError("失误次数必须为正数")

        self.rows = rows
        self.cols = cols
        self.max_mistakes = mistakes
        self.mistakes_left = mistakes
        self.arrows: dict[tuple[int, int], Arrow] = {}

        for arrow in arrows:
            if not self.in_bounds(arrow.row, arrow.col):
                raise ValueError(f"箭头坐标越界：{arrow.position}")
            if arrow.position in self.arrows:
                raise ValueError(f"箭头坐标重复：{arrow.position}")
            self.arrows[arrow.position] = arrow

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols

    @property
    def remaining(self) -> int:
        return len(self.arrows)

    @property
    def is_cleared(self) -> bool:
        return not self.arrows

    @property
    def is_failed(self) -> bool:
        return self.mistakes_left <= 0

    def blocker_for(self, position: tuple[int, int]) -> Arrow | None:
        """返回箭头飞行方向上的第一个阻挡箭头；无阻挡时返回 None。"""

        arrow = self.arrows.get(position)
        if arrow is None:
            return None

        dr, dc = arrow.direction.delta
        row, col = arrow.row + dr, arrow.col + dc
        while self.in_bounds(row, col):
            blocker = self.arrows.get((row, col))
            if blocker is not None:
                return blocker
            row += dr
            col += dc
        return None

    def can_exit(self, position: tuple[int, int]) -> bool:
        return position in self.arrows and self.blocker_for(position) is None

    def click(self, position: tuple[int, int]) -> tuple[ClickResult, Arrow | None]:
        """点击一个格子，返回结果和被点击的箭头。"""

        arrow = self.arrows.get(position)
        if arrow is None:
            return ClickResult.EMPTY, None

        if self.can_exit(position):
            del self.arrows[position]
            return ClickResult.EXITED, arrow

        self.mistakes_left = max(0, self.mistakes_left - 1)
        return ClickResult.BLOCKED, arrow

    def copy(self) -> Board:
        copied = Board(self.rows, self.cols, self.arrows.values(), self.max_mistakes)
        copied.mistakes_left = self.mistakes_left
        return copied

    def state_key(self) -> tuple[tuple[int, int, str], ...]:
        return tuple(
            sorted((a.row, a.col, a.direction.name) for a in self.arrows.values())
        )


def find_solution(board: Board) -> list[tuple[int, int]] | None:
    """使用深度优先搜索寻找从当前状态开始的无失误通关顺序。"""

    directions = {direction.name: direction for direction in Direction}

    @lru_cache(maxsize=None)
    def search(
        state: tuple[tuple[int, int, str], ...],
    ) -> tuple[tuple[int, int], ...] | None:
        if not state:
            return ()

        arrows = [Arrow(row, col, directions[name]) for row, col, name in state]
        current = Board(board.rows, board.cols, arrows)
        for position in sorted(current.arrows):
            if not current.can_exit(position):
                continue
            next_state = tuple(item for item in state if item[:2] != position)
            rest = search(next_state)
            if rest is not None:
                return (position,) + rest
        return None

    result = search(board.state_key())
    return list(result) if result is not None else None
