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
      (f) => f.evidence.source === "scenario://architecture/decision-x-v41",
    ),
    state.facts.some(
      (f) => f.evidence.source === "scenario://architecture/evidence-y-v42",
    ),
    state.replacements.some(
      (e) =>
        state.facts.find((f) => f.id === e.old_id)?.evidence.source ===
        "scenario://architecture/decision-x-v41",
    ),
  ];
  document.querySelectorAll("[data-step]").forEach((b, i) => {
    b.classList.toggle("done", stages[i]);
    b.querySelector(".step-mark").textContent = stages[i] ? "✓" : "↗";
  });
  renderGate();
  renderGraph();
  renderAnswer();
  renderInspector();
  renderEvents();
  renderJourney();
}
function renderJourney() {
  const currentTitle = document.querySelector(
    ".journey-label-now strong",
  );
  const currentLabel = $("journey-current");
  const currentPoint = document.querySelector(
    ".journey-label-now",
  );

  if (!currentTitle || !currentLabel || !currentPoint) {
    return;
  }

  const oldFact = state.facts.find(
    (f) =>
      f.evidence.source ===
      "scenario://architecture/decision-x-v41",
  );

  const newFact = state.facts.find(
    (f) =>
      f.evidence.source ===
      "scenario://architecture/evidence-y-v42",
  );

  const replacement =
    oldFact && newFact
      ? state.replacements.find(
          (edge) =>
            edge.old_id === oldFact.id &&
            edge.new_id === newFact.id &&
            edge.recorded_at <= state.known_at,
        )
      : null;

  currentPoint.classList.remove(
    "journey-conflict",
    "journey-current",
  );

  if (replacement) {
    currentTitle.textContent = "Текущее решение";
    currentLabel.textContent = "Architecture Y · current";
    currentPoint.classList.add("journey-current");
  } else if (
    newFact &&
    state.answer_status === "conflict"
  ) {
    currentTitle.textContent = "Новое evidence";
    currentLabel.textContent = "Architecture Y · конфликт";
    currentPoint.classList.add("journey-conflict");
  } else {
    currentTitle.textContent = "Текущее состояние?";
    currentLabel.textContent = "пока неизвестно";
  }
}

function renderGate() {
  const gate = $("pr-gate");
  const selected = state.facts.filter((f) => f.selected);
  const current = selected.length === 1 ? selected[0].value : null;

  let style = "review";
  let status = "НУЖНЫ ОСНОВАНИЯ";
  let reason = "Память ещё не знает, какое решение действует сейчас.";

  if (state.answer_status === "conflict") {
    style = "blocked";
    status = "STATE CONFLICT";
    reason =
      "Architecture X и Architecture Y одновременно претендуют на текущее состояние проекта.";
  } else if (current === "Architecture Y") {
    style = "blocked";
    status = "STALE CONFIGURATION";
    reason =
      'Текущее решение — Architecture Y, а агент всё ещё предлагает Architecture X.';
  } else if (current === "Architecture X" && state.at < 42) {
    style = "historical";
    status = `VALID IN V${state.at}`;
    reason =
      "В этом историческом состоянии Architecture X действительно была актуальным решением.";
  } else if (current === "Architecture X") {
    status = "KNOWN STATE: ARCHITECTURE X";
    reason =
      "Пока память знает только Architecture X. Это не доказывает, что более нового решения нет.";
  }

  gate.className = `card pr-gate ${style}`;
  $("gate-status").textContent = status;
  $("gate-reason").textContent = reason;
}

