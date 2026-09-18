"""项目启动入口。"""

from __future__ import annotations

import argparse
import os


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="一箭又一箭小游戏")
    parser.add_argument(
        "--capture-screenshots",
        metavar="DIR",
        help="不打开窗口，向指定目录生成 README 界面截图",
    )
    parser.add_argument(
        "--capture-gifs",
        metavar="DIR",
        help="不打开窗口，向指定目录生成博客功能演示 GIF",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.capture_screenshots:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        from arrow_game.app import capture_screenshots

        paths = capture_screenshots(args.capture_screenshots)
        for path in paths:
            print(f"已生成：{path}")
    elif args.capture_gifs:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        from arrow_game.media import capture_gifs

        paths = capture_gifs(args.capture_gifs)
        for path in paths:
            print(f"已生成：{path}")
    else:
        from arrow_game.app import GameApp

        GameApp().run()


if __name__ == "__main__":
    main()
