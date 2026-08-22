# 群星 · 项目交接文档

> 本文件是给接手的 AI（DeepSeek Harness）与开发者阅读的项目说明。
> 项目已开源：https://github.com/jianghao114514/qunxing-bot

---

## 1. 项目是什么

「群星」是一个自部署的 QQ 机器人框架：

- **AI 对话**（多 API 提供商，容灾切换）
- **娱乐玩法**：签到、抽卡、塔罗、疯狂星期四、每日老婆、星球养成、星空名片等
- **AI 人设**（多性格，含病娇主动模式）
- **Web 管理面板**（Flask + Vue 2 + Chart.js + Socket.IO）
- **NapCat 接入**：自动扫描/自动部署/启动/守护
- **B 站开播监控**、进群欢迎语、主题切换等

**定位**：轻量、单机、Windows 优先、个人/小群使用。

---

## 2. 技术栈与环境

| 项 | 值 |
|---|---|
| 语言 | Python 3.13（Windows 上通过 py 启动器/WindowsApps 安装） |
| Web | Flask + flask_socketio（内置，绑定 127.0.0.1:5000） |
| 前端 | Vue 2（CDN 引入）+ Chart.js + Bootstrap，单文件 `web/template.html` |
| 存储 | JSON 文件（`bot_data/`），无数据库 |
| AI | openai 库，兼容 OpenAI 格式的任意提供商 |
| 协议端 | NapCat（OneBot v11 / WebSocket），装在 `bot 目录/napcat/` |
| Node | v24.19.0（`C:\Program Files\nodejs`），仅 DeepSeek Harness 用 |
| Git | Git 2.55（`C:\Program Files\Git\bin\git.exe`） |

---

## 3. 目录结构

```
D:\bot\
├── main.py              # 入口（--no-ui 后台模式 / 桌面模式）
├── launcher.py          # 群星启动器（打包成 exe，自动装环境/依赖/守护）
├── watchdog.py          # NapCat 掉线守护（独立进程）
├── build.py             # 打包脚本（PyInstaller → 群星启动器.exe）
├── build_exe.bat        # 打包入口（双击运行）
├── VERSION              # 版本号文件（年月日命名，见第 6 节）
├── CHANGELOG.md         # 更新日志（每次发版必须更新）
├── README.md            # 开源首页说明
├── LICENSE              # GPLv3
├── requirements.txt     # Python 依赖
├── core/
│   ├── config.py        # 配置加载/保存（bot_data/config.json）
│   ├── database.py      # 用户数据/对话/记忆（JSON）
│   ├── ai.py            # AI 调用（多提供商容灾）
│   ├── ws_client.py     # OneBot WebSocket 客户端 + 各后台线程
│   ├── napcat_finder.py # NapCat 安装位置自动扫描
│   ├── napcat_deploy.py # NapCat 一键自动部署
│   ├── bilibili.py      # B 站公开 API 封装
│   ├── version.py       # 版本号读取
│   ├── yandere.py       # 病娇人设逻辑
│   ├── utils.py / menu_image.py / planet_image.py / profile_image.py
├── plugins/             # 功能插件（插件系统，见第 4 节）
├── web/
│   ├── web_server.py    # Flask 后端 + 全部 /api 接口
│   ├── template.html    # 前端（Vue 单页）
│   ├── desktop.py       # pywebview 桌面窗口
│   └── logo*.svg/png、favicon.*、bg_dark.*   # 品牌素材
├── bot_data/            # 运行时数据（密钥！绝不提交 git）
└── napcat/              # 自动部署的 NapCat（未部署时不存在）
```

---

## 4. 插件系统

- 插件位于 `plugins/`，每个文件一个类，继承 `plugins/base.py:BasePlugin`
- 接口：`match(...)` 判断是否处理 → `handle(...)` 处理并返回 True/False
- 自动加载：`core/plugin_manager.py` 扫描目录加载，支持热重载
- 功能开关：`web_server.py` 的 `api_features` / `api_toggle`（name_map 中文名 ↔ 英文键）
- 后台线程模式参考：`plugins/yandere_active.py`、`plugins/bilibili_watch.py`（在 ws_client.on_open 里启动）

**注意**：新增插件后，菜单映射（menu.py）和功能开关列表（web_server name_map）要同步更新。

---

## 5. GitHub 仓库

- **仓库**：https://github.com/jianghao114514/qunxing-bot（公开，GPLv3）
- **账号**：jianghao114514
- **凭据**：Git 凭据已存 Windows 凭据管理器（git credential manager），push 无需再输密码
- **GitHub CLI**：`C:\Program Files\GitHub CLI\gh.exe`（已安装，但登录方式用 token，见下）
- **API Token**：在 `%APPDATA%\GitHub CLI` 或历史对话中获取；新建 Release 走 GitHub API 需 `Authorization: token <token>`，token 有 repo 权限（**勿提交到仓库**）
- **本地 git**：`C:\Program Files\Git\bin\git.exe`（全局 user.name=jianghao114514, user.email=jianghao114514@users.noreply.github.com）

