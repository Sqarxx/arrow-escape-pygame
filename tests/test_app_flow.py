"""使用 SDL 虚拟显示器测试完整的界面状态流。"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from arrow_game.app import GameApp, make_font  # noqa: E402
from arrow_game.core import find_solution  # noqa: E402


class AppFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = GameApp(headless=True)

    def tearDown(self) -> None:
        pygame.quit()

    def test_solution_reaches_level_clear_screen(self) -> None:
        self.app.start_level(0)
        solution = find_solution(self.app.board)
        self.assertIsNotNone(solution)
        for position in solution or []:
            self.app.click_arrow(position)
            self.app.update(0.6)
        self.assertEqual(self.app.state, "level_clear")

    def test_three_blocked_clicks_reach_failure_screen(self) -> None:
        self.app.start_level(0)
        blocked_position = (3, 3)
        for _ in range(3):
            self.app.click_arrow(blocked_position)
            self.app.update(0.6)
        self.assertEqual(self.app.state, "failed")

    def test_restart_restores_initial_state(self) -> None:
        self.app.start_level(0)
        initial = self.app.board.state_key()
        self.app.click_arrow((1, 2))
        self.app.update(0.6)
        self.app.restart_level()
        self.assertEqual(self.app.board.state_key(), initial)
        self.assertEqual(self.app.board.mistakes_left, self.app.level.mistakes)

    def test_all_screens_can_be_drawn(self) -> None:
        for state in ("start", "playing", "level_clear", "failed", "complete"):
            with self.subTest(state=state):
                self.app.state = state
                self.app.draw()

    def test_font_loader_returns_a_usable_font(self) -> None:
        font = make_font(24, bold=True)
        rendered = font.render("一箭又一箭", True, (255, 255, 255))
        self.assertGreater(rendered.get_width(), 0)
        self.assertGreater(rendered.get_height(), 0)


if __name__ == "__main__":
    unittest.main()
