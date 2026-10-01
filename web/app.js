const $ = (selector) => document.querySelector(selector);
let csrf = null;
let refreshTimer;
let refreshing = false;
let authenticated = false;
let lastOverview = null;
let controlBusy = false;

function time(value) {
  if (!value) return "—";
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  return Number.isNaN(date.valueOf()) ? "—" : new Intl.DateTimeFormat("ru-RU", {dateStyle:"short", timeStyle:"medium"}).format(date);
}

function toast(message, error = false) {
  const node = $("#toast");
  node.textContent = message;
  node.style.background = error ? "#762d2b" : "#242521";
  node.classList.add("visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.remove("visible"), 4000);
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.method === "POST") {
    headers.set("Content-Type", "application/json");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  const timeout = options.method === "POST" ? 120000 : 10000;
  const response = await fetch(path, {...options, headers, credentials:"same-origin", signal:AbortSignal.timeout(timeout)});
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) { csrf = null; sessionView(false); }
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return payload;
}

function sessionView(authed) {
  authenticated = authed;
  $("#session-label").textContent = authed ? "Управление доступно" : "Только просмотр";
  $("#login-open").classList.toggle("hidden", authed);
  $("#logout").classList.toggle("hidden", !authed);
  applyReleaseControls();
}

function statusClass(status) {
  if (["succeeded", "available", "completed", "rolled-back", "stable"].includes(status)) return "available";
  if (["failed", "rollback-failed", "interrupted", "reconcile-required", "unavailable"].includes(status)) return "failed";
  return "";
}

function renderChart(metrics) {
  const root = $("#request-chart");
  root.replaceChildren();
  if (metrics.status !== "available") {
    const p = document.createElement("p"); p.className = "muted"; p.textContent = `Метрики недоступны: ${metrics.error || "ожидание Prometheus"}`; root.append(p); return;
  }
  const rows = metrics.series?.requests || [];
  const values = rows.map(row => ({version:row.metric.version || "?", status:row.metric.status || "?", count:Number(row.value[1])}));
  const max = Math.max(1, ...values.map(row => row.count));
  if (!values.length) { const p = document.createElement("p"); p.className="muted"; p.textContent="Prometheus пока не вернул samples запросов"; root.append(p); return; }
  for (const row of values) {
    const line = document.createElement("div"); line.className="chart-row";
    const label=document.createElement("span"); label.textContent=`${row.version} · ${row.status}`;
    const track=document.createElement("span"); track.className="bar-track";
    const bar=document.createElement("span"); bar.className=`bar${row.status.startsWith("5")?" error":""}`;
    bar.style.width=`${Math.max(1, row.count / max * 100)}%`; track.append(bar);
    const count=document.createElement("strong"); count.className="mono"; count.textContent=String(Math.round(row.count));
    line.append(label,track,count); root.append(line);
  }
}

function fillTable(selector, rows, columns, emptyText) {
  const body=$(selector); body.replaceChildren();
  if (!rows?.length) { const tr=document.createElement("tr"), td=document.createElement("td"); td.colSpan=columns.length; td.className="muted"; td.textContent=emptyText; tr.append(td); body.append(tr); return; }
  for (const row of rows) {
    const tr=document.createElement("tr");
    for (const [key, type] of columns) {
      const td=document.createElement("td");
      if (type === "state") { const span=document.createElement("span"); span.className=`state ${statusClass(row[key])}`; span.textContent=row[key] || "—"; td.append(span); }
      else { td.textContent=type === "time" ? time(row[key]) : type === "json" ? JSON.stringify(row[key] || {}) : String(row[key] ?? "—"); }
      tr.append(td);
    }
    body.append(tr);
  }
}

function releaseAvailability(release, policy, authed, busy, now = Date.now()/1000) {
  const enabled = authed && !busy;
  const decision = release?.last_decision || {};
  const fresh = Number.isFinite(decision.sample_time) && decision.sample_time <= now+5
    && now-decision.sample_time <= (policy?.max_sample_age_seconds ?? 30);
  return {
    start: enabled && !!release && !release.reconcile_required
      && !["canary", "completed", "reconcile-required"].includes(release.status),
    advance: enabled && release?.status === "canary" && !release.reconcile_required
      && fresh && decision.state === "observe" && Number.isFinite(decision.error_ratio)
      && decision.error_ratio <= (policy?.error_threshold ?? 0.05),
    rollback: enabled,
  };
}