function renderGraph() {
  const oldFact = state.facts.find(
    (f) =>
      f.evidence.source ===
      "scenario://architecture/decision-x-v41",
  );

  const newFact = state.facts.find(
    (f) =>
      f.evidence.source ===
      "scenario://architecture/evidence-y-v42",
  );

  const replacement =
    oldFact && newFact
      ? state.replacements.find(
          (edge) =>
            edge.old_id === oldFact.id &&
            edge.new_id === newFact.id &&
            edge.recorded_at <= state.known_at,
        )
      : null;

  const knownReplacementCount =
    state.replacements.filter(
      (edge) => edge.recorded_at <= state.known_at,
    ).length;

  $("graph-count").textContent =
    `${state.facts.length} утверждений · ` +
    `${knownReplacementCount} известных связей изменения`;

  const bindClicks = () => {
    $("graph")
      .querySelectorAll("[data-fact]")
      .forEach((button) => {
        button.onclick = () => {
          focusId = button.dataset.fact;
          renderGraph();
          renderInspector();
        };
      });
  };

  // Guided architecture scenario.
  if (state.query.entity === "project.architecture") {
    if (!oldFact && !newFact) {
      $("graph").innerHTML = `
        <div class="decision-empty">
          <div class="decision-empty-number">01</div>
          <strong>Начните с предыдущего решения</strong>
          <p>
            Нажмите шаг 1 слева.
            Мы сначала увидим только то,
            что уже находится в памяти агента.
          </p>
        </div>`;
      return;
    }

    const oldConflict =
      oldFact && oldFact.conflicting;

    const newConflict =
      newFact && newFact.conflicting;

    const oldClass = replacement
      ? "historical"
      : oldConflict
        ? "conflict"
        : "known";

    const newClass = replacement
      ? "current"
      : newConflict
        ? "conflict"
        : "new-evidence";

    const oldBadge = replacement
      ? "HISTORICAL"
      : oldConflict
        ? "ACTIVE CLAIM"
        : "KNOWN";

    const newBadge = replacement
      ? "CURRENT"
      : newConflict
        ? "ACTIVE CLAIM"
        : "NEW EVIDENCE";

    const card = (
      fact,
      role,
      visualClass,
      badge,
    ) => {
      if (!fact) {
        return `
          <div class="decision-card decision-placeholder">
            <div class="decision-card-head">
              <span>V42</span>
              <em>СЛЕДУЮЩИЙ ШАГ</em>
            </div>

            <strong>Architecture Y</strong>

            <p>
              Новое evidence появится здесь
              после шага 2.
            </p>
          </div>`;
      }

      return `
        <button
          type="button"
          class="
            decision-card
            ${visualClass}
            ${focusId === fact.id ? "focused" : ""}
          "
          data-fact="${fact.id}"
        >
          <div class="decision-card-head">
            <span>
              ${role === "old" ? "V41" : "V42"}
            </span>
            <em>${badge}</em>
          </div>

          <div class="decision-card-body">
            <div class="decision-card-type">
              ${
                role === "old"
                  ? "Предыдущее решение"
                  : "Более позднее evidence"
              }
            </div>

            <strong>${escape(fact.value)}</strong>

            <p>${escape(fact.evidence.agent)}</p>
          </div>

          <div class="decision-card-foot">
            <span>
              ${
                role === "old"
                  ? "ADR-001"
                  : "ADR-002"
              }
            </span>

            <span>
              V${fact.valid_from ?? "?"}
              →
              ${
                fact.effective_to == null
                  ? "∞"
                  : `V${fact.effective_to}`
              }
            </span>
          </div>
        </button>`;
    };

    let bridge;

    if (!newFact) {
      bridge = `
        <div class="decision-bridge waiting">
          <span>Позже появляется</span>
          <strong>→</strong>
          <small>новое evidence</small>
        </div>`;
    } else if (
      state.answer_status === "conflict" &&
      !replacement
    ) {
      bridge = `
        <div class="decision-bridge conflict">
          <span>STATE CONFLICT</span>
          <strong>↔</strong>
          <small>
            оба утверждения пока активны
          </small>
        </div>`;
    } else if (replacement) {
      bridge = `
        <div class="decision-bridge resolved">
          <span>SUPERSEDED</span>
          <strong>→</strong>
          <small>
            изменение подтверждено с V${replacement.effective}
          </small>
        </div>`;
    } else {
      bridge = `
        <div class="decision-bridge waiting">
          <span>Новое evidence</span>
          <strong>→</strong>
        </div>`;
    }

    let explanation = "";

    if (
      state.answer_status === "conflict" &&
      !replacement
    ) {
      explanation = `
        <div class="decision-message conflict">
          <strong>Конфликт состояния.</strong>
          Новое evidence не получает приоритет
          только потому, что оно новее.
          Система ждёт явного подтверждения изменения.
        </div>`;
    }

    if (replacement) {
      explanation = `
        <div class="decision-message resolved">
          <strong>Изменение состояния подтверждено.</strong>
          Architecture X остаётся в истории,
          Architecture Y становится текущим решением.
        </div>`;
    }

    $("graph").innerHTML = `
      <div class="decision-flow">
        ${card(
          oldFact,
          "old",
          oldClass,
          oldBadge,
        )}

        ${bridge}

        ${card(
          newFact,
          "new",
          newClass,
          newBadge,
        )}
      </div>

      ${explanation}
    `;

    bindClicks();
    return;
  }

  // Generic fallback for custom experiments.
  if (!state.facts.length) {
    $("graph").innerHTML =
      '<div class="empty">' +
      '<strong>Нет подходящих утверждений</strong>' +
      'Добавьте факт или измените запрос.' +
      "</div>";
    return;
  }

  $("graph").innerHTML = state.facts
    .map(
      (fact) => `
        <button
          class="generic-memory-card"
          data-fact="${fact.id}"
          type="button"
        >
          <strong>${escape(fact.value)}</strong>
          <span>${escape(fact.evidence.agent)}</span>
          <small>
            V${fact.valid_from ?? "?"}
            →
            ${
              fact.effective_to == null
                ? "∞"
                : `V${fact.effective_to}`
            }
          </small>
        </button>`,
    )
    .join("");

  bindClicks();
}

