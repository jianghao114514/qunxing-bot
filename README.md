# 群星聚合

一个自部署的 QQ 机器人框架：AI 对话、签到、抽卡、塔罗、星球养成等娱乐功能，带星空主题 Web 管理面板，支持 NapCat 协议端一键对接与掉线自动守护。

## 功能

- **AI 对话**：OpenRouter / DeepSeek / Kimi / 智谱等多 API 提供商，支持容灾切换与每日限额
- **娱乐玩法**：签到、抽卡（SSR/SR/R 概率可调）、塔罗、疯狂星期四、每日老婆、星球养成、星空名片
- **AI 人设**：可自定义多个性格人设，含「病娇」模式（主动发起会话，支持白名单）
- **Web 管理面板**：用户管理、配置修改、功能开关、统计图表、实时日志、内存记忆管理
- **NapCat 一键接入**：自动扫描并保存 NapCat 安装位置，启动 / 打开 WebUI / 复制登录令牌一条龙
- **掉线守护**：NapCat 掉线自动重启，带宽限期防连环重启
- **引导流程**：首次运行自动弹配置引导，填连接信息 + AI Key 即可用

## 环境要求

- Windows 10+（NapCat 依赖 QQNT Windows 版）
- Python 3.10+（可让启动器自动安装）

## 快速开始

### 方式一：启动器（推荐）

1. 下载并解压「群星启动器」，双击 `群星启动器.exe`
2. 启动器自动检测 Python 环境并安装依赖，自动释放程序文件
3. 启动 NapCat 并扫码登录机器人 QQ（面板「NapCat 管理」可一键启动）
4. 浏览器打开 `http://127.0.0.1:5000/`，按引导填写连接信息

### 方式二：源码运行

```bash
pip install -r requirements.txt
python main.py
```

## 首次配置

机器人通过 **NapCat**（QQ 协议端）收发消息，需要：

1. 下载 [NapCat](https://napneko.github.io/) 免安装版并解压
2. 启动 NapCat，手机 QQ 扫码登录机器人账号
3. 在 NapCat「网络配置」中开启 WebSocket 服务器（默认端口 3001）
4. 打开面板，在「配置引导」中填写：
   - `ws_url`：如 `ws://127.0.0.1:3001`
   - `bot_qq`：机器人 QQ 号
   - `master_qq`：管理员 QQ 号（唯一有管理权限的人）
   - AI API Key：OpenRouter / DeepSeek 等

## 数据安全说明

- 所有数据（用户、会话、配置、密钥）保存在本地 `bot_data/` 目录，不会上传
- 建议在面板「配置修改 → 基础设置」中设置**面板访问密码**（设置后 Web 面板与日志推送均需密码）
- 面板默认绑定 `127.0.0.1`，不对外网开放

## 目录结构

```
├── main.py             # 入口
├── launcher.py         # 启动器（自动装环境/依赖/守护）
├── watchdog.py         # NapCat 掉线守护
├── core/               # 配置、数据库(JSON)、AI、WebSocket 客户端
├── plugins/            # 插件（签到/抽卡/对话/人设...）
└── web/                # Flask 面板 + 前端模板 + 桌面窗口
```

## 技术栈

Python · Flask · Flask-SocketIO · Vue 2 · Chart.js · pywebview · websocket-client · NapCat(OneBot)

## 开源许可

[GPLv3](LICENSE) © 群星聚合作者

本项目仅供学习研究使用，请遵守 [QQ 软件许可及服务协议](https://rule.tencent.com/rule/preview/46a0f24e-62c1-47e4-a8e3-8e3e9e8e8e8e) 与当地法律法规，勿用于违规用途。
