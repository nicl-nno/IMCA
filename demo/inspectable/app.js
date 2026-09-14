"use strict";
const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const short = (id) => String(id).split("/").at(-1);
const labels = {
  structural_order: "Порядок графа",
  bm25: "Лексический поиск",
  edge_frequency: "Частота связи",
  graph_degree: "Степень узла",
  id_overlap: "Совпадение ID",
};
const stageLabels = {
  candidate_missing: "Не попал в кандидаты",
  ranking_loss: "Потерян при top-5",
  ranking_position_loss: "Неверная позиция в выдаче",
  reader_drop: "Исключён Luna",
  retrieved: "Найден",
};
const statuses = {
  active: "Действует",
  superseded: "Заменён",
  expired: "Истёк",
  not_yet_valid: "Ещё не действует",
  unknown_validity: "Время неизвестно",
};
const diagnoses = {
  conflict: "Противоречие",
  version_change: "Смена версии, не конфликт",
  different_scope: "Разные условия",
  unknown_validity: "Недостаточно временных данных",
};
let catalog, current;
const history = [];
const parents = new Map();

async function api(path, body) {
  $("error").hidden = true;
  const response = await fetch(
    path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Ошибка запроса");
  return data;
}
function fail(error) {
  $("error").textContent = error.message;
  $("error").hidden = false;
}
function metric(value, label) {
  return `<div class="metric"><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`;
}
function badge(text, type = "") {
  return `<span class="badge ${type}">${esc(text)}</span>`;
}
function setView(view) {
  for (const name of ["retrieval", "temporal"]) {
    $(`${name}-view`).hidden = name !== view;
    $(`${name}-tab`).classList.toggle("active", name === view);
    $(`${name}-tab`).setAttribute("aria-pressed", String(name === view));
  }
}
function remember(run) {
  current = run;
  parents.set(run.case_id, run.run_id);
  history.unshift(run);
  if (history.length > 20) history.pop();
  $("history").innerHTML = history
    .map(
      (item, i) =>
        `<div class="history-entry"><button data-history="${i}">${esc(item.run_id.slice(0, 10))} ↗</button> ${esc(item.case_id)} · ${esc(item.mode || item.relation)} · ${item.parent_id ? `родитель ${esc(item.parent_id.slice(0, 10))}` : "исходный запуск"}${item.score !== undefined ? ` · score ${item.score.toFixed(3)}` : ` · ${item.selected_ids.length} фактов`}</div>`,
    )
    .join("");
  document.querySelectorAll("[data-history]").forEach((button) =>
    button.addEventListener("click", () => {
      const run = history[Number(button.dataset.history)];
      current = run;
      parents.set(run.case_id, run.run_id);
      if (run.synthetic) {
        setView("temporal");
        $("temporal-case").value = run.case_id;
        $("mode").value = run.mode;
        $("valid-at").value = run.at;
        $("known-at").value = run.knowledge_position;
        renderTemporal(run);
      } else {
        setView("retrieval");
        $("case").value = run.case_id;
        $("relation").value = run.relation;
        for (const input of document.querySelectorAll("[data-signal]"))
          input.checked = !run.disabled.includes(input.dataset.signal);
        renderRetrieval(run);
      }
    }),
  );
}
async function retrieve() {
  const button = $("replay");
  button.disabled = true;
  try {
    const caseId = $("case").value;
    const run = await api("/api/replay", {
      case_id: caseId,
      relation: $("relation").value,
      disabled: [...document.querySelectorAll("[data-signal]")]
        .filter((e) => !e.checked)
        .map((e) => e.dataset.signal),
      parent_id: parents.get(caseId),
    });
    remember(run);
    renderRetrieval(run);
  } catch (error) {
    fail(error);
  } finally {
    button.disabled = false;
  }
}
function renderRetrieval(run) {
  const item = catalog.cases.find((c) => c.id === run.case_id);
  $("query").textContent = item.query;
  $("route-name").textContent =
    `${run.route} · ${run.candidates.length} кандидатов`;
  $("metrics").innerHTML =
    metric(run.score.toFixed(3), "Официальный score этого примера") +
    metric(run.top5.length, "Фрагментов в замороженном top-5") +
    metric(run.replay_ms.toFixed(2) + " мс", "Ранжирование; без поиска и LLM") +
    metric(
      run.reader ? run.reader.score.toFixed(3) : "—",
      "Score после Luna · сохранённый опыт",
    );
  $("candidates").innerHTML = run.candidates.length
    ? run.candidates
        .map(
          (row, i) =>
            `<button class="candidate" data-candidate="${i}"><b>${esc(row.rank)}. ${esc(short(row.id))}</b> ${row.selected ? badge("top-5") : ""}<small>${esc(row.source)} · ${row.score.toFixed(5)} · ${row.witnesses.length} подтверждений связи</small></button>`,
        )
        .join("")
    : '<p class="muted">Кандидатов нет. Точный отрицательный поиск не подменяется приблизительным совпадением.</p>';
  document
    .querySelectorAll("[data-candidate]")
    .forEach((button) =>
      button.addEventListener("click", () =>
        showEvidence(run, Number(button.dataset.candidate)),
      ),
    );
  if (run.candidates.length) showEvidence(run, 0);
  else $("evidence").textContent = "Нет кандидата для проверки.";
  $("diagnosis").innerHTML = run.stage_diagnoses.length
    ? run.stage_diagnoses
        .map(
          (d) =>
            `<div class="diag">${badge(stageLabels[d.stage], d.stage === "retrieved" ? "" : "warn")}<code>${esc(d.id)}</code></div>`,
        )
        .join("")
    : '<p class="muted">У задания нет положительных эталонных ID. Смотрите итоговый score, например, для проверки отсутствия символа.</p>';
  $("diagnosis").innerHTML += `<details><summary>Базовый плотный поиск: сохранённый top-5</summary><ol>${item.baseline_ids.map((id) => `<li><code>${esc(id)}</code></li>`).join("")}</ol></details>`;
  $("reader").innerHTML = run.reader
    ? `<p>${badge("Сохранённый эксперимент")} <code>${esc(run.reader.model)}</code></p><p>${run.reader.ids.length} из ${run.top5.length} кандидатов оставлено. Время модели: ${run.reader.seconds.toFixed(2)} с.</p><pre>${esc(run.reader.rationale)}</pre><p class="muted">Это записанное объяснение выбора, а не доказательство внутренних причин поведения модели.</p>`
    : '<p class="muted">Для изменённого запуска Luna не вызывалась. Старый ответ модели нельзя переносить на другой набор или порядок кандидатов.</p>';
}
function showEvidence(run, index) {
  document
    .querySelectorAll("[data-candidate]")
    .forEach((button) =>
      button.classList.toggle(
        "selected",
        Number(button.dataset.candidate) === index,
      ),
    );
  const row = run.candidates[index];
  const edge = row.edge
    ? `<div class="edge"><div class="node">${esc(short(row.edge.source))}</div><div class="arrow">${esc(row.edge.relation)}<br>→</div><div class="node">${esc(short(row.edge.target))}</div></div>`
    : '<p class="muted">Для этого маршрута нет записанного свидетельства вызова/ссылки. Определение символа ниже не подменяет доказательство ребра.</p>';
  const witnesses = row.witnesses
    .slice(0, 4)
    .map(
      (w) =>
        `<p><code>${esc(w.source)}:${w.line_start}</code> ${badge(w.kind)}</p><pre>${esc(w.text)}</pre><small class="muted">SHA-256 ${esc(w.source_sha256.slice(0, 16))}…</small>`,
    )
    .join("");
  const signals = Object.entries(row.signals)
    .map(
      ([name, signal]) =>
        `<tr><td>${esc(labels[name])}${run.disabled.includes(name) ? " · выкл." : ""}</td><td>${signal.rank}</td><td>${signal.weight}</td><td>${run.disabled.includes(name) ? "0" : signal.contribution.toFixed(5)}</td></tr>`,
    )
    .join("");
  $("evidence").innerHTML =
    `<code>${esc(row.id)}</code>${edge}${witnesses}${row.witnesses.length > 4 ? `<p class="muted">Показаны 4 из ${row.witnesses.length} подтверждений; все есть в JSON.</p>` : ""}<details open><summary>Фрагмент, доступный памяти</summary><pre>${esc(row.text)}</pre></details>${signals ? `<h2>Вклад в RRF</h2><table class="signal-table"><thead><tr><th>Сигнал</th><th>Ранг</th><th>Вес</th><th>Вклад</th></tr></thead><tbody>${signals}</tbody></table>` : '<p class="muted">Резервный гибридный поиск: фиксированные оценки; переключатели структурных сигналов его не изменяют.</p>'}`;
}
async function recall() {
  $("recall").disabled = true;
  try {
    const caseId = $("temporal-case").value;
    const run = await api("/api/temporal", {
      case_id: caseId,
      at: Number($("valid-at").value),
      knowledge: Number($("known-at").value),
      mode: $("mode").value,
      parent_id: parents.get(caseId),
    });
    remember(run);
    renderTemporal(run);
  } catch (error) {
    fail(error);
  } finally {
    $("recall").disabled = false;
  }
}
function renderTemporal(run) {
  const item = catalog.temporal_cases.find((c) => c.id === run.case_id);
  $("temporal-metrics").innerHTML =
    metric(run.selected_ids.length, "Фактов в ответе") +
    metric(run.conflicts.length, "Обнаружено текущих конфликтов") +
    metric(
      run.cache_hit ? "HIT" : "MISS",
      "Кэш с проверкой ревизии и двух времён",
    ) +
    metric(
      run.latency_ms.toFixed(2) + " мс",
      "Чтение памяти и проверка правил",
    );
  $("facts").innerHTML =
    run.facts
      .map(
        (fact) =>
          `<article class="fact"><p>${badge(statuses[fact.status], fact.status === "active" ? "" : "warn")} ${run.selected_ids.includes(fact.id) ? badge("В ответе") : badge("Только в истории", "warn")}</p><code>${esc(item.parameter)}</code> = <strong>${esc(JSON.stringify(fact.value))}</strong><p class="meta">Действие: [V${fact.valid_from ?? "?"}, ${fact.effective_to === null ? "∞" : "V" + fact.effective_to}) · Запись: ${esc(fact.recorded_at.slice(0, 10))}</p><p class="meta">${esc(fact.evidence.source)} · ${esc(fact.evidence.kind)}</p><details><summary>Свидетельство</summary><pre>${esc(fact.evidence.text)}</pre></details></article>`,
      )
      .join("") || '<p class="muted">На этот момент сведения не поступили.</p>';
  $("conflicts").innerHTML =
    (run.mode === "baseline"
      ? '<p class="notice synthetic">Проверки выключены. Отсутствие предупреждения не означает согласованность.</p>'
      : "") +
    (run.mode === "temporal"
      ? '<p class="muted">Режим проверяет актуальность, но не противоречия.</p>'
      : "") +
    (run.pairs.length
      ? run.pairs
          .map(
            (pair) =>
              `<p>${badge(diagnoses[pair.diagnosis], pair.diagnosis === "conflict" ? "bad" : "")} ${pair.current ? "в текущей выдаче" : "в истории"}</p><p class="muted"><code>${esc(pair.rule)}</code></p>`,
          )
          .join("")
      : '<p class="muted">Пары несовместимых утверждений этим режимом не обнаружены.</p>') +
    '<p class="muted">Ни один факт не удалён. Позднее подтверждение замены меняет текущую выдачу, но не переписывает то, что было известно раньше.</p>';
  $("temporal-source").innerHTML =
    `<p><code>${esc(item.source)}:${item.value_line}</code></p><p class="muted">Основание: ${esc(item.benchmark_task)} · ${esc(item.parameter)}</p><pre>${esc(item.source_text)}</pre><p class="muted">Исходное значение: ${esc(JSON.stringify(item.original))}. Контролируемая новая запись: ${esc(JSON.stringify(item.changed))}.</p>`;
}
function exportRun() {
  if (!current) return;
  const blob = new Blob([JSON.stringify(current, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = `memory-run-${current.run_id.slice(0, 12)}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function init() {
  catalog = await api("/api/catalog");
  $("verification").textContent =
    `Воспроизведено ${catalog.validation.graph_top5}/425 графовых выдач · ${catalog.validation.dense_top5}/425 базовых`;
  $("fixture-hash").textContent =
    `Артефакт ${catalog.content_hash.slice(0, 12)}`;
  $("case").innerHTML = catalog.cases
    .map(
      (c) =>
        `<option value="${esc(c.id)}">${esc(c.id)} · ${esc(c.category)}</option>`,
    )
    .join("");
  $("case").value = "callers_of_symbol-003";
  $("temporal-case").innerHTML = catalog.temporal_cases
    .map(
      (c) =>
        `<option value="${esc(c.id)}">${esc(c.benchmark_task)} · ${esc(c.parameter)}</option>`,
    )
    .join("");
  $("signals").innerHTML = Object.entries(labels)
    .map(
      ([key, label]) =>
        `<label><input type="checkbox" checked data-signal="${key}">${label}</label>`,
    )
    .join("");
  $("replay").addEventListener("click", retrieve);
  $("recall").addEventListener("click", recall);
  $("case").addEventListener("change", retrieve);
  $("temporal-case").addEventListener("change", recall);
  $("retrieval-tab").addEventListener("click", () => {
    setView("retrieval");
    retrieve();
  });
  $("temporal-tab").addEventListener("click", () => {
    setView("temporal");
    recall();
  });
  document
    .querySelectorAll(".export")
    .forEach((button) => button.addEventListener("click", exportRun));
  await retrieve();
}
init().catch(fail);
