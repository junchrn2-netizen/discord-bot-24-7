# 军事管理 Discord Bot

一个用于 Discord 军事服务器的管理机器人，提供军衔管理、互动训练、嵌入消息和部署健康检查。

## 功能

- 通过 `/promote`、`/demote`、`/exile` 和 `/setrank` 管理军衔，记录操作原因并发送日志。
- 通过 `/train` 运行面向市民或军人的互动规则训练。
- 使用 `/embed` 或 `!embed` 发布自定义嵌入消息。
- 在 `GET /` 上提供 `OK` 健康检查，便于部署平台探测服务。
- 同时支持斜杠命令和 `!` 前缀命令；`!sync` 仅限服务器管理员使用。

## 本地运行

1. 在 [Discord Developer Portal](https://discord.com/developers/applications) 创建应用和 Bot，复制 Bot token，并在 **Bot** 页面启用 **Message Content Intent** 与 **Server Members Intent**。
2. 邀请 Bot 加入服务器；OAuth2 scopes 至少选择 `bot` 和 `applications.commands`。Bot 的角色需要高于它要管理的角色，并具备 **Manage Roles** 权限。
3. 安装依赖并配置环境变量：

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

4. 在 `.env` 中填入 `DISCORD_BOT_TOKEN`，然后启动：

   ```bash
   python bot.py
   ```

5. 在 Discord 中由管理员运行 `!sync` 一次以同步斜杠命令。全局命令可能需要一段时间才会显示。

> 不要提交 `.env` 或 Bot token。若 token 泄露，请立即在 Developer Portal 中重置。

## 配置

`bot.py` 顶部集中保存服务器专属的角色和频道 ID：

- `INTERNAL_AFFAIRS_ROLE`：内务部门角色；成员受到额外保护。
- `RANK_IDS`、`RANK_NAMES`、`TIER_CONFIG`：军衔与阶级角色映射。
- `LOG_RANK_CHANGE`：军衔变更日志频道。
- `PROMOTE_CD_HOURS`：各军衔的晋升冷却时间。

部署前请将这些 ID 更新为自己服务器中的 ID。开启 Discord 开发者模式后，可右键复制角色或频道 ID。

## 部署

`Procfile` 使用 `worker: python bot.py`。部署平台应设置 `DISCORD_BOT_TOKEN` 环境变量；健康检查端口从 `PORT` 读取，默认 `10000`。可用 `LOG_LEVEL`（默认 `INFO`）调整日志详细程度。
