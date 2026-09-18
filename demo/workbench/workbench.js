"use strict";

const $ = (id) => document.getElementById(id);

const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[char],
  );

const PRESET_CASES = {
  fastapi: {
    id: "fastapi",

    label:
      "FastAPI · lifecycle API migration",

    repository:
      "fastapi/fastapi",

    revision:
      "0.92.x → 0.93.0+",

    badge:
      "FA",

    projectSummary:
      "Documented public FastAPI lifecycle API transition.",

    request:
      "Load a shared ML model when the FastAPI application starts.",

    workspaceTitle:
      "Proposal based on retrieved memory",

    worldLabel:
      "FastAPI v0.93+",

    entity:
      "fastapi.lifecycle_api",

    predicate:
      "default",

    environment:
      "application",

    at: 93,
    effective: 93,

    effectiveLabel:
      "FastAPI 0.93",

    currentShort:
      "lifespan",

    staleStatus:
      "The agent proposed an API remembered from an earlier FastAPI state.",

    resolvedStatus:
      "Earlier startup-event guidance is preserved as historical; lifespan is current.",

    editor: {
      file:
        "app/main.py",

      lines: [
        {
          text:
            "from fastapi import FastAPI",
          className:
            "keyword",
        },
        {
          text: "",
        },
        {
          text:
            "app = FastAPI()",
        },
        {
          text: "",
        },
        {
          text:
            '@app.on_event("startup")',
          className:
            "stale-line",
        },
        {
          text:
            "async def load_model():",
        },
        {
          text:
            '    ml_models["classifier"] = load_classifier()',
        },
        {
          text: "",
        },
        {
          text:
            "# Agent proposal based on retrieved memory",
          className:
            "agent-comment",
        },
      ],
    },

    evidence: [
      {
        className: "old",
        title: "FastAPI 0.92.x",
        detail: "startup / shutdown events",
      },
      {
        className: "newer",
        title: "FastAPI 0.93.0",
        detail: "lifespan · PR #2944",
      },
      {
        className: "current",
        title: "Current documentation",
        detail: "on_event is deprecated",
      },
    ],

    old: {
      value:
        '@app.on_event("startup")',

      valid_from:
        92,

      source:
        "https://github.com/fastapi/fastapi/tree/0.92.0",

      agent:
        "FastAPI 0.92.x lifecycle API",

      excerpt:
        "Before lifespan support was introduced, startup and shutdown event handlers were the established FastAPI lifecycle mechanism.",
    },

    newer: {
      value:
        "FastAPI(lifespan=lifespan)",

      valid_from:
        93,

      source:
        "https://fastapi.tiangolo.com/release-notes/#0930",

      agent:
        "FastAPI 0.93.0 · PR #2944",

      excerpt:
        "FastAPI 0.93.0 added lifespan async context managers, superseding startup and shutdown events. The release notes recommend lifespan going forward.",
    },

    provenance: [
      {
        label: "OLDER SOURCE",
        title: "fastapi/fastapi · 0.92.x",
        text:
          "Startup/shutdown event-handler API used before lifespan support was introduced.",
      },
      {
        label: "LATER SOURCE",
        title: "FastAPI 0.93.0 · PR #2944",
        text:
          "Lifespan async context managers introduced as the recommended replacement.",
      },
      {
        label: "CURRENT DOCS",
        title: "on_event: deprecated",
        text:
          "Current FastAPI documentation recommends lifespan event handlers.",
      },
    ],
  },


  pandas: {
    id:
      "pandas",

    label:
      "pandas · availability contradiction",

    repository:
      "pandas-dev/pandas",

    revision:
      "1.3.x → 2.0+",

    badge:
      "PD",

    projectSummary:
      "Direct contradiction between stored positive and negated API claims.",

    request:
      "Can this project still use DataFrame.append() under pandas 2.0?",

    workspaceTitle:
      "Proposal based on retrieved memory",

    worldLabel:
      "pandas 2.0+",

    entity:
      "pandas.dataframe_append_availability",

    predicate:
      "default",

    environment:
      "dataframe",

    at: 20,
    effective: 20,

    effectiveLabel:
      "pandas 2.0",

    currentShort:
      "append unavailable",

    conflictType:
      "direct-negation",

    conflictLabel:
      "DIRECT CONTRADICTION",

    relationMetricLabel:
      "recorded relations",

    resolvedRelation:
      "NEGATION RESOLVED",

    conflictSymbol:
      "≠",

    oldConflictStatus:
      "POSITIVE CLAIM",

    newConflictStatus:
      "NEGATED CLAIM",

    oldResolvedStatus:
      "HISTORICAL",

    newResolvedStatus:
      "CURRENT",

    actionTitle:
      "Resolve the contradiction?",

    actionText:
      "Record the newer negated assertion as current while preserving the earlier positive assertion in history. The resolution is stored as an explicit relation.",

    actionButton:
      "Resolve contradiction",

    resolvedTitle:
      "Contradiction resolved",

    staleStatus:
      "Memory contains incompatible positive and negated claims about DataFrame.append().",

    resolvedStatus:
      "The earlier positive availability claim remains in history; the pandas 2.0 negated assertion is current.",

    editor: {
      file:
        "pipeline.py",

      lines: [
        {
          text:
            "import pandas as pd",
          className:
            "keyword",
        },
        {
          text: "",
        },
        {
          text:
            'existing = pd.DataFrame({"x": [1, 2]})',
        },
        {
          text:
            'incoming = pd.DataFrame({"x": [3, 4]})',
        },
        {
          text: "",
        },
        {
          text:
            "combined = existing.append(incoming, ignore_index=True)",
          className:
            "stale-line",
        },
        {
          text: "",
        },
        {
          text:
            "# Agent proposal based on retrieved memory",
          className:
            "agent-comment",
        },
      ],
    },

    evidence: [
      {
        className: "old",
        title: "pandas 1.3.x",
        detail: "DataFrame.append available",
      },
      {
        className: "newer",
        title: "pandas 2.0",
        detail: "DataFrame.append removed",
      },
      {
        className: "current",
        title: "Current guidance",
        detail: "use pandas.concat",
      },
    ],

    old: {
      value:
        "DataFrame.append() is available",

      valid_from:
        13,

      negated:
        false,

      source:
        "https://pandas.pydata.org/pandas-docs/version/1.3/reference/api/pandas.DataFrame.append.html",

      agent:
        "pandas 1.3.x · positive API claim",

      excerpt:
        "In pandas 1.3, DataFrame.append() was available as a public DataFrame method.",
    },

    newer: {
      value:
        "DataFrame.append() is available",

      valid_from:
        20,

      negated:
        true,

      source:
        "https://pandas.pydata.org/pandas-docs/version/2.0/whatsnew/v2.0.0.html",

      agent:
        "pandas 2.0 · removal evidence",

      excerpt:
        "pandas 2.0 removed DataFrame.append(). Current code should use pandas.concat() instead.",
    },

    provenance: [
      {
        label: "POSITIVE EVIDENCE",
        title: "pandas 1.3.x API",
        text:
          "Earlier documentation contains DataFrame.append() as an available API.",
      },
      {
        label: "NEGATED EVIDENCE",
        title: "pandas 2.0 removal",
        text:
          "The 2.0 release removes DataFrame.append(), directly contradicting the stored availability claim.",
      },
      {
        label: "CURRENT GUIDANCE",
        title: "pandas.concat",
        text:
          "Current pandas guidance uses concat() instead of the removed append() method.",
      },
    ],
  },


  pydantic: {
    id:
      "pydantic",

    label:
      "Pydantic · version/API context mismatch",

    repository:
      "pydantic/pydantic",

    revision:
      "1.10.x → 2.x",

    badge:
      "PY",

    projectSummary:
      "Retrieved V1 guidance applied inside a current Pydantic V2 project context.",

    request:
      "Validate this payload using the current Pydantic V2 BaseModel API.",

    workspaceTitle:
      "Proposal from mismatched memory context",

    worldLabel:
      "Pydantic V2",

    entity:
      "pydantic.model_validation_api",

    predicate:
      "default",

    environment:
      "model",

    at: 2,
    effective: 2,

    effectiveLabel:
      "Pydantic V2",

    currentShort:
      "model_validate",

    conflictType:
      "context-mismatch",

    conflictLabel:
      "VERSION / API CONTEXT MISMATCH",

    relationMetricLabel:
      "recorded relations",

    resolvedRelation:
      "CONTEXT RESOLVED",

    conflictSymbol:
      "⇄",

    oldConflictStatus:
      "V1 CONTEXT",

    newConflictStatus:
      "V2 CONTEXT",

    oldResolvedStatus:
      "OUT OF CONTEXT",

    newResolvedStatus:
      "APPLICABLE",

    actionTitle:
      "Resolve the version context?",

    actionText:
      "Keep the V1 guidance in provenance and record the V2 assertion as current for this project version. The resolution is stored as an explicit relation.",

    actionButton:
      "Apply V2 context",

    resolvedTitle:
      "Context resolved",

    staleStatus:
      "The retrieved assertion belongs to the Pydantic V1 API context, while the project is running against V2.",

    resolvedStatus:
      "V1 guidance remains inspectable as out-of-context evidence; model_validate is applicable to the current V2 project.",

    editor: {
      file:
        "models.py",

      lines: [
        {
          text:
            "from pydantic import BaseModel",
          className:
            "keyword",
        },
        {
          text: "",
        },
        {
          text:
            "class User(BaseModel):",
        },
        {
          text:
            "    id: int",
        },
        {
          text:
            "    name: str",
        },
        {
          text: "",
        },
        {
          text:
            "user = User.parse_obj(payload)",
          className:
            "stale-line",
        },
        {
          text: "",
        },
        {
          text:
            "# Retrieved from Pydantic V1 memory context",
          className:
            "agent-comment",
        },
      ],
    },

    evidence: [
      {
        className: "old",
        title: "Retrieved V1 context",
        detail: "BaseModel.parse_obj",
      },
      {
        className: "newer",
        title: "Current V2 context",
        detail: "BaseModel.model_validate",
      },
      {
        className: "current",
        title: "Migration guidance",
        detail: "V1 methods → model_* API",
      },
    ],

    old: {
      value:
        "User.parse_obj(payload)",

      valid_from:
        1,

      negated:
        false,

      source:
        "https://docs.pydantic.dev/1.10/usage/models/",

      agent:
        "Pydantic V1 · API context",

      excerpt:
        "Pydantic V1 exposed BaseModel.parse_obj() for parsing and validating dictionary-like input.",
    },

    newer: {
      value:
        "User.model_validate(payload)",

      valid_from:
        2,

      negated:
        false,

      source:
        "https://docs.pydantic.dev/2.3/blog/pydantic-v2-alpha/",

      agent:
        "Pydantic V2 · current API context",

      excerpt:
        "Pydantic V2 uses the model_* BaseModel API family; model_validate() is the V2 validation path corresponding to V1 parse_obj().",
    },

    provenance: [
      {
        label: "RETRIEVED CONTEXT",
        title: "Pydantic V1",
        text:
          "parse_obj() is valid historical guidance from the V1 API context.",
      },
      {
        label: "CURRENT CONTEXT",
        title: "Pydantic V2",
        text:
          "The active project context uses the V2 model_* BaseModel API.",
      },
      {
        label: "MIGRATION GUIDANCE",
        title: "model_validate",
        text:
          "The V2 validation path for this input is model_validate().",
      },
    ],
  },
};


