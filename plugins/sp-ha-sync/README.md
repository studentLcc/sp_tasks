# SP 任务同步到 Home Assistant

这个目录是独立的 Super Productivity 插件。它在启动时推送一次，并在 `dataChanged`、任务完成、任务更新、任务删除和逻辑日期变化后，通过 750 毫秒防抖再推送一次。

推送未完成任务：有日期的任务按“已过期、今天、一周内”分组，没有计划日期的任务归入“未安排”；超过一周的有日期任务不推送。插件直接调用 Home Assistant 集成的 `/api/sp_tasks/tasks`，因此 HAOS 端仍需安装 `custom_components/sp_tasks`。

## 安装

1. 这个插件调用 SP 的 `PluginAPI.request`。第三方插件不能向局域网或本机地址发请求；把 `192.168.x.x`、`10.x.x.x`、`homeassistant.local` 等地址加入 `allowedHosts` 也不能解除该限制。HA 需要通过一个 SP 可访问、带身份验证和访问控制的 HTTPS 公网入口提供服务。

   将该入口的精确主机名加入 `manifest.json` 的 `allowedHosts` 和 `dataSharing[0].hosts`，不要写协议、端口或路径。例如：

   ```json
   "allowedHosts": ["ha.example.com"],
   "dataSharing": [{
     "recipient": "由用户配置的 Home Assistant",
     "hosts": ["ha.example.com"],
     "userServer": true,
     "data": ["credentials", "taskTitles", "taskNotes", "taskSchedule", "taskStatus", "ids"]
   }]
   ```

2. 在本目录运行：

   ```bash
   ./package.sh
   ```

3. 在 Super Productivity 中打开 `Settings → Plugins → Choose Plugin File`，选择生成的 `sp-ha-sync.zip`。

4. 安装后在“设置 → 插件”中打开此插件的配置页，填写 HA 地址、接口路径、长期访问令牌和时区。表单通过 SP 插件消息桥把 Token 交给宿主侧 `plugin.js`，再存入本地 Secret；Token 不会写入 SP 同步配置，地址、接口路径和时区保存在插件配置中。任务界面顶部的“立即同步”按钮可独立触发推送。

更换入口主机名后需要重新打包安装插件。

## 约束

- `PluginAPI.request` 会检查插件权限和 `allowedHosts`，并额外拒绝私有/本机网络。该插件只能连接公网主机。
- Super Productivity 的 `dataChanged` 会覆盖远程同步和批量操作。插件会比较快照，只有任务数据实际变化时才发请求。
- 当前插件依赖 Super Productivity 19.3.0 或更高版本。实际安装时请使用与你的 SP 版本匹配的插件 API。