function renderAnswer() {
  const selected = state.facts.filter((f) => f.selected);
  const excluded = state.facts.length - selected.length;
  const values = selected.map(
    (f) => `${f.negated ? "НЕ " : ""}${escape(f.value)}`,
  );

  let title;
  let body;

  if (state.answer_status === "conflict") {
    title = "Какое решение текущее — пока неясно";
    body = `
      <p>Память содержит два несовместимых состояния одного проекта.</p>
      <div class="answer-value">${values.join(" / ")}</div>
      <p>
        Более новое evidence не перезаписывает прошлое автоматически.
        Пока переход не подтверждён, конфликт остаётся явным.
      </p>`;
  } else if (state.answer_status === "supported") {
    const current = selected.length === 1 ? selected[0].value : null;

    if (current === "Architecture Y") {
      title = "Текущее состояние: Architecture Y";
      body = `
        <div class="answer-value">Architecture Y</div>
        <p>
          Миграция подтверждена с V42. Architecture X не удалён:
          он остаётся в памяти как исторически верное состояние.
        </p>`;
    } else if (current === "Architecture X" && state.at < 42) {
      title = "Историческое состояние: Architecture X";
      body = `
        <div class="answer-value">Architecture X</div>
        <p>
          В снимке мира V${state.at} это состояние действительно было актуальным.
          Более поздняя миграция не переписывает прошлое.
        </p>`;
    } else {
      title = "Пока известно только Architecture X";
      body = `
        <div class="answer-value">Architecture X</div>
        <p>
          Это единственное состояние, известное памяти к K${state.known}.
          Оно подтверждено имеющимся evidence, но не доказывает,
          что более нового состояния не существует.
        </p>`;
    }
  } else {
    title = "Текущее состояние пока неизвестно";
    body = `
      <p>
        Для выбранного снимка мира и cutoff знаний нет подходящего утверждения.
        Отсутствие сведений не означает, что другое состояние ложно.
      </p>`;
  }

  $("answer").className = `card answer ${state.answer_status}`;
  $("answer").innerHTML =
    `<div class="section-label">ПОЧЕМУ ПАМЯТЬ ТАК СЧИТАЕТ? <span>V${state.at} · K${state.known}</span></div>` +
    `<h2 class="answer-title">${title}</h2>` +
    body +
    `<ol>` +
    `<li>Проверены объект, свойство и окружение.</li>` +
    `<li>Учтено только то, что было известно к K${state.known}; утверждение должно действовать в V${state.at}.</li>` +
    `<li>${selected.length} утверждений выбрано, ${excluded} исключено. Текущих конфликтов: ${state.conflicts.length}.</li>` +
    `</ol>` +
    `<div class="stats">` +
    `<span>${state.latency_ms.toFixed(2)} ms</span>` +
    `<span>${state.cache_hit ? "CACHE HIT" : "LIVE QUERY"}</span>` +
    `<span>REV ${state.revision}</span>` +
    `<span>LLM CALLS: 0</span>` +
    `</div>`;
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
