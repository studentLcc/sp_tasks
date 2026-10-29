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
- `sp_tasks.send_daily_summary`：整理当天任务并出站推送。

任务保存在 Home Assistant 的存储中，重启后仍然存在。同一天重复同步会覆盖当天记录。

## 每天 07:00 推送

在 HA 的自动化界面新建一个时间触发，时间为 `07:00:00`，动作选择 `sp_tasks.send_daily_summary`。示例见 [examples/daily_summary.yaml](examples/daily_summary.yaml)。

Server酱³ 的 SendKey 以 `sctp` 开头。标准的 `sctp<uid>t...` 会自动识别 UID；无法识别时，在集成配置里填写 UID。

## 桥接服务

HACS 只安装 HA 接收端。在 Super Productivity 所在设备上：

1. 打开 `Settings → Misc → Enable local REST API`，复制 Access Token。
2. 在 HA 的用户资料页创建长期访问令牌。
3. 按 [.env.example](.env.example) 创建 `.env`。
4. 在本仓库目录运行 `python3 -m bridge.app`。

默认监听 `127.0.0.1:8787`。进程启动后立即同步，之后每 15 分钟同步一次。手动同步：

```bash
curl -X POST http://127.0.0.1:8787/sync
```

也可以使用 [Dockerfile](Dockerfile) 或 [systemd/sp-ha-bridge.service](systemd/sp-ha-bridge.service)。桥接服务只绑定本机或受控网络，不要暴露到公网。

## 验证

```bash
python3 -m unittest discover -s tests -v
```

同步成功后，在 HA 开发者工具中查看“今日任务”传感器，再手动运行 `sp_tasks.send_daily_summary`。
