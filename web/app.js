const $ = (selector) => document.querySelector(selector);
let csrf = null;
let refreshTimer;
let refreshing = false;

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
  $("#session-label").textContent = authed ? "Управление доступно" : "Только просмотр";
  $("#login-open").classList.toggle("hidden", authed);
  $("#logout").classList.toggle("hidden", !authed);
  document.querySelectorAll(".control").forEach(button => button.disabled = !authed);
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

function updateDecision(release) {
  const decision=release.last_decision || {};
  $("#decision-state").textContent=decision.reason || decision.state || "Не проверено";
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
  } catch (error) { $("#updated-at").textContent=`Панель недоступна: ${error.message}`; $("#health-dot").className="status-dot bad"; }
  finally { refreshing = false; }
}

async function control(path, data = {}) {
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
  }
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
