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
  structural_order: "Graph order",
  bm25: "Lexical search",
  edge_frequency: "Edge frequency",
  graph_degree: "Node degree",
  id_overlap: "ID overlap",
};
const stageLabels = {
  candidate_missing: "Missing from candidates",
  ranking_loss: "Lost at top-5",
  ranking_position_loss: "Wrong ranking position",
  reader_drop: "Dropped by Luna",
  retrieved: "Retrieved",
};
const statuses = {
  active: "Active",
  superseded: "Superseded",
  expired: "Expired",
  not_yet_valid: "Not yet valid",
  unknown_validity: "Validity unknown",
};
const diagnoses = {
  conflict: "Conflict",
  version_change: "Version change, not a conflict",
  different_scope: "Different scope",
  unknown_validity: "Insufficient temporal data",
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
  if (!response.ok) throw new Error(data.error || "Request failed");
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
        `<div class="history-entry"><button data-history="${i}">${esc(item.run_id.slice(0, 10))} ↗</button> ${esc(item.case_id)} · ${esc(item.mode || item.relation)} · ${item.parent_id ? `parent ${esc(item.parent_id.slice(0, 10))}` : "root run"}${item.score !== undefined ? ` · score ${item.score.toFixed(3)}` : ` · ${item.selected_ids.length} facts`}</div>`,
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
    `${run.route} · ${run.candidates.length} candidates`;
  $("metrics").innerHTML =
    metric(run.score.toFixed(3), "Official score for this case") +
    metric(run.top5.length, "Fragments in frozen top-5") +
    metric(run.replay_ms.toFixed(2) + " ms", "Ranking only; no search or LLM") +
    metric(
      run.reader ? run.reader.score.toFixed(3) : "—",
      "Score after Luna · stored run",
    );
  $("candidates").innerHTML = run.candidates.length
    ? run.candidates
        .map(
          (row, i) =>
            `<button class="candidate" data-candidate="${i}"><b>${esc(row.rank)}. ${esc(short(row.id))}</b> ${row.selected ? badge("top-5") : ""}<small>${esc(row.source)} · ${row.score.toFixed(5)} · ${row.witnesses.length} relation witnesses</small></button>`,
        )
        .join("")
    : '<p class="muted">No candidates. Exact negative retrieval is not replaced by an approximate match.</p>';
  document
    .querySelectorAll("[data-candidate]")
    .forEach((button) =>
      button.addEventListener("click", () =>
        showEvidence(run, Number(button.dataset.candidate)),
      ),
    );
  if (run.candidates.length) showEvidence(run, 0);
  else $("evidence").textContent = "No candidate to inspect.";
  $("diagnosis").innerHTML = run.stage_diagnoses.length
    ? run.stage_diagnoses
        .map(
          (d) =>
            `<div class="diag">${badge(stageLabels[d.stage], d.stage === "retrieved" ? "" : "warn")}<code>${esc(d.id)}</code></div>`,
        )
        .join("")
    : '<p class="muted">This case has no positive gold IDs. Use the final score, for example, to verify that the symbol is absent.</p>';
  $("diagnosis").innerHTML += `<details><summary>Dense baseline retrieval: stored top-5</summary><ol>${item.baseline_ids.map((id) => `<li><code>${esc(id)}</code></li>`).join("")}</ol></details>`;
  $("reader").innerHTML = run.reader
    ? `<p>${badge("Stored experiment")} <code>${esc(run.reader.model)}</code></p><p>${run.reader.ids.length} of ${run.top5.length} candidates kept. Model time: ${run.reader.seconds.toFixed(2)} s.</p><pre>${esc(run.reader.rationale)}</pre><p class="muted">This is a stored selection rationale, not evidence of the model's internal reasoning.</p>`
    : '<p class="muted">Luna was not called for the modified run. The stored answer cannot be transferred to a different candidate set or ordering.</p>';
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
    : '<p class="muted">No recorded call/reference witness exists for this route. The symbol definition below is not evidence of that relation.</p>';
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
        `<tr><td>${esc(labels[name])}${run.disabled.includes(name) ? " · off" : ""}</td><td>${signal.rank}</td><td>${signal.weight}</td><td>${run.disabled.includes(name) ? "0" : signal.contribution.toFixed(5)}</td></tr>`,
    )
    .join("");
  $("evidence").innerHTML =
    `<code>${esc(row.id)}</code>${edge}${witnesses}${row.witnesses.length > 4 ? `<p class="muted">Showing 4 of ${row.witnesses.length} witnesses; all are available in JSON.</p>` : ""}<details open><summary>Memory-visible fragment</summary><pre>${esc(row.text)}</pre></details>${signals ? `<h2>RRF contribution</h2><table class="signal-table"><thead><tr><th>Signal</th><th>Rank</th><th>Weight</th><th>Contribution</th></tr></thead><tbody>${signals}</tbody></table>` : '<p class="muted">Fallback hybrid retrieval uses fixed scores; structural signal toggles do not affect it.</p>'}`;
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
    metric(run.selected_ids.length, "Facts in answer") +
    metric(run.conflicts.length, "Current conflicts detected") +
    metric(
      run.cache_hit ? "HIT" : "MISS",
      "Revision- and bitemporal-aware cache",
    ) +
    metric(
      run.latency_ms.toFixed(2) + " ms",
      "Memory read + rule checks",
    );
  $("facts").innerHTML =
    run.facts
      .map(
        (fact) =>
          `<article class="fact"><p>${badge(statuses[fact.status], fact.status === "active" ? "" : "warn")} ${run.selected_ids.includes(fact.id) ? badge("In answer") : badge("History only", "warn")}</p><code>${esc(item.parameter)}</code> = <strong>${esc(JSON.stringify(fact.value))}</strong><p class="meta">Validity: [V${fact.valid_from ?? "?"}, ${fact.effective_to === null ? "∞" : "V" + fact.effective_to}) · Recorded: ${esc(fact.recorded_at.slice(0, 10))}</p><p class="meta">${esc(fact.evidence.source)} · ${esc(fact.evidence.kind)}</p><details><summary>Evidence</summary><pre>${esc(fact.evidence.text)}</pre></details></article>`,
      )
      .join("") || '<p class="muted">No information had arrived by this knowledge cutoff.</p>';
  $("conflicts").innerHTML =
    (run.mode === "baseline"
      ? '<p class="notice synthetic">Checks are disabled. The absence of a warning does not imply consistency.</p>'
      : "") +
    (run.mode === "temporal"
      ? '<p class="muted">This mode checks temporal validity but not conflicts.</p>'
      : "") +
    (run.pairs.length
      ? run.pairs
          .map(
            (pair) =>
              `<p>${badge(diagnoses[pair.diagnosis], pair.diagnosis === "conflict" ? "bad" : "")} ${pair.current ? "in current answer" : "historical"}</p><p class="muted"><code>${esc(pair.rule)}</code></p>`,
          )
          .join("")
      : '<p class="muted">No incompatible assertion pairs were detected in this mode.</p>') +
    '<p class="muted">No fact is deleted. A later confirmed replacement changes the current answer without rewriting what was known earlier.</p>';
  $("temporal-source").innerHTML =
    `<p><code>${esc(item.source)}:${item.value_line}</code></p><p class="muted">Basis: ${esc(item.benchmark_task)} · ${esc(item.parameter)}</p><pre>${esc(item.source_text)}</pre><p class="muted">Original value: ${esc(JSON.stringify(item.original))}. Controlled new assertion: ${esc(JSON.stringify(item.changed))}.</p>`;
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
    `Replayed ${catalog.validation.graph_top5}/425 graph outputs · ${catalog.validation.dense_top5}/425 baseline outputs`;
  $("fixture-hash").textContent =
    `Artifact ${catalog.content_hash.slice(0, 12)}`;
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
