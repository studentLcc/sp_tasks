/// <reference types="@super-productivity/plugin-api/global" />

// SP 任务同步到 Home Assistant。
// 这是一个 host-side plugin，不能使用 import/export 或顶层 await。

const STORAGE_KEY = "sp-ha-sync.config";
const TOKEN_STORAGE_KEY = "sp-ha-sync.haToken";
const SECRET_KEY = "haToken";
const DEFAULT_CONFIG = {
  haUrl: "http://homeassistant.local:8123",
  haEndpoint: "/api/sp_tasks/tasks",
  timezone: "Asia/Shanghai",
};
const CATEGORY_TITLES = { overdue: "已过期", today: "今天", week: "一周内", unscheduled: "未安排" };
const CATEGORIES = ["overdue", "today", "week", "unscheduled"];

let config = { ...DEFAULT_CONFIG };
let debounceTimer = null;
let syncInFlight = false;
let syncPending = false;
let syncPendingReason = null;
let lastSignature = null;

function logError(message, error) {
  console.error("[sp-ha-sync]", message, error || "");
}

function readLocalConfig() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_CONFIG };
    const saved = JSON.parse(raw);
    return {
      ...DEFAULT_CONFIG,
      ...(saved && typeof saved === "object" ? saved : {}),
    };
  } catch (error) {
    logError("读取配置失败", error);
    return { ...DEFAULT_CONFIG };
  }
}

function saveLocalConfig(nextConfig) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(nextConfig));
}

async function getHaToken() {
  if (typeof PluginAPI.getSecret === "function") {
    try {
      const token = await PluginAPI.getSecret(SECRET_KEY);
      if (token) return token;
    } catch (error) {
      logError("SP Secret API 不可用，尝试读取本机插件存储", error);
    }
  }
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  } catch (error) {
    logError("读取本机 HA Token 失败", error);
    return "";
  }
}

function registerUiMessageHandler() {
  if (typeof PluginAPI.onMessage !== "function") return;
  PluginAPI.onMessage(async (message) => {
    if (!message || typeof message !== "object") return { ok: false, error: "invalid_message" };
    const type = message.type;
    const payload = message;
    try {
      if (type === "getHaTokenStatus") {
        return { ok: true, hasToken: !!(await getHaToken()) };
      }
      if (type === "setHaToken") {
        const token = typeof payload.token === "string" ? payload.token.trim() : "";
        if (!token) return { ok: false, error: "token_required" };
        if (typeof PluginAPI.setSecret !== "function") {
          return { ok: false, error: "secret_api_unavailable" };
        }
        await PluginAPI.setSecret(SECRET_KEY, token);
        try {
          localStorage.removeItem(TOKEN_STORAGE_KEY);
        } catch (_) {
          // Secret storage remains authoritative when local storage is unavailable.
        }
        return { ok: true, storage: "secret" };
      }
      if (type === "syncNow") {
        requestSync("manual");
        return { ok: true };
      }
      return { ok: false, error: "unknown_message" };
    } catch (error) {
      logError(`UI message failed: ${type}`, error);
      return { ok: false, error: error.message || String(error) };
    }
  });
}

async function loadConfig() {
  if (typeof PluginAPI.loadSyncedData === "function") {
    try {
      const raw = await PluginAPI.loadSyncedData();
      if (raw) {
        const saved = JSON.parse(raw);
        if (saved && typeof saved === "object") return { ...DEFAULT_CONFIG, ...saved };
      }
    } catch (error) {
      logError("读取同步配置失败", error);
    }
  }
  return readLocalConfig();
}

function moment(value) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return null;
  const timestamp = value < 100000000000 ? value * 1000 : value;
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? null : date;
}

function dateParts(date, timezone) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return { year: values.year, month: values.month, day: values.day };
}