let DEMO_CASE =
  PRESET_CASES.fastapi;


let state = null;
let inspectorOpen = false;
let loading = false;


async function request(action, payload = {}) {
  const response = await fetch(`/api/live/${action}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }

  return data;
}


function coordinates() {
  return {
    room: state.room,
    entity: DEMO_CASE.entity,
    predicate: DEMO_CASE.predicate,
    environment: DEMO_CASE.environment,
    at: DEMO_CASE.at,
  };
}


function factBySource(source) {
  return state?.facts?.find(
    (fact) => fact.evidence.source === source,
  );
}


function knownReplacement() {
  const oldFact = factBySource(DEMO_CASE.old.source);
  const newFact = factBySource(DEMO_CASE.newer.source);

  if (!oldFact || !newFact) {
    return null;
  }

  return state.replacements.find(
    (edge) =>
      edge.old_id === oldFact.id &&
      edge.new_id === newFact.id &&
      edge.recorded_at <= state.known_at,
  );
}


function displayFactValue(fact) {
  if (!fact) {
    return "UNKNOWN";
  }

  return fact.negated
    ? `NOT ${fact.value}`
    : fact.value;
}


function conflictPresentation() {
  return {
    conflictLabel:
      DEMO_CASE.conflictLabel ||
      "STATE CONFLICT",

    resolvedRelation:
      DEMO_CASE.resolvedRelation ||
      "SUPERSEDED",

    conflictSymbol:
      DEMO_CASE.conflictSymbol ||
      "⚡",

    oldConflictStatus:
      DEMO_CASE.oldConflictStatus ||
      "ACTIVE CLAIM",

    newConflictStatus:
      DEMO_CASE.newConflictStatus ||
      "ACTIVE CLAIM",

    oldResolvedStatus:
      DEMO_CASE.oldResolvedStatus ||
      "HISTORICAL",

    newResolvedStatus:
      DEMO_CASE.newResolvedStatus ||
      "CURRENT",

    actionTitle:
      DEMO_CASE.actionTitle ||
      "Record the state transition?",

    actionText:
      DEMO_CASE.actionText ||
      "This adds an explicit supersession relation. The earlier fact will remain in history.",

    actionButton:
      DEMO_CASE.actionButton ||
      "Confirm supersession",

    resolvedTitle:
      DEMO_CASE.resolvedTitle ||
      "Transition recorded",

    relationMetricLabel:
      DEMO_CASE.relationMetricLabel ||
      "supersessions",
  };
}


function renderProject() {
  $("repo-name").textContent =
    DEMO_CASE.repository;

  $("repo-revision").textContent =
    DEMO_CASE.revision;

  $("context-repo").textContent =
    DEMO_CASE.repository;

  $("context-revision").textContent =
    DEMO_CASE.revision;

  $("context-task").textContent =
    DEMO_CASE.request;

  $("context-world").textContent =
    `${DEMO_CASE.worldLabel} · V${state.at}`;

  $("context-known").textContent =
    `K${state.known} / ${state.events.length}`;

  $("task-title").textContent =
    DEMO_CASE.workspaceTitle;

  $("preset-request-text").textContent =
    DEMO_CASE.request;

  const projectEmpty =
    document.querySelector(".empty-project");

  projectEmpty.innerHTML = `
    <span class="repo-badge">
      ${escapeHtml(DEMO_CASE.badge)}
    </span>

    <strong>
      ${escapeHtml(DEMO_CASE.repository)}
    </strong>

    <p>
      ${escapeHtml(DEMO_CASE.projectSummary)}
    </p>
  `;

  document.querySelector(".project-section").innerHTML = `
    <span class="section-label">
      EVIDENCE
    </span>

    ${DEMO_CASE.evidence
      .map(
        (item) => `
          <button
            class="evidence-tree-item active"
            type="button"
          >
            <span class="tree-dot ${escapeHtml(item.className)}"></span>

            <span>
              <strong>${escapeHtml(item.title)}</strong>
              <small>${escapeHtml(item.detail)}</small>
            </span>
          </button>
        `,
      )
      .join("")}
  `;
}


function renderWorkspace() {
  const editorTab =
    document.querySelector(".editor-tab");

  editorTab.textContent =
    DEMO_CASE.editor.file;

  const replacement =
    knownReplacement();

  document.querySelector(".editor-content").innerHTML =
    DEMO_CASE.editor.lines
      .map((line, index) => {
        const className =
          line.className || "";

        const resolvedClass =
          replacement &&
          className.includes("stale-line")
            ? "historical-line"
            : className;

        return `
          <div class="line-number">
            ${index + 1}
          </div>

          <div class="agent-line ${resolvedClass}">
            ${escapeHtml(line.text)}
          </div>
        `;
      })
      .join("");

  const status =
    $("agent-status");

  if (replacement) {
    status.className =
      "agent-status resolved";

    status.querySelector("strong").textContent =
      "Memory state resolved";

    status.querySelector("p").textContent =
      DEMO_CASE.resolvedStatus;

    $("inspect-memory").textContent =
      "Inspect memory";

    $("inspect-memory").disabled =
      false;

    return;
  }

  status.className =
    "agent-status warning";

  status.querySelector("strong").textContent =
    "Potentially stale memory";

  status.querySelector("p").textContent =
    DEMO_CASE.staleStatus;

  $("inspect-memory").textContent =
    "Inspect memory";

  $("inspect-memory").disabled =
    false;
}


function renderMemoryStateMap() {
  const facts = state?.facts || [];

  const presentation =
    conflictPresentation();

  const replacements = (state?.replacements || []).filter(
    (edge) => edge.recorded_at <= state.known_at,
  );

  if (facts.length < 2) {
    return `
      <section class="memory-state-graph">
        <div class="state-graph-heading">
          <div>
            <span class="section-label">MEMORY STATE GRAPH</span>
            <h3>Whole-memory state</h3>
          </div>

          <span class="graph-snapshot">
            V${state.at} · K${state.known}
          </span>
        </div>

        <div class="state-graph-empty">
          Waiting for enough memory assertions to build the graph.
        </div>
      </section>
    `;
  }

  const first = facts[0];
  const second = facts[1];

  const replacement = replacements.find(
    (edge) =>
      (edge.old_id === first.id && edge.new_id === second.id) ||
      (edge.old_id === second.id && edge.new_id === first.id),
  );

  const conflict =
    state.answer_status === "conflict" &&
    !replacement;

  let oldFact = first;
  let newFact = second;

  if (replacement) {
    oldFact =
      facts.find((fact) => fact.id === replacement.old_id) || first;

    newFact =
      facts.find((fact) => fact.id === replacement.new_id) || second;
  }

  const selectedFact =
    facts.find((fact) => fact.selected);

  const currentValue =
    replacement
      ? displayFactValue(newFact)
      : conflict
        ? "UNRESOLVED"
        : displayFactValue(selectedFact);

  const graphClass =
    replacement
      ? "resolved"
      : conflict
        ? "conflict"
        : "neutral";

  const relationLabel =
    replacement
      ? `${presentation.resolvedRelation} · V${replacement.effective}`
      : conflict
        ? presentation.conflictLabel
        : "MEMORY STATE";

  const oldStatus =
    replacement
      ? presentation.oldResolvedStatus
      : conflict
        ? presentation.oldConflictStatus
        : "ACTIVE";

  const newStatus =
    replacement
      ? presentation.newResolvedStatus
      : conflict
        ? presentation.newConflictStatus
        : "ACTIVE";

  const activeConflictCount =
    replacement
      ? 0
      : state.conflicts.length;

  const connectorSvg =
    replacement
      ? `
        <path
          class="graph-edge supersession-edge"
          d="M 380 164 C 480 164, 610 164, 710 164"
          marker-end="url(#arrow-green)"
        />

        <path
          class="graph-edge current-edge"
          d="M 885 215 C 845 260, 710 280, 650 294"
          marker-end="url(#arrow-green)"
        />
      `
      : `
        <path
          class="graph-edge conflict-edge"
          d="M 215 215 C 260 270, 425 278, 500 296"
          marker-end="url(#arrow-red)"
        />

        <path
          class="graph-edge conflict-edge"
          d="M 885 215 C 840 270, 675 278, 600 296"
          marker-end="url(#arrow-red)"
        />
      `;

  return `
    <section class="memory-state-graph ${graphClass}">
      <div class="state-graph-heading">
        <div>
          <span class="section-label">
            MEMORY STATE GRAPH
          </span>

          <h3>
            Whole-memory state
          </h3>
        </div>

        <div class="state-graph-meta">
          <span>
            <strong>${facts.length}</strong>
            assertions
          </span>

          <span>
            <strong>${activeConflictCount}</strong>
            conflicts
          </span>

          <span>
            <strong>${replacements.length}</strong>
            ${escapeHtml(presentation.relationMetricLabel)}
          </span>

          <span class="graph-snapshot">
            V${state.at} · K${state.known}
          </span>
        </div>
      </div>

      <div class="state-graph-canvas">
        <svg
          viewBox="0 0 1100 365"
          role="img"
          aria-label="Graph of memory assertions and their current state"
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            <marker
              id="arrow-red"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#b44a42"></path>
            </marker>

            <marker
              id="arrow-green"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#17644e"></path>
            </marker>

            <marker
              id="arrow-gray"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#9aa49f"></path>
            </marker>
          </defs>


          <!-- Evidence -> assertion -->
          <path
            class="graph-edge evidence-edge"
            d="M 215 61 L 215 91"
            marker-end="url(#arrow-gray)"
          />

          <path
            class="graph-edge evidence-edge"
            d="M 885 61 L 885 91"
            marker-end="url(#arrow-gray)"
          />

          ${connectorSvg}


          <!-- source 1 -->
          <foreignObject x="75" y="12" width="280" height="50">
            <div
              xmlns="http://www.w3.org/1999/xhtml"
              class="graph-source"
            >
              <span>SOURCE</span>
              <strong>${escapeHtml(oldFact.evidence.agent)}</strong>
            </div>
          </foreignObject>


          <!-- source 2 -->
          <foreignObject x="745" y="12" width="280" height="50">
            <div
              xmlns="http://www.w3.org/1999/xhtml"
              class="graph-source"
            >
              <span>SOURCE</span>
              <strong>${escapeHtml(newFact.evidence.agent)}</strong>
            </div>
          </foreignObject>


          <!-- old assertion -->
          <foreignObject x="40" y="95" width="350" height="125">
            <div
              xmlns="http://www.w3.org/1999/xhtml"
              class="graph-fact-node ${
                replacement
                  ? "historical"
                  : conflict
                    ? "conflict"
                    : "active"
              }"
            >
              <div class="graph-node-kicker">
                MEMORY ASSERTION
              </div>

              <strong>
                ${escapeHtml(displayFactValue(oldFact))}
              </strong>

              <div class="graph-node-bottom">
                <span>${oldStatus}</span>

                <small>
                  V${oldFact.valid_from ?? "?"}
                  →
                  ${
                    replacement
                      ? `V${replacement.effective}`
                      : "∞"
                  }
                </small>
              </div>
            </div>
          </foreignObject>


          <!-- new assertion -->
          <foreignObject x="710" y="95" width="350" height="125">
            <div
              xmlns="http://www.w3.org/1999/xhtml"
              class="graph-fact-node ${
                replacement
                  ? "current"
                  : conflict
                    ? "conflict"
                    : "active"
              }"
            >
              <div class="graph-node-kicker">
                MEMORY ASSERTION
              </div>

              <strong>
                ${escapeHtml(displayFactValue(newFact))}
              </strong>

              <div class="graph-node-bottom">
                <span>${newStatus}</span>

                <small>
                  V${newFact.valid_from ?? "?"} → ∞
                </small>
              </div>
            </div>
          </foreignObject>


          <!-- relation badge -->
          <foreignObject x="420" y="120" width="260" height="78">
            <div
              xmlns="http://www.w3.org/1999/xhtml"
              class="graph-relation-badge ${graphClass}"
            >
              <span>${relationLabel}</span>

              <strong>
                ${
                  replacement
                    ? "→"
                    : conflict
                      ? presentation.conflictSymbol
                      : "·"
                }
              </strong>
            </div>
          </foreignObject>


          <!-- current state -->
          <foreignObject x="390" y="292" width="320" height="62">
            <div
              xmlns="http://www.w3.org/1999/xhtml"
              class="graph-current-state ${graphClass}"
            >
              <span>CURRENT MEMORY STATE</span>

              <strong>
                ${escapeHtml(currentValue)}
              </strong>
            </div>
          </foreignObject>
        </svg>
      </div>

      <div class="state-graph-legend">
        <span class="current">● current</span>
        <span class="conflict">● conflict</span>
        <span class="historical">● historical</span>

        <span class="legend-note">
          Sources → assertions → resolved/current state
        </span>
      </div>
    </section>
  `;
}


function renderInspector() {
  const inspector = $("memory-inspector");

  const presentation =
    conflictPresentation();

  inspector.hidden = !inspectorOpen;

  if (!inspectorOpen) {
    return;
  }

  const oldFact =
    factBySource(DEMO_CASE.old.source);

  const newFact =
    factBySource(DEMO_CASE.newer.source);

  const replacement =
    knownReplacement();

  const conflict =
    state.answer_status === "conflict" &&
    !replacement;

  const oldClass =
    replacement
      ? "historical"
      : conflict
        ? "conflict"
        : "known";

  const newClass =
    replacement
      ? "current"
      : conflict
        ? "conflict"
        : "known";

  const oldBadge =
    replacement
      ? "HISTORICAL"
      : conflict
        ? "ACTIVE CLAIM"
        : "KNOWN";

  const newBadge =
    replacement
      ? "CURRENT"
      : conflict
        ? "ACTIVE CLAIM"
        : "NEW EVIDENCE";

  let relation;

  if (replacement) {
    relation = `
      <div class="memory-relation resolved">
        <span>SUPERSEDED</span>
        <strong>→</strong>
        <small>effective from ${escapeHtml(DEMO_CASE.effectiveLabel)}</small>
      </div>
    `;
  } else {
    relation = `
      <div class="memory-relation conflict">
        <span>STATE CONFLICT</span>
        <strong>↔</strong>
        <small>
          newer evidence does not overwrite earlier memory automatically
        </small>
      </div>
    `;
  }

  inspector.innerHTML = `
    <div class="inspector-heading">
      <div>
        <span class="section-label">
          MEMORY INSPECTOR
        </span>

        <h2>
          What happened in memory?
        </h2>
      </div>

      <button
        id="close-inspector"
        class="secondary"
        type="button"
      >
        Close
      </button>
    </div>

    <div class="memory-inspector-body">

      ${renderMemoryStateMap()}


      <details class="provenance-details">
        <summary>
          Sources &amp; provenance

          <span>
            ${DEMO_CASE.provenance.length}
            supporting sources
          </span>
        </summary>

        <div class="provenance-row">
          ${DEMO_CASE.provenance
            .map(
              (source) => `
                <article>
                  <span>
                    ${escapeHtml(source.label)}
                  </span>

                  <strong>
                    ${escapeHtml(source.title)}
                  </strong>

                  <p>
                    ${escapeHtml(source.text)}
                  </p>
                </article>
              `,
            )
            .join("")}
        </div>
      </details>

      ${

        conflict
          ? `
            <div class="inspector-action">
              <div>
                <strong>
                  ${escapeHtml(presentation.actionTitle)}
                </strong>

                <p>
                  ${escapeHtml(presentation.actionText)}
                </p>
              </div>

              <button
                id="confirm-transition"
                class="primary"
                type="button"
              >
                ${escapeHtml(presentation.actionButton)}
              </button>
            </div>
          `
          : `
            <div class="inspector-action resolved">
              <div>
                <strong>
                  ${escapeHtml(presentation.resolvedTitle)}
                </strong>

                <p>
                  ${escapeHtml(DEMO_CASE.resolvedStatus)}
                </p>
              </div>

              <span class="resolved-pill">
                CURRENT · ${escapeHtml(DEMO_CASE.currentShort)}
              </span>
            </div>
          `
      }

    </div>
  `;

  $("close-inspector").onclick = () => {
    inspectorOpen = false;
    renderInspector();
  };

  document
    .querySelectorAll("[data-memory-map-fact]")
    .forEach((button) => {
      button.onclick = () => {
        document
          .querySelectorAll("[data-memory-map-fact]")
          .forEach((node) =>
            node.classList.remove("focused"),
          );

        button.classList.add("focused");
      };
    });

  const confirm =
    $("confirm-transition");

  if (confirm) {
    confirm.onclick =
      confirmTransition;
  }
}


function render() {
  if (!state) {
    return;
  }

  if ($("preset-case")) {
    $("preset-case").value =
      DEMO_CASE.id;
  }

  renderProject();
  renderWorkspace();
  renderInspector();
}


async function confirmTransition() {
  const oldFact =
    factBySource(DEMO_CASE.old.source);

  const newFact =
    factBySource(DEMO_CASE.newer.source);

  if (!oldFact || !newFact) {
    return;
  }

  const button =
    $("confirm-transition");

  button.disabled = true;
  button.textContent =
    "Recording…";

  try {
    state = await request(
      "replace",
      {
        ...coordinates(),
        old_id: oldFact.id,
        new_id: newFact.id,
        effective: DEMO_CASE.effective,
      },
    );

    render();
  } catch (error) {
    button.disabled = false;
    button.textContent =
      conflictPresentation().actionButton;

    alert(error.message);
  }
}


async function loadDemoCase() {
  if (loading) {
    return;
  }

  loading = true;

  $("new-session").disabled = true;

  $("agent-status")
    .querySelector("strong")
    .textContent =
      `${DEMO_CASE.label} · loading…`;

  try {
    state = await request("create");

    const room = state.room;

    state = await request(
      "save",
      {
        room,
        entity: DEMO_CASE.entity,
        predicate: DEMO_CASE.predicate,
        environment: DEMO_CASE.environment,
        at: DEMO_CASE.at,

        value:
          DEMO_CASE.old.value,

        valid_from:
          DEMO_CASE.old.valid_from,

        valid_to: null,

        source:
          DEMO_CASE.old.source,

        agent:
          DEMO_CASE.old.agent,

        excerpt:
          DEMO_CASE.old.excerpt,

        negated:
          Boolean(DEMO_CASE.old.negated),
      },
    );

    state = await request(
      "save",
      {
        room,
        entity: DEMO_CASE.entity,
        predicate: DEMO_CASE.predicate,
        environment: DEMO_CASE.environment,
        at: DEMO_CASE.at,

        value:
          DEMO_CASE.newer.value,

        valid_from:
          DEMO_CASE.newer.valid_from,

        valid_to: null,

        source:
          DEMO_CASE.newer.source,

        agent:
          DEMO_CASE.newer.agent,

        excerpt:
          DEMO_CASE.newer.excerpt,

        negated:
          Boolean(DEMO_CASE.newer.negated),
      },
    );

    inspectorOpen = false;

    render();
  } catch (error) {
    $("agent-status")
      .querySelector("strong")
      .textContent =
        "Unable to load demo case";

    $("agent-status")
      .querySelector("p")
      .textContent =
        error.message;
  } finally {
    loading = false;
    $("new-session").disabled = false;
  }
}


const presetSelect =
  $("preset-case");

presetSelect.innerHTML =
  Object.values(PRESET_CASES)
    .map(
      (item) => `
        <option value="${item.id}">
          ${escapeHtml(item.label)}
        </option>
      `,
    )
    .join("");

presetSelect.value =
  DEMO_CASE.id;

presetSelect.onchange =
  async (event) => {
    const nextCase =
      PRESET_CASES[event.target.value];

    if (!nextCase || loading) {
      return;
    }

    DEMO_CASE =
      nextCase;

    inspectorOpen =
      false;

    await loadDemoCase();
  };


$("new-session").onclick =
  loadDemoCase;

$("inspect-memory").onclick = () => {
  inspectorOpen = true;
  renderInspector();
};


loadDemoCase();