function applyReleaseControls() {
  document.querySelectorAll(".control").forEach(button => button.disabled = !authenticated || controlBusy);
  const allowed = releaseAvailability(lastOverview?.release, lastOverview?.policy, authenticated, controlBusy);
  $('[data-action="/api/release/start"]').disabled = !allowed.start;
  $("#apply-weight").disabled = !allowed.advance;
  $('[data-action="/api/release/complete"]').disabled = !allowed.advance;
  $('[data-action="/api/release/rollback"]').disabled = !allowed.rollback;
  const active = lastOverview?.release?.status === "canary";
  const policy = lastOverview?.policy || {};
  $("#release-help").textContent = !authenticated ? "Войдите для управления релизами." : controlBusy
    ? "Дождитесь завершения текущей операции."
    : active && !allowed.advance
      ? `Canary уже активен. Запустите трафик 10 запросов/с на 120 секунд. Для смены доли нужны полное окно ${policy.window_seconds ?? 60} с, минимум ${policy.min_requests ?? 30} запросов v2 и свежие безопасные метрики. Ручной откат доступен без метрик.`
      : active ? "Метрики безопасны: можно применить долю или завершить релиз, пока трафик продолжается."
      : lastOverview?.release?.status === "completed" ? "Релиз v2 завершён. Для нового canary сначала откатите на v1."
      : "Запустите непрерывный трафик, затем начните canary. Ручной откат возвращает трафик на v1.";
}

function decisionText(reason) {
  return ({
    "insufficient or invalid v2 requests": "Недостаточно запросов v2 в текущем окне",
    "canary window is not complete": "Ожидание полного окна canary",
    "waiting for a complete fresh window": "Ожидание полного свежего окна",
    "within error threshold": "Доля ошибок в пределах порога",
    "5xx threshold exceeded": "Превышен порог ошибок 5xx",
    "v2 target is down": "Prometheus не видит доступный target v2",
    "source sample is stale or outside this canary": "Метрики устарели или получены до текущего canary",
  })[reason] || reason;
}

function updateDecision(release) {
  const decision=release.last_decision || {};
  $("#decision-state").textContent=decisionText(decision.reason) || decision.state || "Не проверено";
  $("#decision-requests").textContent=decision.requests ?? "—";
  $("#decision-errors").textContent=Number.isFinite(decision.error_ratio) ? `${(decision.error_ratio*100).toFixed(2)}%` : "—";
  $("#decision-time").textContent=time(decision.sample_time);
  $("#decision-breaches").textContent=decision.breaches ?? release.breaches ?? "—";
  $("#canary-status").textContent=release.reconcile_required ? "Требуется сверка маршрута" : release.status || "—";
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const [overview, operations, logData] = await Promise.all([
      api("/api/overview"), api("/api/operations"), api(`/api/logs?limit=50${$("#log-marker").value ? `&marker=${encodeURIComponent($("#log-marker").value)}` : ""}`)
    ]);
    const services=overview.services || {}, release=overview.release || {}, metrics=overview.metrics || {};
    lastOverview = overview;
    applyReleaseControls();
    $("#updated-at").textContent=`Обновлено ${time(overview.updated_at)}`;
    $("#health-dot").className=`status-dot ${services.status === "available" && metrics.status === "available" ? "ok" : "bad"}`;
    $("#release-state").textContent=release.status || "—";
    $("#release-reason").textContent=release.reason || release.last_decision?.reason || "—";
    $("#weights").textContent=services.weights ? `v1 ${services.weights.v1}% · v2 ${services.weights.v2}%` : "Недоступно";
    $("#route-state").textContent=services.error || `HTTPRoute · ${time(services.updated_at)}`;
    const deployments=services.deployments || [];
    $("#pods").textContent=deployments.length ? deployments.map(item=>`${item.name.replace("demo-","")} ${item.ready}/${item.desired}`).join(" · ") : "Недоступно";
    $("#pods-updated").textContent=services.error || `Срез ${time(services.updated_at)}`;
    $("#metrics-state").textContent=metrics.status === "available" ? "Доступны" : "Неизвестно";
    $("#metrics-time").textContent=metrics.latest_sample_time ? `Source sample ${time(metrics.latest_sample_time)}` : metrics.error || "Нет source sample";
    const errorRate=(metrics.series?.error_rate || []).find(row=>row.metric.version === "v2");
    const latency=(metrics.series?.latency_p95 || []).find(row=>row.metric.version === "v2");
    $("#error-rate").textContent=metrics.status === "available" && errorRate ? `${(Number(errorRate.value[1])*100).toFixed(2)}%` : "Неизвестно";
    $("#error-rate-time").textContent=errorRate?.sample_time ? `Sample ${time(errorRate.sample_time)}` : "Нет свежего ряда";
    $("#latency-p95").textContent=metrics.status === "available" && latency ? `${(Number(latency.value[1])*1000).toFixed(1)} ms` : "Неизвестно";
    $("#latency-time").textContent=latency?.sample_time ? `Sample ${time(latency.sample_time)}` : "Нет свежего ряда";
    $("#traffic-time").textContent=`${overview.traffic?.status || "idle"} · ${overview.traffic?.sent || 0} запросов`;
    $("#chart-time").textContent=metrics.latest_sample_time ? time(metrics.latest_sample_time) : "—";
    renderChart(metrics); updateDecision(release);
    $("#logs-time").textContent=`${logData.status || "unavailable"} · ${time(logData.updated_at)}`;
    fillTable("#logs-body", logData.entries, [["event","text"],["cri_time","time"],["version","text"],["status","text"],["request_id","text"],["path","text"]], logData.error || "В Fluentd пока нет подходящих записей");
    fillTable("#operations-body", operations.operations, [["kind","text"],["created","time"],["status","state"],["reason","text"],["details","json"]], "Журнал пока пуст");
    $("#operations-time").textContent=time(operations.updated_at);
    const traffic=overview.traffic || {};
    $("#traffic-feedback").textContent=traffic.status === "running" ? `Идёт серия ${traffic.run_id}: ${traffic.sent}/${traffic.rate*traffic.duration}, ошибок ${traffic.failed}.` : `Последняя серия: ${traffic.status || "idle"}; отправлено ${traffic.sent || 0}, ошибок ${traffic.failed || 0}.`;
    $("#traffic-feedback").className=`feedback ${traffic.failed ? "error" : ""}`;
  } catch (error) { lastOverview=null; applyReleaseControls(); $("#updated-at").textContent=`Панель недоступна: ${error.message}`; $("#health-dot").className="status-dot bad"; }
  finally { refreshing = false; }
}

