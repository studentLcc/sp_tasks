# Super Productivity 任务

这个仓库包含两部分：

1. Home Assistant 集成 `custom_components/sp_tasks`：装在 HAOS 里，接收并保存任务。用 HACS 安装。
2. Super Productivity 插件 `plugins/sp-ha-sync`：在 SP 内监听任务变化，并把任务推送到 HAOS。

插件不会直接发企业微信或 Server酱。HA 收到任务后，用你已经配置好的 `rest_command` 发送。

```text
Super Productivity 插件
  → 启动时推送一次，之后在任务变化时推送
  → HA 集成 /api/sp_tasks/tasks
  → 传感器属性 desp
  → 你的 Server酱 rest_command
```

推送范围是未完成的近期任务和所有未安排任务：

- 已过期：计划日期早于今天
- 今天：计划日期是今天
- 一周内：明天起 7 天内
- 未安排：没有计划日期的任务

有计划日期且在 7 天以后的任务不会推送。

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
| `groups` | 按已过期、今天、一周内、未安排分组 |
| `date` | 这次同步使用的日期 |
| `last_sync` | 最近一次同步时间 |

`desp` 包含已过期、今天、一周内和未安排分类及任务标题。有具体钟点时才写时间，有备注时才写内容。正文不再重复通知标题，也不再给每条任务加日期。正文由插件生成。

## 2. 安装 Super Productivity 插件

插件调用 HA 集成的 `/api/sp_tasks/tasks`。它在 SP 启动时推送一次，并在任务数据变化后推送。

SP 的 `PluginAPI.request()` 会拒绝第三方插件请求私有或本机网络。HA 需要通过一个带身份验证和访问控制的 HTTPS 公网入口提供服务；仅在局域网 IP 或 `.local` 主机名上可访问的 HA 无法由这个插件直连。

有公网 HTTPS 入口时，先编辑 [`plugins/sp-ha-sync/manifest.json`](plugins/sp-ha-sync/manifest.json) 的 `allowedHosts` 和 `dataSharing[0].hosts`，加入入口的主机名，然后执行：

```bash
cd plugins/sp-ha-sync
./package.sh
```

在 SP 的 `Settings → Plugins → Choose Plugin File` 中选择生成的 `sp-ha-sync.zip`。安装后在“设置 → 插件”中打开此插件的配置页，填写 HA 地址、接口路径、长期访问令牌和时区。配置页不显示在 SP 侧边栏；任务界面顶部的“立即同步”按钮可独立触发推送。配置页通过插件消息桥将 Token 交给宿主侧 `plugin.js`，再保存到本地 Secret；它不会写入 SP 同步配置。更换公网入口主机名后需要重新打包安装插件。

限制和 `allowedHosts` 示例见 [`plugins/sp-ha-sync/README.md`](plugins/sp-ha-sync/README.md)。

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

通知标题放日期。正文不要直接使用预先拼好的 desp，而是像天气通知一样，用 groups 里的 overdue、today、week、unscheduled 自己写模板。分类名称、是否显示备注、空分类时的文案都可以改。完整示例在 [examples/daily_summary.yaml](examples/daily_summary.yaml)。

## 4. 不要提交的内容

Home Assistant 长期访问令牌保存在 Super Productivity 本机 Secret 中。不要把它写进 `manifest.json`、插件配置或说明文档。