function isoDate(date, timezone) {
  const parts = dateParts(date, timezone);
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function todayInTimezone(timezone) {
  return isoDate(new Date(), timezone);
}

function dateDistance(day, today) {
  const dayMs = Date.parse(`${day}T00:00:00Z`);
  const todayMs = Date.parse(`${today}T00:00:00Z`);
  return Math.round((dayMs - todayMs) / 86400000);
}

function schedulePoint(task, timezone) {
  const dueWithTime = moment(task.dueWithTime);
  if (dueWithTime) {
    const parts = dateParts(dueWithTime, timezone);
    const time = new Intl.DateTimeFormat("en-GB", {
      timeZone: timezone,
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(dueWithTime);
    return { day: `${parts.year}-${parts.month}-${parts.day}`, time };
  }
  if (typeof task.dueDay === "string" && /^\d{4}-\d{2}-\d{2}/.test(task.dueDay)) {
    return { day: task.dueDay.slice(0, 10), time: "" };
  }
  const plannedAt = moment(task.plannedAt);
  if (plannedAt) {
    const parts = dateParts(plannedAt, timezone);
    const time = new Intl.DateTimeFormat("en-GB", {
      timeZone: timezone,
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(plannedAt);
    return { day: `${parts.year}-${parts.month}-${parts.day}`, time };
  }
  return { day: null, time: "" };
}

function taskContent(value) {
  if (value === null || value === undefined) return "无";
  const text = String(value).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  return text || "无";
}

function classifyTasks(rawTasks, today, timezone) {
  const groups = { overdue: [], today: [], week: [], unscheduled: [] };
  for (const task of rawTasks) {
    if (!task || typeof task !== "object" || task.isDone) continue;
    const point = schedulePoint(task, timezone);
    if (!point.day) {
      groups.unscheduled.push({
        id: String(task.id || ""),
        title: String(task.title || "").trim() || "（无标题）",
        notes: taskContent(task.notes),
        schedule_day: null,
        schedule_time: "",
        category: "unscheduled",
        parent_id: task.parentId || null,
      });
      continue;
    }
    const delta = dateDistance(point.day, today);
    const category = delta < 0 ? "overdue" : delta === 0 ? "today" : delta <= 7 ? "week" : null;
    if (!category) continue;
    groups[category].push({
      id: String(task.id || ""),
      title: String(task.title || "").trim() || "（无标题）",
      notes: taskContent(task.notes),
      schedule_day: point.day,
      schedule_time: point.time,
      category,
      parent_id: task.parentId || null,
    });
  }
  for (const items of Object.values(groups)) {
    items.sort((a, b) =>
      `${a.schedule_day}|${a.schedule_time}|${a.title}`.localeCompare(
        `${b.schedule_day}|${b.schedule_time}|${b.title}`,
        "zh-Hans",
      ),
    );
  }
  return groups;
}

function renderMessage(groups) {
  const lines = [];
  for (const key of CATEGORIES) {
    const items = groups[key] || [];
    lines.push(`${CATEGORY_TITLES[key]}（${items.length}）`, "");
    if (!items.length) {
      lines.push("无", "");
      continue;
    }
    for (const item of items) {
      lines.push(`- ${item.title}`);
      if (item.schedule_time) lines.push(`  时间：${item.schedule_time}`);
      if (item.notes && item.notes !== "无") lines.push(`  内容：${item.notes}`);
      lines.push("");
    }
  }
  return lines.join("\n").trim();
}

function requestSync(reason) {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    syncNow(reason).catch((error) => logError("推送失败", error));
  }, reason === "startup" || reason === "manual" ? 0 : 750);
}

async function syncNow(reason) {
  if (syncInFlight) {
    syncPending = true;
    if (reason === "manual") syncPendingReason = "manual";
    return;
  }
  syncInFlight = true;
  try {
    const token = await getHaToken();
    if (!token) {
      PluginAPI.showSnack({ msg: "SP 任务同步尚未配置 HA Token，请到“设置 → 插件”打开本插件配置。", type: "WARNING" });
      return;
    }
    const rawTasks = await PluginAPI.getTasks();
    const tasksArray = Array.isArray(rawTasks) ? rawTasks : [];
    const today = todayInTimezone(config.timezone);
    const groups = classifyTasks(tasksArray, today, config.timezone);
    const tasks = CATEGORIES.flatMap((key) => groups[key]);
    const payload = {
      source: "super_productivity_plugin",
      date: today,
      synced_at: new Date().toISOString(),
      tasks,
      groups,
      message: renderMessage(groups),
    };
    const signature = JSON.stringify({ date: payload.date, tasks: payload.tasks, groups: payload.groups, message: payload.message });
    if (reason !== "startup" && reason !== "manual" && signature === lastSignature) return;
    const endpoint = new URL(config.haEndpoint, `${config.haUrl.replace(/\/$/, "")}/`).toString();
    await PluginAPI.request(endpoint, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: payload,
    });
    lastSignature = signature;
    PluginAPI.showSnack({ msg: `已推送 ${tasks.length} 个任务到 Home Assistant。`, type: "SUCCESS" });
  } catch (error) {
    logError("同步失败（请检查 URL、Token 及 manifest.allowedHosts）", error);
    const errorMessage = String(error.message || error);
    const privateNetworkBlocked = errorMessage.includes("Requests to private/local networks are not allowed");
    const message = privateNetworkBlocked
      ? "SP 安全策略禁止第三方插件直连局域网地址；allowedHosts 无法解除此限制。请使用带身份验证的 HTTPS 公网入口。"
      : `推送到 Home Assistant 失败：${errorMessage}`;
    PluginAPI.showSnack({ msg: message, type: "ERROR" });
  } finally {
    syncInFlight = false;
    if (syncPending) {
      const pendingReason = syncPendingReason || "pending";
      syncPending = false;
      syncPendingReason = null;
      requestSync(pendingReason);
    }
  }
}

function registerHooks() {
  const hooks = PluginAPI.Hooks;
  for (const hookName of ["DATA_CHANGED", "TASK_COMPLETE", "TASK_UPDATE", "TASK_DELETE", "DAY_CHANGE"]) {
    if (hooks && hooks[hookName]) PluginAPI.registerHook(hooks[hookName], () => requestSync(hookName));
  }
  if (hooks && hooks.PERSISTED_DATA_CHANGED) {
    PluginAPI.registerHook(hooks.PERSISTED_DATA_CHANGED, async () => {
      config = await loadConfig();
      requestSync("configuration");
    });
  }
}

PluginAPI.registerHeaderButton({
  label: "立即同步",
  icon: "cloud_upload",
  onClick: () => requestSync("manual"),
});

PluginAPI.registerConfigHandler(() => PluginAPI.showIndexHtmlAsView());
registerHooks();
registerUiMessageHandler();

const start = async () => {
  config = await loadConfig();
  requestSync("startup");
};

if (typeof PluginAPI.onReady === "function") PluginAPI.onReady(start);
else start();

if (typeof PluginAPI.onUnload === "function") {
  PluginAPI.onUnload(() => {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  });
}
