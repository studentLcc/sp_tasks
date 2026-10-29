# Super Productivity 任务

这个仓库包含两个部分：

1. Home Assistant 集成 `custom_components/sp_tasks`：装在 HAOS 里，接收并保存任务。用 HACS 安装。
2. 桥接服务 `bridge`：跑在 Super Productivity 那台电脑上，读取本机任务并推送到 HAOS。用 Podman 运行。

桥接服务不会直接发企业微信或 Server酱。HA 收到任务后，用你已经配置好的 `rest_command` 发送。

```text
Super Productivity 桌面端
  → 本机 Podman 桥接（启动时立刻推送，之后每 15 分钟）
  → HA 集成 /api/sp_tasks/tasks
  → 传感器属性 desp
  → 你的 Server酱 rest_command
```

推送范围是未完成、并且有计划日期的任务：

- 已过期：计划日期早于今天
- 今天：计划日期是今天
- 一周内：明天起 7 天内

没有计划日期的任务，以及 7 天以后的任务，不会推送。

## 1. 在 HAOS 安装集成

1. 打开 HACS，进入集成，选择右上角菜单里的自定义仓库。
2. 填入 `https://github.com/studentLcc/sp_tasks`，类别选择集成。
3. 下载“SP任务”，重启 Home Assistant。
4. 打开“设置 → 设备与服务 → 添加集成”，搜索“SP任务”并添加。这里不用填 Server酱 或企业微信。

添加后会出现传感器，名称是“Super Productivity 任务 今日任务”。在“开发者工具 → 状态”里打开它，最上面的实体 ID 才是自动化要使用的 ID。

传感器状态是任务数量。属性如下：

| 属性 | 含义 |
| --- | --- |
| `desp` | 给 Server酱 正文使用的文本 |
| `tasks` | 任务列表 |
| `groups` | 按已过期、今天、一周内分组 |
| `date` | 这次同步使用的日期 |
| `last_sync` | 最近一次同步时间 |

`desp` 只包含分类和任务标题。有具体钟点时才写时间，有备注时才写内容。正文不再重复通知标题，也不再给每条任务加日期。

## 2. 在 Super Productivity 电脑上运行桥接

Super Productivity 必须是桌面版，并且和 Podman 在同一台 Linux 电脑上。

1. 打开 `Settings → Misc → Enable local REST API`，复制 Access Token。
2. 在 HA 的用户资料页最底部创建长期访问令牌。
3. 复制环境变量示例：

```bash
cp .env.example .env
```

4. 编辑 `.env`，至少修改这几项：

```bash
SP_API_TOKEN=Super Productivity 的 Access Token
HA_URL=http://HAOS的IP:8123
HA_TOKEN=Home Assistant 长期访问令牌
TZ=Asia/Shanghai
SYNC_INTERVAL_SECONDS=900
```

`900` 表示每 15 分钟向 HAOS 推送一次。容器启动时还会立刻推送一次。

5. 构建并启动。必须使用主机网络，容器才能访问只监听在 `127.0.0.1:3876` 的 Super Productivity：

```bash
podman build -t sp-ha-bridge:local .
podman run -d --replace --name sp-ha-bridge --network host --env-file .env --restart unless-stopped localhost/sp-ha-bridge:local
```

6. 手动推送一次：

```bash
curl -X POST http://127.0.0.1:8787/sync
```

返回 `"ok": true` 后，回到 HA 查看传感器属性。`desp` 里应能看到“已过期、今天、一周内”。

常用命令：

```bash
podman logs -f sp-ha-bridge
podman restart sp-ha-bridge
```

更新桥接代码后，在仓库目录重新执行上面的 `podman build` 和 `podman run --replace`。只更新 HACS 不会改变正文格式，正文是桥接服务生成的。

## 3. 每天早上用已有的 Server酱 发送

把动作名换成你的 `rest_command` 名称，把实体 ID 换成开发者工具里看到的那个：

```yaml
alias: 早上发送任务
trigger:
  - platform: time
    at: "07:00:00"
action:
  - action: rest_command.你的server酱命令名
    data:
      title: "任务（{{ state_attr('你的实体ID', 'date') }}）"
      desp: "{{ state_attr('你的实体ID', 'desp') }}"
      tags: "任务"
```

通知标题放日期。正文不再重复这个标题。示例文件是 [examples/daily_summary.yaml](examples/daily_summary.yaml)。

## 4. 不要提交的内容

`.env` 里有 Super Productivity 令牌和 HA 令牌。它已经在 `.gitignore` 里，不要提交，也不要写进说明。
