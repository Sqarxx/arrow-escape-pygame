"""录制文档使用的真实游戏 GIF。"""

from __future__ import annotations

from pathlib import Path

import pygame
from PIL import Image

from .app import BLUE, RED, GameApp, WINDOW_HEIGHT, WINDOW_WIDTH


GIF_WIDTH = 700
GIF_HEIGHT = round(WINDOW_HEIGHT * GIF_WIDTH / WINDOW_WIDTH)
FRAME_DURATION_MS = 100


class GifRecorder:
    """把 Pygame 画面转换为尺寸较小、颜色稳定的 GIF。"""

    def __init__(self) -> None:
        self.frames: list[Image.Image] = []

    def capture(
        self,
        app: GameApp,
        cursor: tuple[int, int] | None = None,
        clicking: bool = False,
    ) -> None:
        app.draw()
        surface = app.screen.copy()
        if cursor is not None:
            if clicking:
                pygame.draw.circle(surface, RED, cursor, 20, 4)
            pygame.draw.circle(surface, (255, 255, 255), cursor, 10)
            pygame.draw.circle(surface, BLUE, cursor, 10, 3)

        image = Image.frombytes(
            "RGB",
            (WINDOW_WIDTH, WINDOW_HEIGHT),
            pygame.image.tobytes(surface, "RGB"),
        )
        image = image.resize((GIF_WIDTH, GIF_HEIGHT), Image.Resampling.LANCZOS)
        self.frames.append(image)

    def hold(
        self,
        app: GameApp,
        count: int,
        dt: float = 0.1,
        cursor: tuple[int, int] | None = None,
        clicking: bool = False,
    ) -> None:
        for _ in range(count):
            self.capture(app, cursor, clicking)
            app.update(dt)

    def move(
        self,
        app: GameApp,
        start: tuple[int, int],
        end: tuple[int, int],
        count: int = 6,
    ) -> None:
        for step in range(1, count + 1):
            ratio = step / count
            cursor = (
                round(start[0] + (end[0] - start[0]) * ratio),
                round(start[1] + (end[1] - start[1]) * ratio),
            )
            self.capture(app, cursor)
            app.update(0.1)

    def save(self, path: Path) -> None:
        if not self.frames:
            raise ValueError("没有可保存的 GIF 帧")

        # 全部帧共用首帧生成的调色板，避免播放时颜色闪烁。
        palette = self.frames[0].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
        frames = [
            frame.quantize(palette=palette, dither=Image.Dither.NONE)
            for frame in self.frames
        ]
        frames[0].save(
            path,
            save_all=True,
            append_images=frames[1:],
            duration=FRAME_DURATION_MS,
            loop=0,
            optimize=True,
            disposal=2,
        )


def _new_app() -> GameApp:
    return GameApp(headless=True)


def _record_start_game(path: Path) -> None:
    app = _new_app()
    recorder = GifRecorder()
    recorder.hold(app, 8)
    destination = app.start_button.rect.center
    recorder.move(app, (820, 700), destination)
    recorder.hold(app, 2, cursor=destination, clicking=True)
    app.handle_click(destination)
    recorder.hold(app, 12, cursor=destination)
    recorder.save(path)


def _record_arrow_escape(path: Path) -> None:
    app = _new_app()
    app.start_level(0)
    recorder = GifRecorder()
    position = (1, 2)
    destination = tuple(map(round, app.cell_center(position)))
    recorder.hold(app, 6)
    recorder.move(app, (850, 680), destination)
    recorder.hold(app, 2, cursor=destination, clicking=True)
    app.click_arrow(position)
    recorder.hold(app, 10, 0.07, destination)
    recorder.hold(app, 8)
    recorder.save(path)


def _record_collision(path: Path) -> None:
    app = _new_app()
    app.start_level(0)
    recorder = GifRecorder()
    position = (3, 3)
    destination = tuple(map(round, app.cell_center(position)))
    recorder.hold(app, 6)
    recorder.move(app, (850, 680), destination)
    recorder.hold(app, 2, cursor=destination, clicking=True)
    app.click_arrow(position)
    recorder.hold(app, 10, 0.07, destination)
    recorder.hold(app, 8)
    recorder.save(path)


def _record_hint_undo(path: Path) -> None:
    app = _new_app()
    app.start_level(0)
    recorder = GifRecorder()
    hint = app.hint_button.rect.center
    recorder.hold(app, 5)
    recorder.move(app, (850, 680), hint)
    recorder.hold(app, 2, cursor=hint, clicking=True)
    app.handle_click(hint)
    recorder.hold(app, 12, cursor=hint)

    solution = app.hint_position
    if solution is None:
        raise RuntimeError("提示功能没有返回安全箭头")
    arrow_center = tuple(map(round, app.cell_center(solution)))
    recorder.move(app, hint, arrow_center)
    recorder.hold(app, 2, cursor=arrow_center, clicking=True)
    app.click_arrow(solution)
    recorder.hold(app, 9, 0.07, arrow_center)

    undo = app.undo_button.rect.center
    recorder.move(app, arrow_center, undo)
    recorder.hold(app, 2, cursor=undo, clicking=True)
    app.handle_click(undo)
    recorder.hold(app, 10, cursor=undo)
    recorder.save(path)


def _record_auto_solve(path: Path) -> None:
    app = _new_app()
    app.start_level(0)
    recorder = GifRecorder()
    auto = app.auto_button.rect.center
    recorder.hold(app, 5)
    recorder.move(app, (850, 680), auto)
    recorder.hold(app, 2, cursor=auto, clicking=True)
    app.handle_click(auto)

    for _ in range(70):
        recorder.capture(app, auto)
        app.update(0.12)
        if app.state == "level_clear":
            break
    recorder.hold(app, 12)
    recorder.save(path)


def _record_failure_restart(path: Path) -> None:
    app = _new_app()
    app.start_level(0)
    recorder = GifRecorder()
    position = (3, 3)
    destination = tuple(map(round, app.cell_center(position)))
    recorder.hold(app, 5)

    for _ in range(app.board.max_mistakes):
        recorder.hold(app, 2, cursor=destination, clicking=True)
        app.click_arrow(position)
        recorder.hold(app, 7, 0.09, destination)

    recorder.hold(app, 8)
    restart = app.result_primary.rect.center
    recorder.move(app, (700, 650), restart)
    recorder.hold(app, 2, cursor=restart, clicking=True)
    app.handle_click(restart)
    recorder.hold(app, 10, cursor=restart)
    recorder.save(path)


def capture_gifs(output_directory: str | Path) -> list[Path]:
    """生成博客中使用的六组功能演示 GIF。"""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    jobs = (
        ("start_game.gif", _record_start_game),
        ("arrow_escape.gif", _record_arrow_escape),
        ("collision.gif", _record_collision),
        ("hint_undo.gif", _record_hint_undo),
        ("auto_solve.gif", _record_auto_solve),
        ("failure_restart.gif", _record_failure_restart),
    )
    paths: list[Path] = []
    try:
        for filename, recorder in jobs:
            path = output / filename
            recorder(path)
            paths.append(path)
    finally:
        pygame.quit()
    return paths