async function control(path, data = {}) {
  if (controlBusy) return;
  controlBusy = true;
  applyReleaseControls();
  const feedback = path.includes("incident") ? $("#incident-feedback") : $("#release-feedback");
  if (feedback) { feedback.textContent="Действие выполняется…"; feedback.className="feedback"; }
  try {
    const result=await api(path,{method:"POST",body:JSON.stringify(data)});
    if (feedback) { feedback.textContent=`${result.status || "Готово"} · ${result.reason || result.confirmed_version || "результат записан в журнал"}`; feedback.className="feedback success"; }
    toast("Операция завершена"); await refresh(); return result;
  } catch(error) {
    const message = error.name === "TimeoutError" ? "Ответ задерживается; проверьте результат в журнале операций." : error.message;
    if(feedback){feedback.textContent=message;feedback.className="feedback error";}
    toast(message,true); refresh(); throw error;
  } finally { controlBusy = false; applyReleaseControls(); }
}

$("#login-open").addEventListener("click",()=>$("#login-dialog").showModal());
$("#login-close").addEventListener("click",()=>$("#login-dialog").close());
$("#login-form").addEventListener("submit",async event=>{
  event.preventDefault(); const password=new FormData(event.currentTarget).get("password");
  try { const result=await api("/api/login",{method:"POST",body:JSON.stringify({password})}); csrf=result.csrf; sessionView(true); $("#login-dialog").close(); event.currentTarget.reset(); await refresh(); }
  catch(error){$("#login-error").textContent=error.message;}
});
$("#logout").addEventListener("click",async()=>{try{await api("/api/logout",{method:"POST",body:"{}"});}catch(_){}csrf=null;sessionView(false);toast("Сессия завершена");});
$("#traffic-form").addEventListener("submit",async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.currentTarget));data.rate=Number(data.rate);data.duration=Number(data.duration);await control("/api/traffic/start",data).catch(()=>{});});
$("#traffic-stop").addEventListener("click",()=>control("/api/traffic/stop").catch(()=>{}));
document.querySelectorAll("[data-action]").forEach(button=>button.addEventListener("click",()=>control(button.dataset.action,button.dataset.json?JSON.parse(button.dataset.json):{}).catch(()=>{})));
$("#apply-weight").addEventListener("click",()=>control("/api/release/weight",{percent:Number($("#weight").value)}).catch(()=>{}));
$("#weight").addEventListener("input",event=>$("#weight-value").value=`${event.target.value}%`);
$("#log-search").addEventListener("submit",event=>{event.preventDefault();refresh();});

api("/api/session").then(result=>{csrf=result.csrf;sessionView(result.authenticated);}).catch(()=>sessionView(false));
refresh(); refreshTimer=setInterval(refresh,5000);
