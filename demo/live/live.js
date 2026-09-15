"use strict";
const $ = (id) => document.getElementById(id);
const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const short = (id) => id.slice(0, 7);
const reasons = {
  active: "Действует в выбранной версии",
  superseded: "Заменён новым утверждением",
  expired: "Интервал действия закончился",
  not_yet_valid: "Ещё не действует",
  unknown_validity: "Неизвестен интервал действия",
  not_known: "Ещё не поступил в память",
  different_environment: "Другое окружение",
  different_entity: "Другой объект",
  different_predicate: "Другое свойство",
};
let state = null,
  focusId = null,
  busy = false;
function coordinates() {
  return {
    room: state?.room,
    entity: $("query-entity").value,
    predicate: $("query-predicate").value,
    environment: $("query-environment").value,
    at: Number($("valid-at").value),
    known: Number($("known-at").value),
  };
}
async function request(action, payload) {
  if (busy) return;
  busy = true;
  $("error").hidden = true;
  document.querySelectorAll("button").forEach((b) => (b.disabled = true));
  try {
    const res = await fetch(`/api/live/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Ошибка записи");
    state = data;
    const url = new URL(location.href);
    url.searchParams.set("room", state.room);
    history.replaceState(null, "", url);
    if (focusId && !state.facts.some((f) => f.id === focusId)) focusId = null;
    render();
  } catch (error) {
    $("error").textContent = error.message;
    $("error").hidden = false;
  } finally {
    busy = false;
    document.querySelectorAll("button").forEach((b) => (b.disabled = false));
  }
}
function render() {
  $("workspace-id").textContent = `SESSION / ${short(state.room)}`;
  $("query-entity").value = state.query.entity;
  $("query-predicate").value = state.query.predicate;
  $("query-environment").value = state.query.environment;
  $("valid-at").max = Math.max(
    3,
    state.at,
    ...state.facts.map((f) => f.valid_from ?? 0),
    ...state.facts.map((f) => f.valid_to ?? 0),
  );
  $("valid-at").value = state.at;
  $("valid-label").textContent = `V${state.at}`;
  $("known-at").max = state.events.length;
  $("known-at").value = state.known;
  $("known-label").textContent = `K${state.known} / ${state.events.length}`;
  $("known-caption").textContent = state.known
    ? `После события ${state.known} · ${new Date(state.known_at).toLocaleTimeString("ru-RU", { timeZone: "UTC" })} UTC`
    : "До поступления первого утверждения";
  const stages = [
    state.facts.some(
      (f) => f.evidence.source === "scenario://checkout/config-v0",
    ),
    state.facts.some(
      (f) => f.evidence.source === "scenario://checkout/release-v1",
    ),
    state.replacements.some(
      (e) =>
        state.facts.find((f) => f.id === e.old_id)?.evidence.source ===
        "scenario://checkout/config-v0",
    ),
  ];
  document.querySelectorAll("[data-step]").forEach((b, i) => {
    b.classList.toggle("done", stages[i]);
    b.querySelector(".step-mark").textContent = stages[i] ? "✓" : "↗";
  });
  renderGraph();
  renderAnswer();
  renderInspector();
  renderEvents();
}
function renderGraph() {
  $("graph-count").textContent =
    `${state.facts.length} утверждений · ${state.replacements.filter((e) => e.recorded_at <= state.known_at).length} известных связей замены`;
  if (!state.facts.length) {
    $("graph").innerHTML =
      '<div class="empty"><strong>У памяти пока нет оснований для ответа</strong>Начните с шага 1 слева или добавьте собственное утверждение.<br>Здесь появятся источники, факты и связи между ними.</div>';
    return;
  }
  let html = state.facts
    .map((f) => {
      const style = f.conflicting ? "conflict" : f.selected ? "" : "excluded";
      return `<div class="graph-line"><div class="source-node"><strong>${escape(f.evidence.agent)}</strong>источник утверждения</div><span class="connector"></span><button class="fact-node ${style} ${focusId === f.id ? "focus" : ""}" data-fact="${f.id}"><strong>${f.negated ? "НЕ " : ""}${escape(f.value)}</strong><small>${escape(f.entity)} · ${escape(f.predicate)}<br>V${f.valid_from ?? "?"} → ${f.effective_to == null ? "∞" : `V${f.effective_to}`} · ${escape(f.scope.environment)}</small></button><span class="connector"></span><div class="node-status ${style}">${f.conflicting ? "Противоречие" : f.selected ? "В ответе" : escape(reasons[f.status])}</div></div>`;
    })
    .join("");
  html += state.conflicts
    .map(
      (pair) =>
        `<div class="edge-note conflict">↔ Конфликт ${pair.ids.map(short).join(" / ")}: разные несовместимые утверждения, один объект и пересекающиеся интервалы.</div>`,
    )
    .join("");
  html += state.replacements
    .map(
      (e) =>
        `<div class="edge-note ${e.recorded_at > state.known_at ? "past" : ""}">↪ ${short(e.old_id)} → ${short(e.new_id)} · замена с V${e.effective}${e.recorded_at > state.known_at ? " · пока не известна в выбранном K" : " · исходный факт сохранён"}</div>`,
    )
    .join("");
  $("graph").innerHTML = html;
  $("graph")
    .querySelectorAll("[data-fact]")
    .forEach(
      (b) =>
        (b.onclick = () => {
          focusId = b.dataset.fact;
          renderGraph();
          renderInspector();
        }),
    );
}
function renderAnswer() {
  const selected = state.facts.filter((f) => f.selected);
  const excluded = state.facts.length - selected.length;
  let title, body;
  if (state.answer_status === "conflict") {
    title = "Нельзя выбрать одно значение";
    body = `<p>Память поддерживает несовместимые утверждения. Новизна записи сама по себе не делает её верной.</p><div class="answer-value">${selected.map((f) => `${f.negated ? "НЕ " : ""}${escape(f.value)}`).join(" / ")}</div><p>Уточните источник или подтвердите временную замену. Автоматического «последний победил» нет.</p>`;
  } else if (state.answer_status === "supported") {
    title = "Поддерживается памятью";
    body = `<div class="answer-value">${selected.map((f) => `${f.negated ? "НЕ " : ""}${escape(f.value)}`).join(" · ")}</div><p>Для ${escape(state.query.entity)}, ${escape(state.query.environment)}, в версии V${state.at}. Это вывод из записанных утверждений, не независимая проверка их истинности.</p>`;
  } else {
    title = "Недостаточно оснований";
    body =
      "<p>Нет подходящего утверждения с известным интервалом действия. Отсутствие сведений не означает, что факт ложен.</p>";
  }
  $("answer").className = `card answer ${state.answer_status}`;
  $("answer").innerHTML =
    `<div class="section-label">ОТВЕТ И ЕГО ОСНОВАНИЯ <span>V${state.at} · K${state.known}</span></div><h2 class="answer-title">${title}</h2>${body}<ol><li>Проверены объект, свойство и окружение.</li><li>Учтено только известное к K${state.known}; интервал должен содержать V${state.at}.</li><li>${selected.length} утверждений выбрано, ${excluded} исключено. ${state.conflicts.length} текущих конфликтов.</li></ol><div class="stats"><span>${state.latency_ms.toFixed(2)} ms</span><span>${state.cache_hit ? "CACHE HIT" : "LIVE QUERY"}</span><span>REV ${state.revision}</span><span>LLM CALLS: 0</span></div>`;
}
function renderInspector() {
  const fact = state.facts.find((f) => f.id === focusId);
  if (!fact) {
    $("inspector").innerHTML =
      '<div class="section-label">ИНСПЕКТОР ФАКТА</div><h2>Почему именно этот факт?</h2><p>Нажмите на узел карты. Здесь появятся источник, временные границы и проверяемая причина отбора.</p>';
    return;
  }
  const candidates = state.facts.filter(
    (f) =>
      f.id !== fact.id &&
      f.entity === fact.entity &&
      f.predicate === fact.predicate &&
      f.scope.environment === fact.scope.environment &&
      f.valid_from != null,
  );
  $("inspector").innerHTML =
    `<div class="section-label">ИНСПЕКТОР ФАКТА <span>${short(fact.id)}</span></div><h2>${fact.negated ? "НЕ " : ""}${escape(fact.value)}</h2><dl class="fact-detail"><dt>Решение правила</dt><dd>${escape(reasons[fact.status])}${fact.conflicting ? " · участвует в конфликте" : ""}</dd><dt>Интервал действия / время записи</dt><dd>[V${fact.valid_from ?? "?"}, ${fact.effective_to == null ? "∞" : `V${fact.effective_to}`})<br>${escape(fact.recorded_at)}</dd><dt>Источник · ${escape(fact.evidence.agent)}</dt><dd>${escape(fact.evidence.source)}</dd></dl><div class="evidence">${escape(fact.evidence.text)}</div><p class="micro-id">${fact.id}</p>${candidates.length ? `<details><summary>Подтвердить замену этого факта</summary><label>Новое утверждение<select id="replacement-target">${candidates.map((f) => `<option value="${f.id}">${escape(f.value)} · ${short(f.id)}</option>`).join("")}</select></label><label>С какой версии<input id="replacement-at" type="number" min="0" max="100" value="${state.at}"></label><p class="hint">Явное решение посетителя. Старый факт остаётся в истории; межконтекстные замены запрещены.</p><button id="confirm-replacement" class="primary">Подтвердить замену</button></details>` : ""}`;
  if ($("confirm-replacement"))
    $("confirm-replacement").onclick = () =>
      request("replace", {
        ...coordinates(),
        old_id: fact.id,
        new_id: $("replacement-target").value,
        effective: Number($("replacement-at").value),
      });
}
function renderEvents() {
  $("events").innerHTML = state.events.length
    ? state.events
        .map(
          (e, i) =>
            `<div class="event ${i >= state.known ? "future" : ""}"><span class="k-marker">K${i + 1}</span><div><strong>${e.kind === "assertion" ? `${escape(e.agent)}: ${escape(e.value)}` : "Подтверждена временная замена"}</strong><small>${e.kind === "assertion" ? escape(e.entity) : `${short(e.old_id)} → ${short(e.new_id)}, с V${e.effective}`} · ${new Date(e.recorded_at).toLocaleTimeString("ru-RU", { timeZone: "UTC" })} UTC</small></div><button data-known="${i + 1}">Вернуться сюда</button></div>`,
        )
        .join("")
    : '<p class="hint">Запишите первый факт. Каждая операция появится здесь с реальным временем поступления.</p>';
  $("events")
    .querySelectorAll("[data-known]")
    .forEach(
      (b) =>
        (b.onclick = () =>
          request("snapshot", {
            ...coordinates(),
            known: Number(b.dataset.known),
          })),
    );
}
document
  .querySelectorAll("[data-step]")
  .forEach(
    (b) =>
      (b.onclick = () =>
        request("step", { room: state?.room, step: Number(b.dataset.step) })),
  );
$("ask").onclick = () => request("snapshot", coordinates());
$("valid-at").oninput = () =>
  ($("valid-label").textContent = `V${$("valid-at").value}`);
$("known-at").oninput = () =>
  ($("known-label").textContent =
    `K${$("known-at").value} / ${state?.events.length ?? 0}`);
$("valid-at").onchange = $("known-at").onchange = () =>
  request("snapshot", coordinates());
$("new-room").onclick = () => request("create", {});
$("export").onclick = () => {
  if (!state) return;
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(state, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = `memory-trace-${short(state.room)}-K${state.known}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
$("fact-form").onsubmit = (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  request("save", {
    ...coordinates(),
    ...data,
    valid_from: data.valid_from === "" ? null : Number(data.valid_from),
    valid_to: data.valid_to === "" ? null : Number(data.valid_to),
    negated: event.target.elements.negated.checked,
  });
};
const existing = new URL(location.href).searchParams.get("room");
request(existing ? "snapshot" : "create", existing ? { room: existing } : {});
