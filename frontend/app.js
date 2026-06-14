const refreshButton = document.querySelector("#refresh-button");
const reloadEventsButton = document.querySelector("#reload-events-button");
const statusMessage = document.querySelector("#status-message");
const startEventList = document.querySelector("#start-event-list");
const runtimeList = document.querySelector("#runtime-list");

let runtimes = [];
let startEvent = null;
let deviceState = null;

async function refreshRuntimeState() {
  try {
    const response = await fetch("/api/runtimes");

    if (!response.ok) {
      throw new Error(`Runtime API returned ${response.status}`);
    }

    const state = await response.json();
    runtimes = state.runtimes ?? [];
    startEvent = state.start_event ?? null;
    deviceState = state.device_state ?? null;

    render();
  } catch (error) {
    statusMessage.textContent = "";
  }
}

async function triggerStartEvent(eventId) {
  statusMessage.textContent = "Creating runtime...";

  try {
    const response = await fetch(`/api/events/${encodeURIComponent(eventId)}`, {
      method: "POST",
    });

    if (!response.ok) {
      throw new Error(`Start returned ${response.status}`);
    }

    statusMessage.textContent = "Runtime created.";
    await refreshRuntimeState();
  } catch (error) {
    statusMessage.textContent = "Runtime could not be created.";
  }
}

async function triggerEvent(runtimeId, eventId) {
  statusMessage.textContent = "Triggering event...";

  try {
    const response = await fetch(`/api/runtimes/${encodeURIComponent(runtimeId)}/events/${encodeURIComponent(eventId)}`, {
      method: "POST",
    });

    if (!response.ok) {
      throw new Error(`Trigger returned ${response.status}`);
    }

    statusMessage.textContent = "Event triggered.";
    await refreshRuntimeState();
  } catch (error) {
    statusMessage.textContent = "Event could not be triggered.";
  }
}

async function killRuntime(runtimeId) {
  statusMessage.textContent = "Killing runtime...";

  try {
    const response = await fetch(`/api/runtimes/${encodeURIComponent(runtimeId)}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      throw new Error(`Kill returned ${response.status}`);
    }

    statusMessage.textContent = "Runtime killed.";
    await refreshRuntimeState();
  } catch (error) {
    statusMessage.textContent = "Runtime could not be killed.";
  }
}

async function reloadEvents() {
  statusMessage.textContent = "Reloading events...";

  try {
    const response = await fetch("/api/events/reload", {
      method: "POST",
    });

    if (!response.ok) {
      const result = await response.json();
      throw new Error(result.error || `Reload returned ${response.status}`);
    }

    statusMessage.textContent = "Events reloaded.";
    await refreshRuntimeState();
  } catch (error) {
    statusMessage.textContent = "Events could not be reloaded.";
  }
}

function render() {
  renderDeviceState();
  renderStartEvent();
  renderRuntimes();
}

function renderDeviceState() {
  const existing = document.querySelector("#device-state-panel");

  if (existing) {
    existing.remove();
  }

  if (!deviceState || deviceState.passed || !deviceState.issues?.length) {
    return;
  }

  const panel = document.createElement("section");
  panel.id = "device-state-panel";
  panel.className = "device-state-panel";

  const title = document.createElement("h2");
  title.textContent = "Device state check failed";

  const list = document.createElement("dl");
  list.className = "device-state-list";

  for (const issue of deviceState.issues) {
    const topic = document.createElement("dt");
    topic.textContent = issue.topic;

    const detail = document.createElement("dd");
    const actual = issue.actual ?? "missing";
    detail.textContent = `Expected ${String(issue.expected)}, got ${actual}`;

    list.append(topic, detail);
  }

  panel.append(title, list);
  document.querySelector(".toolbar").after(panel);
}

function renderStartEvent() {
  startEventList.innerHTML = "";

  if (!startEvent) {
    startEventList.append(emptyState("No start event available."));
    return;
  }

  startEventList.append(renderEventBlock(startEvent, "Start", () => triggerStartEvent(startEvent.id)));
}

function renderRuntimes() {
  runtimeList.innerHTML = "";

  if (!runtimes.length) {
    runtimeList.append(emptyState("No active runtimes."));
    return;
  }

  for (const runtime of runtimes) {
    runtimeList.append(renderRuntime(runtime));
  }
}

function renderRuntime(runtime) {
  const section = document.createElement("section");
  section.className = "runtime-block";

  const header = document.createElement("div");
  header.className = "runtime-header";

  const titleGroup = document.createElement("div");

  const name = document.createElement("h3");
  name.textContent = runtime.name;

  const location = document.createElement("p");
  location.className = "location";
  location.textContent = runtime.current_location_name;

  const kill = document.createElement("button");
  kill.type = "button";
  kill.className = "danger-button";
  kill.textContent = "Kill";
  kill.addEventListener("click", () => killRuntime(runtime.id));

  titleGroup.append(name, location);
  header.append(titleGroup, kill);
  section.append(header);

  const variables = renderLocationVariables(runtime.location_variables ?? {});

  if (variables) {
    section.append(variables);
  }

  const events = document.createElement("div");
  events.className = "event-list";

  if (!runtime.events.length) {
    events.append(emptyState("No events available for this runtime."));
  }

  for (const event of runtime.events) {
    events.append(renderEventBlock(event, "Trigger", () => triggerEvent(runtime.id, event.id)));
  }

  section.append(events);
  return section;
}

function renderLocationVariables(variables) {
  const entries = Object.entries(variables);

  if (!entries.length) {
    return null;
  }

  const list = document.createElement("dl");
  list.className = "variable-list";

  for (const [name, value] of entries) {
    const key = document.createElement("dt");
    key.textContent = name;

    const displayValue = document.createElement("dd");
    displayValue.textContent = String(value);

    list.append(key, displayValue);
  }

  return list;
}

function renderEventBlock(event, label, triggerAction) {
  const block = document.createElement("article");
  block.className = "event-block";

  const title = document.createElement("h3");
  title.textContent = event.name;

  const description = document.createElement("p");
  description.className = "event-description";
  description.textContent = event.description || "No description available.";

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.textContent = label;
  trigger.addEventListener("click", triggerAction);

  block.append(title, description, trigger);
  return block;
}

function emptyState(message) {
  const empty = document.createElement("p");
  empty.className = "empty-state";
  empty.textContent = message;
  return empty;
}

refreshButton.addEventListener("click", refreshRuntimeState);
reloadEventsButton.addEventListener("click", reloadEvents);
refreshRuntimeState();
setInterval(refreshRuntimeState, 3000);
