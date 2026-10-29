# Super Productivity 任务

Home Assistant 自定义集成。桥接服务把 Super Productivity 的今天任务推到 HA，HA 保存任务，并在每天 07:00 由 HA 自己推送到企业微信机器人和 Server酱³。

```text
Super Productivity 桌面端
  → 运行在 SP 设备上的 bridge
  → HA 集成 /api/sp_tasks/tasks
  → 每天 07:00
  → 企业微信机器人 / Server酱³
```

这个仓库可以用 HACS 安装 HA 集成。它不是 HAOS 加载项：集成必须运行在 Home Assistant 进程里，才能注册接口、传感器和通知服务。加载项是独立容器，不适合承载这个组件。桥接服务仍然单独运行在 Super Productivity 所在的设备上，不随 HACS 安装。

## 用 HACS 安装

1. 打开 HACS → 集成 → 右上角菜单 → 自定义仓库。
2. 仓库地址填写 `https://github.com/studentLcc/sp_tasks`，类别选择“集成”。
3. 搜索并下载“Super Productivity 任务”。
4. 重启 Home Assistant。
5. 打开“设置 → 设备与服务 → 添加集成”，搜索“Super Productivity 任务”。
6. 填入企业微信机器人 Webhook 和/或 Server酱 SendKey。两项都可以留空，以后在集成选项里修改。

安装后会得到：

- `POST /api/sp_tasks/tasks`：桥接服务写入任务。请求必须带 Home Assistant 长期访问令牌。
- `GET /api/sp_tasks/tasks?date=YYYY-MM-DD`：读取指定日期的任务。
- “今日任务”传感器：状态是任务数量，属性包含 `date`、`tasks`、`last_sync`。
- 传感器 `sensor.sp_tasks_today`：状态是今天的任务数量。属性 `tasks` 是任务列表，属性 `message` 是可以直接交给已有 `rest_command` 的正文。
- `sp_tasks.send_daily_summary`：可选动作。已经有 Server酱 `rest_command` 时不用它。

任务保存在 Home Assistant 的存储中，重启后仍然存在。同一天重复同步会覆盖当天记录。

## 每天 07:00 推送

在 HA 的自动化界面新建一个时间触发，时间为 `07:00:00`，动作选择 `sp_tasks.send_daily_summary`。示例见 [examples/daily_summary.yaml](examples/daily_summary.yaml)。

Server酱³ 的 SendKey 以 `sctp` 开头。标准的 `sctp<uid>t...` 会自动识别 UID；无法识别时，在集成配置里填写 UID。

## 桥接服务镜像

HACS 只安装 HA 接收端。桥接镜像要在运行 Super Productivity 的同一台 Linux 电脑上用 Podman 构建，并使用 host 网络，这样容器才能访问 `127.0.0.1:3876`。

```bash
cp .env.example .env
podman build -t sp-ha-bridge:local .
podman run -d --replace --name sp-ha-bridge --network host --env-file .env sp-ha-bridge:local
podman logs -f sp-ha-bridge
curl -X POST http://127.0.0.1:8787/sync
```

已安装 `podman compose` 时，也可以在填写 `.env` 后执行 `podman compose up -d --build`。`.env` 里填写 SP Access Token、HA 地址和 HA 长期访问令牌。容器启动后立即同步，之后每 15 分钟同步一次。

## 验证

```bash
python3 -m unittest discover -s tests -v
```

同步成功后，在 HA 开发者工具中查看“今日任务”传感器，再手动运行 `sp_tasks.send_daily_summary`。
