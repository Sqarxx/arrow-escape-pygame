"""Pygame 图形界面、交互和动画。"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path

import pygame

from .core import Arrow, Board, ClickResult, Direction, find_solution
from .levels import LEVELS
from .progress import ProgressData, ProgressStore, calculate_rating


WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 760
FPS = 60
BOARD_LEFT = 248
BOARD_TOP = 150
CELL_SIZE = 72

BG_TOP = (249, 252, 251)
BG_BOTTOM = (229, 245, 241)
PANEL = (255, 255, 255)
BOARD_BG = (222, 241, 237)
GRID = (190, 221, 215)
INK = (31, 65, 61)
MUTED = (93, 121, 117)
BLUE = (30, 164, 147)
BLUE_DARK = (20, 136, 123)
CYAN = (82, 194, 178)
ORANGE = (238, 168, 96)
RED = (225, 111, 119)
WHITE = (255, 255, 255)
SOFT_TEAL = (234, 248, 245)
SOFT_RED = (255, 235, 237)
SHADOW = (180, 205, 200)
ARROW_COLORS = (
    (30, 164, 147),
    (225, 111, 119),
    (91, 153, 219),
    (239, 168, 96),
    (151, 126, 205),
    (105, 183, 116),
)
LEVEL_TIME_TARGETS = (25, 32, 40, 48, 60)


def make_font(size: int, bold: bool = False) -> pygame.font.Font:
    """优先选择包含中文字符的系统字体。

    某些 Windows + Python 3.13 环境下，Pygame 的 ``SysFont`` 无法正确
    处理字体名称列表，因此这里逐个查找字体文件，再交给 ``Font`` 加载。
    """

    candidates = [
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
    ]

    # Windows 常见中文字体直接按文件加载，可绕开部分环境中损坏的
    # Pygame 系统字体索引（用户截图中的 splitext TypeError 即来自该索引）。
    if os.name == "nt":
        font_directory = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        filenames = (
            ["msyhbd.ttc", "msyh.ttc", "simhei.ttf"]
            if bold
            else ["msyh.ttc", "msyhbd.ttc", "simhei.ttf"]
        )
        for filename in filenames:
            font_path = font_directory / filename
            if font_path.is_file():
                try:
                    return pygame.font.Font(str(font_path), size)
                except (OSError, pygame.error):
                    continue

    for candidate in candidates:
        try:
            font_path = pygame.font.match_font(candidate, bold=bold)
        except (OSError, TypeError, ValueError):
            # 系统字体表中存在异常条目时继续尝试下一个候选字体。
            continue
        if font_path:
            return pygame.font.Font(font_path, size)

    # 极少数系统没有上述中文字体时，仍保证程序可以启动。
    return pygame.font.Font(None, size)


def draw_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    position: tuple[int, int],
    anchor: str = "topleft",
) -> pygame.Rect:
    image = font.render(text, True, color)
    rect = image.get_rect()
    setattr(rect, anchor, position)
    surface.blit(image, rect)
    return rect


@dataclass(slots=True)
class Button:
    rect: pygame.Rect
    text: str
    primary: bool = True

    def draw(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        mouse_position: tuple[int, int],
    ) -> None:
        hovered = self.rect.collidepoint(mouse_position)
        if self.primary:
            color = BLUE_DARK if hovered else BLUE
            text_color = WHITE
            border_color = color
        else:
            color = SOFT_TEAL if hovered else WHITE
            text_color = INK
            border_color = GRID
        shadow = self.rect.move(0, 4)
        pygame.draw.rect(surface, SHADOW, shadow, border_radius=14)
        pygame.draw.rect(surface, color, self.rect, border_radius=14)
        pygame.draw.rect(surface, border_color, self.rect, 2, border_radius=14)
        draw_text(surface, self.text, font, text_color, self.rect.center, "center")

    def hit(self, position: tuple[int, int]) -> bool:
        return self.rect.collidepoint(position)


@dataclass(slots=True)
class FlyingAnimation:
    arrow: Arrow
    start: pygame.Vector2
    end: pygame.Vector2
    elapsed: float = 0.0
    duration: float = 0.52

    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed / self.duration)

    @property
    def done(self) -> bool:
        return self.elapsed >= self.duration


@dataclass(slots=True)
class CollisionAnimation:
    position: tuple[int, int]
    blocker: tuple[int, int]
    elapsed: float = 0.0
    duration: float = 0.58

    @property
    def done(self) -> bool:
        return self.elapsed >= self.duration


@dataclass(slots=True)
class GameSnapshot:
    board: Board
    level_clicks: int
    hints_used: int
    elapsed_time: float


class GameApp:
    """小游戏应用。游戏状态只在此处负责切换，规则由 Board 负责。"""

    def __init__(
        self,
        headless: bool = False,
        save_path: str | Path | None = None,
    ) -> None:
        pygame.init()
        pygame.display.set_caption("一箭又一箭 · Arrow Escape")
        flags = pygame.HIDDEN if headless else 0
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), flags)
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "start"
        if save_path is None and not headless:
            save_path = Path(__file__).resolve().parent.parent / "save_data.json"
        self.progress_store = (
            ProgressStore(save_path, len(LEVELS)) if save_path is not None else None
        )
        self.progress = (
            self.progress_store.load() if self.progress_store else ProgressData()
        )
        self.level_index = 0
        self.board = LEVELS[0].create_board()
        self.elapsed_time = 0.0
        self.level_clicks = 0
        self.hints_used = 0
        self.auto_used = False
        self.history: list[GameSnapshot] = []
        self.auto_solving = False
        self.auto_queue: list[tuple[int, int]] = []
        self.auto_delay = 0.0
        self.completion_recorded = False
        self.result_stars = 0
        self.result_score = 0
        self.flying: list[FlyingAnimation] = []
        self.collision: CollisionAnimation | None = None
        self.hint_position: tuple[int, int] | None = None
        self.hint_time = 0.0
        self.toast = ""
        self.toast_time = 0.0

        self.font_xl = make_font(58, True)
        self.font_lg = make_font(34, True)
        self.font_md = make_font(24, True)
        self.font_body = make_font(20)
        self.font_small = make_font(16)

        self.start_button = Button(pygame.Rect(365, 525, 270, 58), "开始游戏")
        self.select_button = Button(pygame.Rect(385, 596, 230, 48), "关卡选择", False)
        self.restart_button = Button(pygame.Rect(118, 694, 140, 44), "重新开始", False)
        self.undo_button = Button(pygame.Rect(274, 694, 140, 44), "撤销一步", False)
        self.hint_button = Button(pygame.Rect(430, 694, 140, 44), "提示一步", False)
        self.auto_button = Button(pygame.Rect(586, 694, 140, 44), "AI 解题", False)
        self.home_button = Button(pygame.Rect(742, 694, 140, 44), "返回首页", False)
        self.select_home_button = Button(pygame.Rect(375, 642, 250, 50), "返回首页", False)
        self.result_primary = Button(pygame.Rect(362, 510, 276, 56), "下一关")
        self.result_secondary = Button(pygame.Rect(362, 580, 276, 50), "重玩本关", False)

    @property
    def level(self):  # 类型由 LEVELS 决定，避免界面层重复导入注解。
        return LEVELS[self.level_index]

    @property
    def board_rect(self) -> pygame.Rect:
        return pygame.Rect(
            BOARD_LEFT,
            BOARD_TOP,
            self.board.cols * CELL_SIZE,
            self.board.rows * CELL_SIZE,
        )

    def level_card_rect(self, index: int) -> pygame.Rect:
        row, col = divmod(index, 3)
        count_in_row = min(3, len(LEVELS) - row * 3)
        width, height, gap = 220, 176, 28
        row_width = count_in_row * width + (count_in_row - 1) * gap
        start_x = (WINDOW_WIDTH - row_width) // 2
        return pygame.Rect(start_x + col * (width + gap), 174 + row * 216, width, height)

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    def start_level(self, index: int) -> None:
        if not 0 <= index < len(LEVELS):
            raise IndexError("关卡编号越界")
        self.level_index = index
        self.board = LEVELS[index].create_board()
        self.state = "playing"
        self.elapsed_time = 0.0
        self.level_clicks = 0
        self.hints_used = 0
        self.auto_used = False
        self.history.clear()
        self.auto_solving = False
        self.auto_queue.clear()
        self.auto_delay = 0.0
        self.completion_recorded = False
        self.result_stars = 0
        self.result_score = 0
        self.flying.clear()
        self.collision = None
        self.hint_position = None
        self.hint_time = 0.0
        self.toast = ""
        self.toast_time = 0.0

    def restart_level(self) -> None:
        self.start_level(self.level_index)

    def save_progress(self) -> None:
        if self.progress_store is None:
            return
        try:
            self.progress_store.save(self.progress)
        except OSError:
            self.toast = "存档写入失败，本局仍可继续"
            self.toast_time = 2.0

    def current_snapshot(self) -> GameSnapshot:
        return GameSnapshot(
            self.board.copy(),
            self.level_clicks,
            self.hints_used,
            self.elapsed_time,
        )

    def stop_auto_solve(self, show_message: bool = False) -> None:
        was_running = self.auto_solving
        self.auto_solving = False
        self.auto_queue.clear()
        if was_running and show_message:
            self.toast = "已停止 AI 自动解题"
            self.toast_time = 1.2

    def undo_move(self) -> None:
        self.stop_auto_solve()
        if not self.history:
            self.toast = "还没有可以撤销的操作"
            self.toast_time = 1.2
            return
        snapshot = self.history.pop()
        self.board = snapshot.board
        self.level_clicks = snapshot.level_clicks
        self.hints_used = snapshot.hints_used
        self.elapsed_time = snapshot.elapsed_time
        self.flying.clear()
        self.collision = None
        self.hint_position = None
        self.toast = "已撤销上一步"
        self.toast_time = 1.2

    def start_auto_solve(self) -> None:
        if self.auto_solving:
            self.stop_auto_solve(show_message=True)
            return
        if self.flying or self.collision is not None:
            return
        solution = find_solution(self.board)
        if not solution:
            self.toast = "当前状态没有可用的自动解法"
            self.toast_time = 1.5
            return
        self.auto_solving = True
        self.auto_used = True
        self.auto_queue = solution
        self.auto_delay = 0.45
        self.toast = "AI 正在按求解序列演示"
        self.toast_time = 1.5

    def finish_level(self) -> None:
        if self.completion_recorded:
            return
        target = LEVEL_TIME_TARGETS[min(self.level_index, len(LEVEL_TIME_TARGETS) - 1)]
        self.result_stars, self.result_score = calculate_rating(
            self.board.max_mistakes,
            self.board.mistakes_left,
            self.elapsed_time,
            self.hints_used,
            target,
            self.auto_used,
        )
        self.progress.record_completion(
            self.level_index,
            self.result_stars,
            self.result_score,
            self.elapsed_time,
            len(LEVELS),
        )
        self.save_progress()
        self.completion_recorded = True
        self.auto_solving = False

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.handle_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_click(event.pos)

    def handle_key(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            if self.state == "start":
                self.running = False
            else:
                self.stop_auto_solve()
                self.state = "start"
        elif self.state == "start" and key in (pygame.K_RETURN, pygame.K_SPACE):
            self.start_level(self.progress.unlocked_level)
        elif self.state == "playing":
            if key == pygame.K_r:
                self.restart_level()
            elif key == pygame.K_h:
                self.show_hint()
            elif key == pygame.K_u:
                self.undo_move()
            elif key == pygame.K_a:
                self.start_auto_solve()
        elif self.state == "level_clear" and key in (pygame.K_RETURN, pygame.K_SPACE):
            self.go_to_next_level()
        elif self.state == "failed" and key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
            self.restart_level()
        elif self.state == "complete" and key in (pygame.K_RETURN, pygame.K_SPACE):
            self.start_level(0)

    def handle_click(self, position: tuple[int, int]) -> None:
        if self.state == "start":
            if self.start_button.hit(position):
                self.start_level(self.progress.unlocked_level)
            elif self.select_button.hit(position):
                self.state = "level_select"
            return

        if self.state == "level_select":
            if self.select_home_button.hit(position):
                self.state = "start"
                return
            for index in range(len(LEVELS)):
                if self.level_card_rect(index).collidepoint(position):
                    if self.progress.is_unlocked(index):
                        self.start_level(index)
                    return
            return

        if self.state == "playing":
            if self.restart_button.hit(position):
                self.restart_level()
            elif self.undo_button.hit(position):
                self.undo_move()
            elif self.hint_button.hit(position):
                self.stop_auto_solve()
                self.show_hint()
            elif self.auto_button.hit(position):
                self.start_auto_solve()
            elif self.home_button.hit(position):
                self.stop_auto_solve()
                self.state = "start"
            elif not self.flying and self.collision is None:
                cell = self.pixel_to_cell(position)
                if cell is not None:
                    self.stop_auto_solve()
                    self.click_arrow(cell)
            return

        if self.state == "level_clear":
            if self.result_primary.hit(position):
                self.go_to_next_level()
            elif self.result_secondary.hit(position):
                self.restart_level()
        elif self.state == "failed":
            if self.result_primary.hit(position):
                self.restart_level()
            elif self.result_secondary.hit(position):
                self.state = "start"
        elif self.state == "complete":
            if self.result_primary.hit(position):
                self.start_level(0)
            elif self.result_secondary.hit(position):
                self.state = "start"

    def pixel_to_cell(self, position: tuple[int, int]) -> tuple[int, int] | None:
        if not self.board_rect.collidepoint(position):
            return None
        col = (position[0] - BOARD_LEFT) // CELL_SIZE
        row = (position[1] - BOARD_TOP) // CELL_SIZE
        return int(row), int(col)

    def cell_center(self, position: tuple[int, int]) -> pygame.Vector2:
        row, col = position
        return pygame.Vector2(
            BOARD_LEFT + col * CELL_SIZE + CELL_SIZE / 2,
            BOARD_TOP + row * CELL_SIZE + CELL_SIZE / 2,
        )

    def click_arrow(self, position: tuple[int, int]) -> None:
        if position not in self.board.arrows:
            return
        self.history.append(self.current_snapshot())
        blocker = self.board.blocker_for(position)
        result, arrow = self.board.click(position)
        if result is ClickResult.EMPTY or arrow is None:
            return

        self.level_clicks += 1
        self.hint_position = None
        if result is ClickResult.EXITED:
            start = self.cell_center(arrow.position)
            dr, dc = arrow.direction.delta
            distance = max(WINDOW_WIDTH, WINDOW_HEIGHT)
            end = start + pygame.Vector2(dc * distance, dr * distance)
            self.flying.append(FlyingAnimation(arrow, start, end))
            self.toast = "路径畅通！"
            self.toast_time = 0.9
        elif blocker is not None:
            self.collision = CollisionAnimation(position, blocker.position)
            self.toast = f"前方有阻挡，剩余 {self.board.mistakes_left} 次机会"
            self.toast_time = 1.2

    def show_hint(self) -> None:
        if self.flying or self.collision is not None:
            return
        solution = find_solution(self.board)
        if solution:
            self.hints_used += 1
            self.hint_position = solution[0]
            self.hint_time = 2.0
            self.toast = "蓝色光圈标出了可安全飞出的箭头"
            self.toast_time = 2.0

    def go_to_next_level(self) -> None:
        if self.level_index + 1 < len(LEVELS):
            self.start_level(self.level_index + 1)
        else:
            self.state = "complete"

    def update(self, dt: float) -> None:
        if self.state == "playing":
            self.elapsed_time += dt

        for animation in self.flying:
            animation.elapsed += dt
        self.flying = [animation for animation in self.flying if not animation.done]

        if self.collision is not None:
            self.collision.elapsed += dt
            if self.collision.done:
                self.collision = None

        self.hint_time = max(0.0, self.hint_time - dt)
        if self.hint_time == 0:
            self.hint_position = None
        self.toast_time = max(0.0, self.toast_time - dt)

        if (
            self.state == "playing"
            and self.auto_solving
            and not self.flying
            and self.collision is None
            and not self.board.is_cleared
        ):
            self.auto_delay -= dt
            if self.auto_delay <= 0 and self.auto_queue:
                next_position = self.auto_queue.pop(0)
                if next_position in self.board.arrows:
                    self.click_arrow(next_position)
                self.auto_delay = 0.22

        if self.state == "playing" and not self.flying and self.collision is None:
            if self.board.is_failed:
                self.auto_solving = False
                self.state = "failed"
            elif self.board.is_cleared:
                self.finish_level()
                self.state = "level_clear"

    def draw(self) -> None:
        self.draw_background()
        if self.state == "start":
            self.draw_start_screen()
        elif self.state == "level_select":
            self.draw_level_select_screen()
        elif self.state == "playing":
            self.draw_game_screen()
        elif self.state == "level_clear":
            self.draw_result_screen(True)
        elif self.state == "failed":
            self.draw_result_screen(False)
        elif self.state == "complete":
            self.draw_complete_screen()

    def draw_background(self) -> None:
        for y in range(WINDOW_HEIGHT):
            ratio = y / WINDOW_HEIGHT
            color = tuple(
                int(BG_TOP[i] * (1 - ratio) + BG_BOTTOM[i] * ratio) for i in range(3)
            )
            pygame.draw.line(self.screen, color, (0, y), (WINDOW_WIDTH, y))
        for x, y, radius, alpha in (
            (80, 60, 145, 42),
            (920, 100, 175, 34),
            (850, 720, 220, 28),
        ):
            glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*CYAN, alpha), (radius, radius), radius, 2)
            self.screen.blit(glow, (x - radius, y - radius))

    def draw_start_screen(self) -> None:
        mouse = pygame.mouse.get_pos()
        self.draw_arrow_pattern()
        self.draw_outlined_text(
            "一箭又一箭",
            self.font_xl,
            ORANGE,
            INK,
            (500, 108),
            2,
        )
        draw_text(
            self.screen,
            "ARROW  ESCAPE",
            self.font_small,
            BLUE,
            (500, 160),
            "center",
        )
        draw_text(
            self.screen,
            "看方向 · 找顺序 · 让箭头全部出发",
            self.font_body,
            MUTED,
            (500, 200),
            "center",
        )
        self.draw_mascot((500, 345))
        self.start_button.text = (
            "继续游戏" if self.progress.unlocked_level > 0 else "开始游戏"
        )
        draw_text(
            self.screen,
            f"第 {self.progress.unlocked_level + 1} 关",
            self.font_md,
            INK,
            (500, 480),
            "center",
        )
        self.start_button.draw(self.screen, self.font_md, mouse)
        self.draw_play_triangle((401, 554))
        self.select_button.draw(self.screen, self.font_body, mouse)
        total_stars = sum(record.stars for record in self.progress.records.values())
        draw_text(
            self.screen,
            f"已解锁 {self.progress.unlocked_level + 1}/{len(LEVELS)} 关  ·  累计 {total_stars} 星",
            self.font_small,
            MUTED,
            (500, 671),
            "center",
        )
        draw_text(
            self.screen,
            "R 重开  H 提示  U 撤销  A 自动解题",
            self.font_small,
            MUTED,
            (500, 709),
            "center",
        )

    def draw_level_select_screen(self) -> None:
        mouse = pygame.mouse.get_pos()
        self.draw_arrow_pattern()
        draw_text(self.screen, "选择关卡", self.font_xl, INK, (500, 72), "center")
        draw_text(
            self.screen,
            "完成当前关卡后自动解锁下一关，最佳成绩会自动保存",
            self.font_body,
            MUTED,
            (500, 126),
            "center",
        )
        for index, level in enumerate(LEVELS):
            rect = self.level_card_rect(index)
            unlocked = self.progress.is_unlocked(index)
            hovered = unlocked and rect.collidepoint(mouse)
            color = WHITE if unlocked else (239, 245, 243)
            if hovered:
                color = SOFT_TEAL
            pygame.draw.rect(self.screen, SHADOW, rect.move(0, 4), border_radius=20)
            pygame.draw.rect(self.screen, color, rect, border_radius=20)
            border = BLUE if hovered else (GRID if unlocked else (207, 220, 216))
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=20)

            if unlocked:
                record = self.progress.record_for(index)
                draw_text(
                    self.screen,
                    f"第 {index + 1} 关",
                    self.font_small,
                    BLUE,
                    (rect.centerx, rect.y + 23),
                    "center",
                )
                draw_text(
                    self.screen,
                    level.name,
                    self.font_md,
                    INK,
                    (rect.centerx, rect.y + 58),
                    "center",
                )
                self.draw_stars((rect.centerx, rect.y + 105), record.stars, 14)
                score_text = (
                    f"最佳 {record.best_score} 分"
                    if record.best_score
                    else "尚未通关"
                )
                draw_text(
                    self.screen,
                    score_text,
                    self.font_small,
                    MUTED,
                    (rect.centerx, rect.y + 144),
                    "center",
                )
            else:
                draw_text(
                    self.screen,
                    "未解锁",
                    self.font_md,
                    (148, 166, 162),
                    rect.center,
                    "center",
                )
        self.select_home_button.draw(self.screen, self.font_body, mouse)

    def draw_stars(
        self,
        center: tuple[int, int],
        filled: int,
        radius: int = 18,
    ) -> None:
        gap = radius * 2 + 10
        start_x = center[0] - gap
        for index in range(3):
            points: list[tuple[float, float]] = []
            star_center = (start_x + index * gap, center[1])
            for point_index in range(10):
                angle = -math.pi / 2 + point_index * math.pi / 5
                point_radius = radius if point_index % 2 == 0 else radius * 0.45
                points.append(
                    (
                        star_center[0] + math.cos(angle) * point_radius,
                        star_center[1] + math.sin(angle) * point_radius,
                    )
                )
            color = ORANGE if index < filled else (188, 207, 203)
            if index < filled:
                pygame.draw.polygon(self.screen, color, points)
            else:
                pygame.draw.polygon(self.screen, color, points, 2)

    def draw_outlined_text(
        self,
        text: str,
        font: pygame.font.Font,
        fill: tuple[int, int, int],
        outline: tuple[int, int, int],
        center: tuple[int, int],
        width: int,
    ) -> None:
        for dx in range(-width, width + 1):
            for dy in range(-width, width + 1):
                if dx * dx + dy * dy <= width * width:
                    draw_text(
                        self.screen,
                        text,
                        font,
                        outline,
                        (center[0] + dx, center[1] + dy),
                        "center",
                    )
        draw_text(self.screen, text, font, fill, center, "center")

    def draw_arrow_pattern(self) -> None:
        pattern = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        directions = (Direction.DOWN, Direction.UP, Direction.LEFT, Direction.RIGHT)
        for row, y in enumerate(range(30, WINDOW_HEIGHT, 86)):
            offset = 42 if row % 2 else 0
            for col, x in enumerate(range(-20 + offset, WINDOW_WIDTH + 40, 112)):
                arrow = Arrow(0, 0, directions[(row + col) % len(directions)])
                self.draw_arrow_icon(
                    pattern,
                    arrow,
                    (x, y),
                    34,
                    BLUE,
                    22,
                )
        self.screen.blit(pattern, (0, 0))

    def draw_mascot(self, center: tuple[int, int]) -> None:
        cx, cy = center
        points = [
            (cx - 100, cy - 47),
            (cx + 34, cy - 47),
            (cx + 34, cy - 78),
            (cx + 112, cy),
            (cx + 34, cy + 78),
            (cx + 34, cy + 47),
            (cx - 100, cy + 47),
        ]
        shadow_points = [(x, y + 8) for x, y in points]
        pygame.draw.polygon(self.screen, SHADOW, shadow_points)
        pygame.draw.polygon(self.screen, CYAN, points)
        pygame.draw.polygon(self.screen, INK, points, 6)
        pygame.draw.line(
            self.screen,
            (174, 235, 226),
            (cx - 79, cy - 27),
            (cx + 25, cy - 27),
            7,
        )
        for eye_x in (cx - 52, cx - 5):
            pygame.draw.circle(self.screen, WHITE, (eye_x, cy - 2), 23)
            pygame.draw.circle(self.screen, INK, (eye_x + 4, cy + 1), 10)
            pygame.draw.circle(self.screen, WHITE, (eye_x + 7, cy - 3), 3)
        pygame.draw.line(
            self.screen,
            INK,
            (cx - 74, cy - 33),
            (cx - 43, cy - 26),
            6,
        )
        pygame.draw.line(
            self.screen,
            INK,
            (cx - 17, cy - 26),
            (cx + 12, cy - 34),
            6,
        )
        pygame.draw.arc(
            self.screen,
            INK,
            pygame.Rect(cx - 48, cy + 8, 58, 35),
            math.radians(15),
            math.radians(165),
            4,
        )
        pygame.draw.circle(self.screen, (243, 152, 157), (cx - 81, cy + 21), 8)
        pygame.draw.circle(self.screen, (243, 152, 157), (cx + 23, cy + 21), 8)

    def draw_play_triangle(self, center: tuple[int, int]) -> None:
        cx, cy = center
        pygame.draw.polygon(
            self.screen,
            WHITE,
            ((cx - 8, cy - 11), (cx - 8, cy + 11), (cx + 12, cy)),
        )

    def draw_game_screen(self) -> None:
        mouse = pygame.mouse.get_pos()
        self.draw_top_hud()
        self.draw_board(mouse)
        self.draw_flying_animations()
        self.draw_bottom_toolbar(mouse)

        if self.toast_time > 0:
            toast_width = min(520, max(270, len(self.toast) * 22 + 48))
            toast = pygame.Rect((WINDOW_WIDTH - toast_width) // 2, 651, toast_width, 36)
            warning = "阻挡" in self.toast or "失败" in self.toast or "没有" in self.toast
            toast_color = SOFT_RED if warning else SOFT_TEAL
            text_color = RED if warning else INK
            border_color = RED if warning else CYAN
            pygame.draw.rect(self.screen, toast_color, toast, border_radius=19)
            pygame.draw.rect(self.screen, border_color, toast, 1, border_radius=19)
            draw_text(self.screen, self.toast, self.font_small, text_color, toast.center, "center")

    def draw_top_hud(self) -> None:
        left = pygame.Rect(48, 26, 250, 100)
        center = pygame.Rect(365, 18, 270, 116)
        right = pygame.Rect(702, 26, 250, 100)
        for rect in (left, center, right):
            pygame.draw.rect(self.screen, SHADOW, rect.move(0, 3), border_radius=18)
            pygame.draw.rect(self.screen, WHITE, rect, border_radius=18)
            pygame.draw.rect(self.screen, GRID, rect, 1, border_radius=18)

        draw_text(
            self.screen,
            f"第 {self.level_index + 1} 关",
            self.font_md,
            BLUE,
            (left.centerx, left.y + 31),
            "center",
        )
        draw_text(
            self.screen,
            self.level.name,
            self.font_small,
            MUTED,
            (left.centerx, left.y + 70),
            "center",
        )

        heart_gap = 38
        heart_start = center.centerx - (self.board.max_mistakes - 1) * heart_gap / 2
        for index in range(self.board.max_mistakes):
            color = RED if index < self.board.mistakes_left else (207, 219, 216)
            self.draw_heart((int(heart_start + index * heart_gap), center.y + 38), 13, color)
        minutes, seconds = divmod(int(self.elapsed_time), 60)
        pygame.draw.circle(self.screen, BLUE, (center.centerx - 42, center.y + 85), 12, 2)
        pygame.draw.line(
            self.screen,
            BLUE,
            (center.centerx - 42, center.y + 85),
            (center.centerx - 42, center.y + 77),
            2,
        )
        pygame.draw.line(
            self.screen,
            BLUE,
            (center.centerx - 42, center.y + 85),
            (center.centerx - 35, center.y + 88),
            2,
        )
        draw_text(
            self.screen,
            f"{minutes:02d}:{seconds:02d}",
            self.font_md,
            INK,
            (center.centerx + 22, center.y + 85),
            "center",
        )

        draw_text(
            self.screen,
            "剩余箭头",
            self.font_small,
            MUTED,
            (right.centerx, right.y + 28),
            "center",
        )
        draw_text(
            self.screen,
            str(self.board.remaining),
            self.font_lg,
            BLUE,
            (right.centerx, right.y + 67),
            "center",
        )

    def draw_heart(
        self,
        center: tuple[int, int],
        size: int,
        color: tuple[int, int, int],
    ) -> None:
        cx, cy = center
        pygame.draw.circle(self.screen, color, (cx - size // 2, cy - size // 3), size // 2)
        pygame.draw.circle(self.screen, color, (cx + size // 2, cy - size // 3), size // 2)
        pygame.draw.polygon(
            self.screen,
            color,
            ((cx - size, cy - size // 4), (cx + size, cy - size // 4), (cx, cy + size)),
        )

    def draw_bottom_toolbar(self, mouse: tuple[int, int]) -> None:
        pygame.draw.line(self.screen, GRID, (72, 680), (928, 680), 1)
        self.auto_button.text = "停止 AI" if self.auto_solving else "AI 解题"
        self.restart_button.draw(self.screen, self.font_small, mouse)
        self.undo_button.draw(self.screen, self.font_small, mouse)
        self.hint_button.draw(self.screen, self.font_small, mouse)
        self.auto_button.draw(self.screen, self.font_small, mouse)
        self.home_button.draw(self.screen, self.font_small, mouse)

    def draw_board(self, mouse: tuple[int, int]) -> None:
        rect = self.board_rect
        shadow = rect.inflate(16, 16).move(0, 7)
        pygame.draw.rect(self.screen, SHADOW, shadow, border_radius=22)
        pygame.draw.rect(self.screen, BOARD_BG, rect.inflate(16, 16), border_radius=22)

        for row in range(self.board.rows):
            for col in range(self.board.cols):
                cell = pygame.Rect(
                    BOARD_LEFT + col * CELL_SIZE,
                    BOARD_TOP + row * CELL_SIZE,
                    CELL_SIZE,
                    CELL_SIZE,
                )
                color = WHITE if (row + col) % 2 == 0 else (240, 249, 247)
                pygame.draw.rect(self.screen, color, cell)
                pygame.draw.rect(self.screen, GRID, cell, 1)

        hover_cell = self.pixel_to_cell(mouse)
        for position, arrow in self.board.arrows.items():
            center = self.cell_center(position)
            color = self.arrow_color(arrow)
            scale = 47
            if position == hover_cell and self.collision is None:
                color = tuple(max(0, channel - 24) for channel in color)
                scale = 53
            if self.hint_position == position:
                pulse = 31 + int(math.sin(pygame.time.get_ticks() / 140) * 4)
                pygame.draw.circle(self.screen, CYAN, center, pulse, 4)

            offset_x = 0
            if self.collision is not None and self.collision.position == position:
                phase = self.collision.elapsed / self.collision.duration
                offset_x = int(math.sin(phase * math.pi * 8) * (1 - phase) * 13)
                color = RED
            if self.collision is not None and self.collision.blocker == position:
                pygame.draw.circle(self.screen, ORANGE, center, 33, 4)
            self.draw_arrow_icon(
                self.screen,
                arrow,
                (int(center.x + offset_x), int(center.y)),
                scale,
                color,
            )

        if self.collision is not None:
            start = self.cell_center(self.collision.position)
            end = self.cell_center(self.collision.blocker)
            pygame.draw.line(self.screen, (*RED,), start, end, 3)

    def arrow_color(self, arrow: Arrow) -> tuple[int, int, int]:
        index = (arrow.row * 3 + arrow.col * 5 + arrow.direction.value[0]) % len(
            ARROW_COLORS
        )
        return ARROW_COLORS[index]

    def draw_arrow_icon(
        self,
        surface: pygame.Surface,
        arrow: Arrow,
        center: tuple[int, int] | pygame.Vector2,
        size: int,
        color: tuple[int, int, int],
        alpha: int = 255,
    ) -> None:
        icon = pygame.Surface((80, 80), pygame.SRCALPHA)
        points = [(40, 7), (65, 33), (52, 33), (52, 68), (28, 68), (28, 33), (15, 33)]
        pygame.draw.polygon(icon, (*color, alpha), points)
        pygame.draw.polygon(icon, (255, 255, 255, min(alpha, 90)), points, 2)
        angles = {
            Direction.UP: 0,
            Direction.LEFT: 90,
            Direction.DOWN: 180,
            Direction.RIGHT: -90,
        }
        icon = pygame.transform.rotate(icon, angles[arrow.direction])
        icon = pygame.transform.smoothscale(icon, (size, size))
        surface.blit(icon, icon.get_rect(center=(int(center[0]), int(center[1]))))

    def draw_flying_animations(self) -> None:
        for animation in self.flying:
            progress = animation.progress
            eased = 1 - (1 - progress) ** 3
            position = animation.start.lerp(animation.end, eased)
            alpha = int(255 * (1 - progress * 0.65))
            self.draw_arrow_icon(
                self.screen,
                animation.arrow,
                position,
                52 + int(progress * 12),
                self.arrow_color(animation.arrow),
                alpha,
            )

    def draw_result_screen(self, success: bool) -> None:
        mouse = pygame.mouse.get_pos()
        card = pygame.Rect(260, 120, 480, 540)
        pygame.draw.rect(self.screen, SHADOW, card.move(0, 5), border_radius=28)
        pygame.draw.rect(self.screen, PANEL, card, border_radius=28)
        pygame.draw.rect(self.screen, GRID, card, 1, border_radius=28)
        color = CYAN if success else RED
        pygame.draw.circle(self.screen, color, (500, 230), 64)
        if success:
            pygame.draw.lines(
                self.screen,
                WHITE,
                False,
                ((469, 229), (490, 250), (532, 207)),
                10,
            )
        else:
            draw_text(self.screen, "!", self.font_xl, WHITE, (500, 226), "center")
        title = "关卡通过！" if success else "挑战失败"
        subtitle = (
            f"你已清空第 {self.level_index + 1} 关的全部箭头"
            if success
            else "失误机会已经用完，再观察一下箭头顺序吧"
        )
        title_y = 352 if success else 335
        if success:
            self.draw_stars((500, 305), self.result_stars, 17)
        draw_text(self.screen, title, self.font_lg, INK, (500, title_y), "center")
        draw_text(self.screen, subtitle, self.font_small, MUTED, (500, 392), "center")
        draw_text(
            self.screen,
            f"点击 {self.level_clicks} 次  ·  用时 {int(self.elapsed_time)} 秒  ·  提示 {self.hints_used} 次",
            self.font_body,
            color,
            (500, 432),
            "center",
        )
        if success:
            best_score = self.progress.record_for(self.level_index).best_score
            draw_text(
                self.screen,
                f"本局 {self.result_score} 分  ·  最佳 {best_score} 分",
                self.font_body,
                ORANGE,
                (500, 469),
                "center",
            )
        self.result_primary.text = "下一关" if success else "重新挑战"
        self.result_secondary.text = "重玩本关" if success else "返回首页"
        self.result_primary.draw(self.screen, self.font_body, mouse)
        self.result_secondary.draw(self.screen, self.font_body, mouse)

    def draw_complete_screen(self) -> None:
        mouse = pygame.mouse.get_pos()
        card = pygame.Rect(230, 104, 540, 560)
        pygame.draw.rect(self.screen, SHADOW, card.move(0, 5), border_radius=30)
        pygame.draw.rect(self.screen, PANEL, card, border_radius=30)
        pygame.draw.rect(self.screen, GRID, card, 1, border_radius=30)
        for radius, color in ((76, BLUE), (57, CYAN), (36, ORANGE)):
            pygame.draw.circle(self.screen, color, (500, 235), radius, 4)
        draw_text(self.screen, "★", self.font_xl, ORANGE, (500, 230), "center")
        draw_text(self.screen, "全部通关", self.font_lg, INK, (500, 350), "center")
        draw_text(
            self.screen,
            f"恭喜你完成全部 {len(LEVELS)} 个原创关卡！",
            self.font_body,
            MUTED,
            (500, 398),
            "center",
        )
        self.result_primary.text = "从头挑战"
        self.result_secondary.text = "返回首页"
        self.result_primary.draw(self.screen, self.font_body, mouse)
        self.result_secondary.draw(self.screen, self.font_body, mouse)

    def save_screenshot(self, path: Path) -> None:
        self.draw()
        pygame.display.flip()
        pygame.image.save(self.screen, str(path))


def capture_screenshots(output_directory: str | Path) -> list[Path]:
    """生成 README 所需的真实界面截图。"""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    app = GameApp(headless=True)
    paths: list[Path] = []

    captures = (
        ("start.png", "start"),
        ("levels.png", "level_select"),
        ("game.png", "playing"),
        ("hint.png", "hint_demo"),
        ("auto_solve.png", "auto_demo"),
        ("success.png", "level_clear"),
        ("failure.png", "failed"),
        ("complete.png", "complete"),
    )
    for filename, state in captures:
        if state == "level_select":
            app.progress.unlocked_level = 4
            app.progress.record_completion(0, 3, 1320, 18.0, len(LEVELS))
            app.progress.record_completion(1, 2, 980, 31.0, len(LEVELS))
            app.progress.record_completion(2, 1, 720, 49.0, len(LEVELS))
            app.state = "level_select"
        elif state == "playing":
            app.start_level(1)
            app.board.mistakes_left -= 1
            app.collision = CollisionAnimation((1, 3), (4, 3), elapsed=0.18)
            app.toast = "前方有阻挡，剩余 2 次机会"
            app.toast_time = 1.0
        elif state == "hint_demo":
            app.start_level(0)
            solution = find_solution(app.board)
            app.hint_position = solution[0] if solution else None
            app.hint_time = 2.0
            app.hints_used = 1
            app.toast = "青色光圈标出了可安全飞出的箭头"
            app.toast_time = 2.0
        elif state == "auto_demo":
            app.start_level(0)
            app.start_auto_solve()
            app.update(0.5)
            app.update(0.02)
            app.toast = "AI 正在按求解序列自动演示"
            app.toast_time = 1.5
        elif state == "level_clear":
            app.state = "level_clear"
            app.level_clicks = len(app.level.arrows)
            app.elapsed_time = 23.0
            app.hints_used = 0
            app.result_stars = 3
            app.result_score = 1270
            app.progress.record_completion(
                app.level_index, 3, 1270, 23.0, len(LEVELS)
            )
        elif state == "failed":
            app.start_level(2)
            app.board.mistakes_left = 0
            app.level_clicks = 5
            app.elapsed_time = 18.0
            app.state = "failed"
        elif state == "complete":
            app.progress.unlocked_level = len(LEVELS) - 1
            for index in range(len(LEVELS)):
                app.progress.record_completion(
                    index,
                    3 if index < 3 else 2,
                    1200 - index * 70,
                    20.0 + index * 6,
                    len(LEVELS),
                )
            app.state = "complete"
        else:
            app.state = state
        path = output / filename
        app.save_screenshot(path)
        paths.append(path)

    pygame.quit()
    return paths
