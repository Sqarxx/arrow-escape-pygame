"""覆盖作业要求中的核心测试项。"""

import unittest

from arrow_game.core import Arrow, Board, ClickResult, Direction, find_solution
from arrow_game.levels import LEVELS


class BoardTests(unittest.TestCase):
    def test_t01_unblocked_arrow_exits(self) -> None:
        board = Board(5, 5, [Arrow(2, 2, Direction.RIGHT)])
        result, _ = board.click((2, 2))
        self.assertEqual(result, ClickResult.EXITED)
        self.assertTrue(board.is_cleared)

    def test_t02_blocked_arrow_costs_one_mistake(self) -> None:
        board = Board(
            5,
            5,
            [Arrow(2, 1, Direction.RIGHT), Arrow(2, 4, Direction.UP)],
        )
        result, _ = board.click((2, 1))
        self.assertEqual(result, ClickResult.BLOCKED)
        self.assertEqual(board.remaining, 2)
        self.assertEqual(board.mistakes_left, 2)

    def test_t03_edge_arrow_exits_without_overflow(self) -> None:
        cases = (
            Arrow(0, 2, Direction.UP),
            Arrow(4, 2, Direction.DOWN),
            Arrow(2, 0, Direction.LEFT),
            Arrow(2, 4, Direction.RIGHT),
        )
        for arrow in cases:
            with self.subTest(direction=arrow.direction):
                board = Board(5, 5, [arrow])
                self.assertEqual(board.click(arrow.position)[0], ClickResult.EXITED)

    def test_t04_clearing_all_arrows_marks_level_clear(self) -> None:
        board = Board(3, 3, [Arrow(1, 1, Direction.UP)])
        board.click((1, 1))
        self.assertTrue(board.is_cleared)

    def test_t05_mistakes_exhausted_marks_failure(self) -> None:
        board = Board(
            3,
            3,
            [Arrow(1, 0, Direction.RIGHT), Arrow(1, 2, Direction.UP)],
            mistakes=2,
        )
        board.click((1, 0))
        board.click((1, 0))
        self.assertTrue(board.is_failed)

    def test_t06_recreate_board_restores_layout_and_mistakes(self) -> None:
        level = LEVELS[0]
        board = level.create_board()
        original_state = board.state_key()
        board.click((1, 2))
        restarted = level.create_board()
        self.assertEqual(restarted.state_key(), original_state)
        self.assertEqual(restarted.mistakes_left, level.mistakes)

    def test_empty_cell_does_nothing(self) -> None:
        board = Board(3, 3, [Arrow(1, 1, Direction.UP)])
        result, arrow = board.click((0, 0))
        self.assertEqual(result, ClickResult.EMPTY)
        self.assertIsNone(arrow)
        self.assertEqual(board.mistakes_left, 3)

    def test_blocker_for_returns_nearest_arrow(self) -> None:
        near = Arrow(2, 2, Direction.UP)
        board = Board(
            5,
            5,
            [Arrow(2, 0, Direction.RIGHT), near, Arrow(2, 4, Direction.DOWN)],
        )
        self.assertEqual(board.blocker_for((2, 0)), near)


class LevelTests(unittest.TestCase):
    def test_at_least_three_levels(self) -> None:
        self.assertGreaterEqual(len(LEVELS), 3)

    def test_every_level_contains_all_four_directions(self) -> None:
        expected = set(Direction)
        for level in LEVELS:
            with self.subTest(level=level.name):
                self.assertEqual({arrow.direction for arrow in level.arrows}, expected)

    def test_every_level_has_a_solution(self) -> None:
        for level in LEVELS:
            with self.subTest(level=level.name):
                solution = find_solution(level.create_board())
                self.assertIsNotNone(solution)
                self.assertEqual(len(solution or []), len(level.arrows))


if __name__ == "__main__":
    unittest.main()
