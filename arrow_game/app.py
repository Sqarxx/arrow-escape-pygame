"""Pygame 图形界面、交互和动画。"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path

import pygame

from .core import Arrow, ClickResult, Direction, find_solution
from .levels import LEVELS


WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 760
FPS = 60
BOARD_LEFT = 58
BOARD_TOP = 142
CELL_SIZE = 78

BG_TOP = (18, 31, 53)
BG_BOTTOM = (29, 53, 82)
PANEL = (245, 248, 252)
BOARD_BG = (231, 239, 247)
GRID = (198, 213, 227)
INK = (30, 47, 68)
MUTED = (91, 109, 129)
BLUE = (39, 134, 246)
BLUE_DARK = (27, 105, 208)
CYAN = (57, 203, 192)
ORANGE = (246, 158, 68)
RED = (234, 78, 91)
WHITE = (255, 255, 255)


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
            color = (224, 234, 244) if hovered else WHITE
            text_color = INK
            border_color = GRID
        shadow = self.rect.move(0, 4)
        pygame.draw.rect(surface, (13, 25, 43, 70), shadow, border_radius=14)
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


class GameApp:
    """小游戏应用。游戏状态只在此处负责切换，规则由 Board 负责。"""

    def __init__(self, headless: bool = False) -> None:
        pygame.init()
        pygame.display.set_caption("一箭又一箭 · Arrow Escape")
        flags = pygame.HIDDEN if headless else 0
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), flags)
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "start"
        self.level_index = 0
        self.board = LEVELS[0].create_board()
        self.elapsed_time = 0.0
        self.level_clicks = 0
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

        self.start_button = Button(pygame.Rect(385, 500, 230, 62), "开始游戏")
        self.restart_button = Button(pygame.Rect(684, 512, 250, 52), "重新开始", False)
        self.hint_button = Button(pygame.Rect(684, 578, 250, 52), "提示一步", False)
        self.home_button = Button(pygame.Rect(684, 644, 250, 52), "返回首页", False)
        self.result_primary = Button(pygame.Rect(362, 485, 276, 58), "下一关")
        self.result_secondary = Button(pygame.Rect(362, 558, 276, 52), "重玩本关", False)

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

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    def start_level(self, index: int) -> None:
        self.level_index = index
        self.board = LEVELS[index].create_board()
        self.state = "playing"
        self.elapsed_time = 0.0
        self.level_clicks = 0
        self.flying.clear()
        self.collision = None
        self.hint_position = None
        self.hint_time = 0.0
        self.toast = ""
        self.toast_time = 0.0

    def restart_level(self) -> None:
        self.start_level(self.level_index)

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
                self.state = "start"
        elif self.state == "start" and key in (pygame.K_RETURN, pygame.K_SPACE):
            self.start_level(0)
        elif self.state == "playing":
            if key == pygame.K_r:
                self.restart_level()
            elif key == pygame.K_h:
                self.show_hint()
        elif self.state == "level_clear" and key in (pygame.K_RETURN, pygame.K_SPACE):
            self.go_to_next_level()
        elif self.state == "failed" and key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
            self.restart_level()
        elif self.state == "complete" and key in (pygame.K_RETURN, pygame.K_SPACE):
            self.start_level(0)

    def handle_click(self, position: tuple[int, int]) -> None:
        if self.state == "start":
            if self.start_button.hit(position):
                self.start_level(0)
            return

        if self.state == "playing":
            if self.restart_button.hit(position):
                self.restart_level()
            elif self.hint_button.hit(position):
                self.show_hint()
            elif self.home_button.hit(position):
                self.state = "start"
            elif not self.flying and self.collision is None:
                cell = self.pixel_to_cell(position)
                if cell is not None:
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

        if self.state == "playing" and not self.flying and self.collision is None:
            if self.board.is_failed:
                self.state = "failed"
            elif self.board.is_cleared:
                self.state = "level_clear"

    def draw(self) -> None:
        self.draw_background()
        if self.state == "start":
            self.draw_start_screen()
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
            (90, 80, 150, 12),
            (900, 120, 190, 10),
            (820, 700, 240, 8),
        ):
            glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*CYAN, alpha), (radius, radius), radius)
            self.screen.blit(glow, (x - radius, y - radius))

    def draw_start_screen(self) -> None:
        mouse = pygame.mouse.get_pos()
        draw_text(self.screen, "一箭又一箭", self.font_xl, WHITE, (500, 150), "center")
        draw_text(
            self.screen,
            "ARROW  ESCAPE",
            self.font_small,
            CYAN,
            (500, 205),
            "center",
        )
        draw_text(
            self.screen,
            "看清方向 · 判断阻挡 · 按序清空棋盘",
            self.font_body,
            (188, 205, 222),
            (500, 253),
            "center",
        )
        self.draw_logo((500, 365))
        self.start_button.draw(self.screen, self.font_md, mouse)
        draw_text(
            self.screen,
            "鼠标点击箭头｜R 重新开始｜H 提示｜Esc 返回",
            self.font_small,
            (159, 179, 201),
            (500, 600),
            "center",
        )
        draw_text(
            self.screen,
            f"原创 {len(LEVELS)} 关 · 每关均通过自动求解验证",
            self.font_small,
            (115, 140, 166),
            (500, 650),
            "center",
        )

    def draw_logo(self, center: tuple[int, int]) -> None:
        pygame.draw.circle(self.screen, (31, 65, 94), center, 88)
        pygame.draw.circle(self.screen, CYAN, center, 88, 3)
        arrow = Arrow(0, 0, Direction.RIGHT)
        self.draw_arrow_icon(self.screen, arrow, center, 68, WHITE)
        for angle in (45, 135, 225, 315):
            radians = math.radians(angle)
            point = (
                int(center[0] + math.cos(radians) * 110),
                int(center[1] + math.sin(radians) * 110),
            )
            pygame.draw.circle(self.screen, BLUE, point, 7)

    def draw_game_screen(self) -> None:
        mouse = pygame.mouse.get_pos()
        draw_text(
            self.screen,
            f"第 {self.level_index + 1} 关  ·  {self.level.name}",
            self.font_lg,
            WHITE,
            (58, 58),
        )
        draw_text(
            self.screen,
            "点击箭头，前方无遮挡即可飞出",
            self.font_small,
            (164, 184, 207),
            (60, 106),
        )
        self.draw_board(mouse)
        self.draw_side_panel(mouse)
        self.draw_flying_animations()

        if self.toast_time > 0:
            toast_width = min(520, max(270, len(self.toast) * 22 + 48))
            toast = pygame.Rect((WINDOW_WIDTH - toast_width) // 2, 704, toast_width, 38)
            pygame.draw.rect(self.screen, (12, 24, 41), toast, border_radius=19)
            draw_text(self.screen, self.toast, self.font_small, WHITE, toast.center, "center")

    def draw_board(self, mouse: tuple[int, int]) -> None:
        rect = self.board_rect
        shadow = rect.inflate(16, 16).move(0, 7)
        pygame.draw.rect(self.screen, (10, 21, 37), shadow, border_radius=22)
        pygame.draw.rect(self.screen, BOARD_BG, rect.inflate(16, 16), border_radius=22)

        for row in range(self.board.rows):
            for col in range(self.board.cols):
                cell = pygame.Rect(
                    BOARD_LEFT + col * CELL_SIZE,
                    BOARD_TOP + row * CELL_SIZE,
                    CELL_SIZE,
                    CELL_SIZE,
                )
                color = (239, 245, 250) if (row + col) % 2 == 0 else (228, 237, 246)
                pygame.draw.rect(self.screen, color, cell)
                pygame.draw.rect(self.screen, GRID, cell, 1)

        hover_cell = self.pixel_to_cell(mouse)
        for position, arrow in self.board.arrows.items():
            center = self.cell_center(position)
            color = BLUE
            scale = 50
            if position == hover_cell and self.collision is None:
                color = BLUE_DARK
                scale = 56
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
                CYAN,
                alpha,
            )

    def draw_side_panel(self, mouse: tuple[int, int]) -> None:
        panel = pygame.Rect(654, 142, 304, 570)
        pygame.draw.rect(self.screen, PANEL, panel, border_radius=22)
        draw_text(self.screen, "关卡状态", self.font_md, INK, (684, 175))
        self.draw_stat_card((684, 224), "剩余箭头", str(self.board.remaining), BLUE)
        self.draw_stat_card((684, 313), "失误机会", str(self.board.mistakes_left), RED)
        minutes, seconds = divmod(int(self.elapsed_time), 60)
        self.draw_stat_card((684, 402), "本关用时", f"{minutes:02d}:{seconds:02d}", CYAN)
        self.restart_button.draw(self.screen, self.font_body, mouse)
        self.hint_button.draw(self.screen, self.font_body, mouse)
        self.home_button.draw(self.screen, self.font_body, mouse)

    def draw_stat_card(
        self,
        position: tuple[int, int],
        label: str,
        value: str,
        accent: tuple[int, int, int],
    ) -> None:
        rect = pygame.Rect(position[0], position[1], 250, 72)
        pygame.draw.rect(self.screen, WHITE, rect, border_radius=14)
        pygame.draw.rect(self.screen, accent, (rect.x, rect.y, 7, rect.height), border_radius=4)
        draw_text(self.screen, label, self.font_small, MUTED, (rect.x + 25, rect.y + 13))
        draw_text(self.screen, value, self.font_md, accent, (rect.right - 22, rect.centery), "midright")

    def draw_result_screen(self, success: bool) -> None:
        mouse = pygame.mouse.get_pos()
        card = pygame.Rect(260, 120, 480, 540)
        pygame.draw.rect(self.screen, PANEL, card, border_radius=28)
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
        draw_text(self.screen, title, self.font_lg, INK, (500, 330), "center")
        draw_text(self.screen, subtitle, self.font_small, MUTED, (500, 379), "center")
        draw_text(
            self.screen,
            f"点击次数 {self.level_clicks}    用时 {int(self.elapsed_time)} 秒",
            self.font_body,
            color,
            (500, 430),
            "center",
        )
        self.result_primary.text = "下一关" if success else "重新挑战"
        self.result_secondary.text = "重玩本关" if success else "返回首页"
        self.result_primary.draw(self.screen, self.font_body, mouse)
        self.result_secondary.draw(self.screen, self.font_body, mouse)

    def draw_complete_screen(self) -> None:
        mouse = pygame.mouse.get_pos()
        card = pygame.Rect(230, 104, 540, 560)
        pygame.draw.rect(self.screen, PANEL, card, border_radius=30)
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
    """生成 README 所需的四张真实界面截图。"""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    app = GameApp(headless=True)
    paths: list[Path] = []

    captures = (
        ("start.png", "start"),
        ("game.png", "playing"),
        ("success.png", "level_clear"),
        ("failure.png", "failed"),
    )
    for filename, state in captures:
        if state == "playing":
            app.start_level(1)
            app.board.mistakes_left -= 1
            app.collision = CollisionAnimation((1, 3), (4, 3), elapsed=0.18)
            app.toast = "前方有阻挡，剩余 2 次机会"
            app.toast_time = 1.0
        elif state == "level_clear":
            app.state = "level_clear"
            app.level_clicks = len(app.level.arrows)
            app.elapsed_time = 23.0
        elif state == "failed":
            app.start_level(2)
            app.board.mistakes_left = 0
            app.level_clicks = 5
            app.elapsed_time = 18.0
            app.state = "failed"
        else:
            app.state = state
        path = output / filename
        app.save_screenshot(path)
        paths.append(path)

    pygame.quit()
    return paths
