# claude-bili-reply

用 Claude Code 自动回复 B站 视频评论。计划任务每小时跑一轮，拉下新评论，让 Claude 按你写的规则查你给的资料，写好回复，校验通过后用你的账号发出去。带一个状态页，能看到这一轮在查什么、回了什么、跳过了什么。

作者自己的《影之刃零全解析》系列就是这套在回，查的是游戏解包数据。那份规则和查数据的脚本放在 examples/pbz 里，可以照着改。

## 一轮做什么

1. 用 config.toml 里的 cookie 拉 videos.json 里每期视频的全部评论，去掉 state/seen.json 里处理过的和 UP 主自己的。没有新评论就结束，不调用模型。
2. 把新评论连同楼里的上下文写进 state/inbox/<时间>.json。
3. 调 `claude -p`，让它按 PLAYBOOK.md 处理，把每条的回复或跳过写进 state/out/<时间>.json。它只能读写本目录的文件，不能联网，不能发评论。
4. run.py 检查输出（rpid 必须在 inbox 里，内容非空、不超过 1000 字、没有破折号），逐条发出，间隔 6 秒，记进 state/log.md。
5. 模型这一轮没写出输出文件时不标记已读，下一轮重试。

## 需要什么

1. Windows（计划任务和状态页里查任务状态用的是 PowerShell，回复逻辑本身不挑系统）。
2. Python 3.11 以上，只用标准库。
3. 装好并登录了 Claude Code，命令行里 `claude -p "hi"` 能出结果。
4. 能登录视频所在 B站 账号的浏览器，用来取 cookie。

## 装好

1. 克隆这个仓库。复制 config.example.toml 为 config.toml，填 [bili] 里的 cookie。浏览器按 F12，在应用（Application）、Cookie、bilibili.com 下找这几项。
2. 复制 videos.example.json 为 videos.json，每期视频写一项（ep 自己起的编号、aid、bvid、title）。aid 在视频页按 F12 控制台输入 `window.__INITIAL_STATE__.aid` 能看到。
3. 把你的资料放进本目录（项目代码、文档、数据表、视频文稿都行），再改 PLAYBOOK.md，写清楚资料在哪、怎么查、用什么口吻回。
4. 运行 `python run.py check`，返回 True 和你的昵称说明 cookie 能用。
5. 运行 `python run.py init`，把现在已有的评论都标成已处理。不想回旧评论时做这一步，想回的话给一个时间，比如 `python run.py init 1761800000` 只标这个 unix 时间以前的。
6. 运行 `python run.py fetch` 看有哪些新评论，再 `python run.py round` 手动跑一轮，看 state/out 和 state/log.md 里回得对不对。
7. 没问题以后用 PowerShell 运行 `.\install-task.ps1`，注册每小时一轮的计划任务和状态页。状态页默认 http://127.0.0.1:8789。想在手机上看就加 `-WebHost 你的局域网或 Tailscale 地址`，脚本会只对 `-AllowFrom` 给的网段开防火墙。间隔用 `-Minutes` 改。

## 改什么在哪

1. 回复的口吻、回不回的标准、查资料的方法，改 PLAYBOOK.md。
2. 用哪个模型、思考强度、一轮最长多久，改 config.toml 的 [agent]。默认 sonnet、medium、45 分钟。
3. 走自己的 API 网关时，在本目录建 agent.env，内容是一个 JSON 对象，比如 `{"ANTHROPIC_BASE_URL": "...", "ANTHROPIC_AUTH_TOKEN": "..."}`，run.py 调 claude 时会带上这些环境变量。
4. 模型每轮会把查实的结论补进 knowledge/facts.md，查出的视频错误补进 knowledge/video_errors.md。后者可以拿来决定要不要发勘误。

## 常用命令

1. `python run.py check` 看 cookie 是否还登录着。
2. `python run.py fetch` 打印没处理的新评论，不调用模型、不发评论。
3. `python run.py round` 手动跑一轮。
4. `python run.py post 文件` 按一个输出文件发评论（格式同 state/out），用来手动补发或改错。
5. `python run.py init [unix时间]` 把这个时间以前的评论全部标成已处理。
6. `schtasks /end /tn bili-reply` 停掉正在跑的一轮，`schtasks /change /tn bili-reply /disable` 关掉计划任务。

## 出问题先看哪里

1. cookie 失效时 state/log.md 会写登录失效，状态页也会显示。重新取 cookie 填进 config.toml。
2. 每轮模型的完整过程在 state/runs/<时间>.jsonl，回复不对时先看这里，再改 PLAYBOOK.md。
3. 每轮的 token 用量记在 state/log.md 和 state/rounds.json。

## 文件

1. run.py 一轮的流程和上面的命令。
2. bili.py B站 接口（拉评论、回复、删除、私信），只用标准库。
3. web.py 和 web.html 状态页。
4. install-task.ps1 和 run-hidden.vbs 注册计划任务，后台跑不弹窗。
5. PLAYBOOK.md 给模型的规则模板。examples/pbz 是实际在用的一份（规则、视频表、查解包数据的脚本）。

## 许可

MIT