### 发布流程（重要）

版本号规则见第 6 节。发布一次更新的完整步骤：

```bash
# 1. 改代码
# 2. 更新 VERSION（如 26.8.20 → 26.8.21）
# 3. 更新 CHANGELOG.md 顶部（新版本号 + 本次改动说明）
# 4. 提交并打标签
git add -A
git commit -m "v26.8.20: 一句话说明"
git tag -a v26.8.20 -m "群星 v26.8.20（一句话）"
git push
git push origin v26.8.20
# 5. 重新打包 exe（必须，否则 Release 附件是旧功能）
python build.py        # 产物 dist\群星启动器.exe → 复制为 QunXingLauncher-v26.8.20.exe
# 6. 创建 GitHub Release + 上传 exe（GitHub API，见对话历史脚本模式）
#    POST /repos/jianghao114514/qunxing-bot/releases {tag_name, name, body}
#    POST uploads.github.com/.../assets?name=QunXingLauncher-v26.8.20.exe
```

**README 顶部的版本号**也要同步改。

---

## 6. 版本命名规则

- **格式**：`年.月.日`（如 `26.8.20` = 2026年8月20日）
- **跨天**：换新日期（如 8月20日 → `26.8.20`）
- **同一天多次更新**：末尾加 `.1`、`.2` 递增（如 `26.8.20.1`）
- 存放：`VERSION` 文件（根目录），代码统一从 `core/version.py` 读取
- git 标签：`v` + 版本号（如 `v26.8.20`）
- exe 命名：`QunXingLauncher-v<版本号>.exe`

---

## 7. 关键配置（bot_data/config.json）

敏感字段（web_password/api_key/app_secret/app_token/email.password 等）**绝不提交 git**（.gitignore 已排除 bot_data）。

常用键：
- `ws_url`：NapCat WebSocket 地址（含 token，如 `ws://127.0.0.1:3001/?token=xxx`）
- `bot_qq` / `master_qq`：机器人 QQ / 管理员 QQ（master 唯一有管理权限）
- `web_password`：面板密码（空 = 无认证，仅本机）
- `system_name`：显示名（默认"群星"）
- `welcome_bonus` / `welcome_message`：进群欢迎（支持 {qq}/{bonus}/{currency} 占位符）
- `bilibili_enabled` / `bilibili_watch` / `bilibili_alert_group`：B 站监控
- `napcat_exe` / `napcat_qq` / `napcat_watchdog_enabled`：NapCat
- `api_providers`：AI 提供商列表（可多个，容灾切换）

---

## 8. 日常运维

| 操作 | 方式 |
|---|---|
| 启动机器人 | 双击 `群星启动器.exe`（或 `python main.py`） |
| 停止 | 面板「系统控制 → 停止机器人」 |
| 重启 | 面板「系统控制 → 重启机器人」（重启后不弹窗，页面自动恢复） |
| 卸载 | 面板「系统控制 → 卸载」（分 3 步询问保留数据/Python/NapCat） |
| NapCat 启动 | 面板「NapCat 管理 → 启动 NapCat」（自动扫描位置 + 快捷登录） |
| NapCat 部署 | 面板「一键自动部署」（下载约110MB，支持镜像源，实时进度） |
| NapCat WebUI | 面板按钮打开（端口 6099，token 在 webui.json） |
| 面板地址 | http://127.0.0.1:5000/ |
| 修改模板 | 直接改 `web/template.html`，刷新页面即生效（热更新，无需重启） |
| 修改后端 | 改 py 文件后需重启机器人 |
| 日志 | 面板「实时日志」页（Socket.IO 推送） |

**调试技巧**：`python watchdog.py --once` 可单次检测 NapCat 登录状态。

---

## 9. 安全约定

- `bot_data/`（含密钥）永不进 git；`.gitignore` 已排除
- 面板 `/api/config` 返回的密钥已脱敏（`****`+末4位），保存 masked 值不会覆盖真实值
- 新增 API 注意：QQ 号参数必须 `isdigit()` 校验；provider `base_url` 只允许公网 http/https（防 SSRF）
- web_password 为空时面板无认证（仅绑定 127.0.0.1）
- socket.io 日志推送受 web_password 保护（前端 `io({query:{token}})`）

---

## 10. 接手注意（给 DeepSeek Harness）

- 模型/账号沿用当前 DeepSeek 配置即可，无需更换
- 改代码遵循现有模式：插件继承 BasePlugin、配置走 core/config、数据走 core/database
- 前端是单文件 template.html（Vue 2 语法，无构建步骤），改完直接生效
- 发版必须走第 5 节完整流程（VERSION + CHANGELOG + 标签 + exe + Release）
- 不要往仓库提交：bot_data、.qunxing_version、python_runtime、日志、*.exe、_t.py
- 遇到 GitHub 连接失败：多半是网络问题，重试或让用户开加速器（Steam++，若 443 被占需先结束 Steam++.Accelerator.exe 进程）
- npm 镜像已设为淘宝源；node 在 C:\Program Files\nodejs（新终端可能需要手动加 PATH）
