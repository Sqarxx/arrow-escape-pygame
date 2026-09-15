# 提交前检查清单

项目代码、测试、截图和博客草稿已经完成。以下项目包含你的个人信息或外部账号操作，需要由你在提交前确认。

## 必须完成

- [ ] 运行 `python main.py`，亲自通关并确认自己能解释路径检测代码；
- [ ] 在 `BLOG.md` 顶部填写课程链接、作业链接、学号和 GitHub 仓库链接；
- [ ] 按自己的真实学习与试玩时间校准 `BLOG.md` 的 PSP“实际耗时”；
- [ ] 将本地仓库推送到自己的 GitHub，并确认仓库可以被助教访问；
- [ ] 把 `BLOG.md` 发布到课程要求的博客平台，检查图片能否显示；
- [ ] 提交前再次运行 `python -m unittest discover -v`。

## GitHub 上传命令

先在 GitHub 网页新建一个空仓库（不要再次添加 README 或 `.gitignore`），然后在本目录执行：

```powershell
git remote add origin https://github.com/你的用户名/arrow-escape-pygame.git
git push -u origin main
```

上传后，把真实仓库链接同时填入 `BLOG.md`。如果修改了个人信息，再提交并推送：

```powershell
git add BLOG.md
git commit -m "docs: 填写课程与仓库信息"
git push
```

## 可选加分材料

- [ ] 用系统录屏录制 20～40 秒演示，展示成功飞出、碰撞、通关和失败；
- [ ] 将视频或 GIF 放入博客，不建议把体积较大的视频直接提交到 Git 仓库；
- [ ] 在答辩前阅读 `arrow_game/core.py` 和 `arrow_game/app.py` 中的注释。
