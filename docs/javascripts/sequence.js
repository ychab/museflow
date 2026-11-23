// Renders every `<div class="seq">` from the JSON in its `<script type="application/json">`:
//   {"lanes": [{"id", "name", "sub", "color"}], "steps": [...]}
// A step is {"phase": "..."}, or {"from", "to", "text", "detail"?, "style"?} for an arrow (style: human, attacker, fail),
// or {"note": lane id, "text", "detail"?, "style"?} for a box on a lane (style: check, done, refused).
// `color` names a lane colour of sequence.css (teal, indigo, amber, green, grey, fail); texts may hold inline HTML.

function renderSequence(container) {
  const source = container.querySelector('script[type="application/json"]');
  if (!source || container.querySelector(".seq-grid")) return;

  const flow = JSON.parse(source.textContent);
  const index = Object.fromEntries(flow.lanes.map((lane, i) => [lane.id, i]));
  const grid = document.createElement("div");
  grid.className = "seq-grid";
  grid.style.gridTemplateColumns = `repeat(${flow.lanes.length}, minmax(0, 1fr))`;
  grid.style.minWidth = `${flow.lanes.length * 8}rem`;

  flow.lanes.forEach((lane, i) => {
    const actor = document.createElement("div");
    actor.className = "seq-actor";
    actor.style.gridColumn = String(i + 1);
    actor.style.setProperty("--seq-color", `var(${laneColor(lane)})`);
    actor.innerHTML = `<div>${lane.name}<small>${lane.sub ?? ""}</small></div>`;
    grid.append(actor);
  });

  let row = 2;
  let number = 0;

  for (const item of flow.steps) {
    if (item.phase) {
      const phase = document.createElement("div");
      phase.className = "seq-phase";
      phase.style.gridRow = String(row++);
      phase.textContent = item.phase;
      grid.append(phase);
      continue;
    }

    number += 1;
    const step = document.createElement("div");
    step.style.gridRow = String(row++);
    const detail = item.detail ? `<span class="seq-detail">${item.detail}</span>` : "";
    // Each step names the lanes it joins, in their colours: no scrolling back up to the headers of a long diagram
    const tag = (id) => `<b style="color:var(${laneColor(flow.lanes[index[id]])})">${flow.lanes[index[id]].name}</b>`;
    const route = item.note ? tag(item.note) : `${tag(item.from)} → ${tag(item.to)}`;
    const label = `<span class="seq-num">${number}</span><p><span class="seq-route">${route}</span>${item.text}${detail}</p>`;

    if (item.note) {
      const lane = index[item.note];
      step.className = "seq-step";
      step.style.gridColumn = `${lane + 1} / span ${Math.min(2, flow.lanes.length - lane)}`;
      step.innerHTML = `<div class="seq-note ${item.style ?? ""}"><div class="seq-label">${label}</div></div>`;
    } else {
      const from = index[item.from];
      const to = index[item.to];
      const span = Math.abs(to - from) + 1;
      // The arrow runs between the centres of the two lanes it joins.
      const inset = `${(50 / span).toFixed(3)}%`;
      step.className = `seq-step ${item.style ?? ""}`;
      step.style.gridColumn = `${Math.min(from, to) + 1} / span ${span}`;
      step.innerHTML =
        `<div class="seq-label" style="padding-inline:calc(${inset} + 0.3rem)">${label}</div>` +
        `<div class="seq-arrow ${to > from ? "right" : "left"}" style="margin-inline:${inset}"><i></i><b></b></div>`;
    }
    grid.append(step);
  }

  flow.lanes.forEach((_, i) => {
    const lifeline = document.createElement("div");
    lifeline.className = "seq-lifeline";
    lifeline.style.gridColumn = String(i + 1);
    lifeline.style.gridRow = `1 / ${row}`;
    grid.prepend(lifeline);
  });

  // Wider than the text column on most screens: shown over the page on demand
  const toolbar = document.createElement("div");
  toolbar.className = "seq-toolbar";
  const expand = document.createElement("button");
  expand.type = "button";
  expand.className = "seq-expand";
  expand.textContent = "⤢ Expand";
  expand.addEventListener("click", () => toggleExpanded(container));
  toolbar.append(expand);

  container.append(toolbar, grid);
}

function toggleExpanded(container, expanded = !container.classList.contains("seq-expanded")) {
  container.classList.toggle("seq-expanded", expanded);
  document.body.classList.toggle("seq-open", expanded);
  container.querySelector(".seq-expand").textContent = expanded ? "✕ Close (Esc)" : "⤢ Expand";
}

function laneColor(lane) {
  return lane.color === "fail" ? "--seq-fail" : `--seq-lane-${lane.color}`;
}

function renderSequences() {
  document.querySelectorAll(".seq").forEach(renderSequence);
}

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  document.querySelectorAll(".seq.seq-expanded").forEach((container) => toggleExpanded(container, false));
});

// With instant navigation, a page change swaps the content without reloading the scripts: `document$` emits on each.
if (window.document$) {
  window.document$.subscribe(renderSequences);
} else {
  document.addEventListener("DOMContentLoaded", renderSequences);
}
