# SP 任务同步到 Home Assistant

这个目录是独立的 Super Productivity 插件。它在启动时推送一次，并在 `dataChanged`、任务完成、任务更新、任务删除和逻辑日期变化后，通过 750 毫秒防抖再推送一次。

推送范围是未完成且有计划日期的任务，按“已过期、今天、一周内”分组。插件直接调用 Home Assistant 集成的 `/api/sp_tasks/tasks`，因此 HAOS 端仍需安装 `custom_components/sp_tasks`。

## 安装

1. 这个插件调用 SP 的 `PluginAPI.request`。上传安装的插件不能向局域网或本机地址发请求；把 `192.168.x.x`、`10.x.x.x`、`homeassistant.local` 等地址加入 `allowedHosts` 也不能解除该限制。上传插件要直连 HA，需要一个 SP 可访问的 HTTPS 公网入口，并做好身份验证和访问控制。HA 只在局域网时，按仓库中的 [`docs/super-productivity-fork-workflow.md`](../../docs/super-productivity-fork-workflow.md) 安装内置插件。

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

4. 安装后打开插件菜单中的“配置 SP → Home Assistant 同步”，或打开插件侧栏，填写 HA 地址、接口路径、长期访问令牌和时区。表单通过 SP 插件消息桥把 Token 交给宿主侧 `plugin.js`，再存入本地 Secret；Token 不会写入 SP 同步配置，地址、接口路径和时区保存在插件配置中。

仅更改 `.local` 主机名，或把局域网 IP 加进白名单，不能让上传插件访问局域网 HA。

## 约束

- `PluginAPI.request` 会检查插件权限和 `allowedHosts`，并额外拒绝私有/本机网络。普通上传插件没有启用内网访问的 manifest 开关。内网例外只存在于按 fork 流程打进 SP 的内置 `sp-ha-sync`。
- Super Productivity 的 `dataChanged` 会覆盖远程同步和批量操作。插件会比较快照，只有任务数据实际变化时才发请求。
- 当前插件依赖 Super Productivity 19.3.0 或更高版本。实际安装时请使用与你的 SP 版本匹配的插件 API。
