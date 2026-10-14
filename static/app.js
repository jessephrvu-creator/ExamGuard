
const $ = (id) => document.getElementById(id);

let lastStatus = null;
let isScanning = false;
let toastTimer;
let lastReportedError = null;

const staleAfterSeconds = 5;

function toast(message) {
  const el = $("toast");
  if (!el) return;
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 4500);
}

function bandClass(signal) {
  if (signal === "Near / Strong") return "near";
  if (signal === "Medium") return "medium";
  if (signal === "Far / Weak") return "far";
  return "unknown";
}

function displayName(name) {
  return typeof name === "string" && name.trim()
    ? name
    : "Name unavailable";
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[ch]);
}

function renderDevices(devices) {
  const filter = $("signalFilter").value;

  const shown = devices
    .filter((d) => {
      if (filter === "All signals") return true;
      if (filter === "Near / Strong") return d.rssi != null && d.rssi >= -60;
      if (filter === "Medium") return d.rssi != null && d.rssi >= -75 && d.rssi < -60;
      if (filter === "Far / Weak") return d.rssi != null && d.rssi < -75;
      if (filter === "Unknown RSSI") return d.rssi == null;
      return true;
    })
    .sort((a, b) => {
      const ar = Number.isFinite(a.rssi) ? a.rssi : -Infinity;
      const br = Number.isFinite(b.rssi) ? b.rssi : -Infinity;
      return br - ar || String(a.address).localeCompare(String(b.address));
    });

  const tbody = $("deviceRows");

  if (!shown.length) {
    const message = devices.length
      ? "No devices match this filter. Try All signals or scan again."
      : lastStatus && lastStatus.scanning
        ? "Waiting for BLE advertisements. RSSI appears as devices are observed."
        : lastStatus && lastStatus.current_scan_time
          ? "No BLE devices were observed in this scan."
          : "No scan results yet. Start a 15-second scan to begin.";

    tbody.innerHTML = `<tr><td colspan="6" class="empty">${escapeHtml(message)}</td></tr>`;
  } else {
    tbody.innerHTML = shown.map((d) => {
      const hasRssi = Number.isFinite(d.rssi);
      const hasLastSeen = Number.isFinite(d.last_seen);
      const age = hasLastSeen ? Date.now() / 1000 - d.last_seen : Infinity;
      const stale = !hasLastSeen || age > staleAfterSeconds || d.rssi_stale;
      const rssiText = !hasRssi
        ? "Unavailable"
        : stale
          ? `Last: ${d.rssi} dBm`
          : `${d.rssi} dBm`;

      const percent = hasRssi
        ? Math.max(4, Math.min(100, (d.rssi + 100) * 1.6))
        : 0;

      const color = d.signal === "Near / Strong"
        ? "#39745e"
        : d.signal === "Medium"
          ? "#9a7132"
          : "#7b8790";

      const history = Array.isArray(d.rssi_history)
        ? d.rssi_history.filter(Number.isFinite).slice(-10)
        : [];

      const historyLabel = history.length
        ? `Recent RSSI readings in dBm: ${history.join(", ")}`
        : "No RSSI readings available";

      const historyBars = history.map((reading) => {
        const height = Math.max(12, Math.min(100, ((reading + 100) / 70) * 100));
        return `<span class="history-bar" style="height:${height}%" title="${reading} dBm" aria-hidden="true"></span>`;
      }).join("");

      const name = displayName(d.name);
      const seenTime = hasLastSeen
        ? new Date(d.last_seen * 1000).toLocaleTimeString()
        : "Unavailable";

      const seenStatus = stale ? "stale" : "current";
      const connection = d.connection_status === "Connected"
        ? "Connected"
        : "Detected";

      return `<tr class="${seenStatus}">
        <td>
          <span class="device-name ${name === "Name unavailable" ? "unknown" : ""}">${escapeHtml(name)}</span>
          <div class="section-description">${connection}</div>
        </td>
        <td><span class="address">${escapeHtml(d.address)}</span></td>
        <td>
          <div class="rssi-cell">
            <span class="rssi">${rssiText}</span>
            <span class="signal-track" aria-hidden="true">
              <span class="signal-fill" style="display:block;width:${percent}%;background:${color}"></span>
            </span>
          </div>
        </td>
        <td>
          <div class="history-bars" role="img" aria-label="${escapeHtml(historyLabel)}">
            ${historyBars || '<span class="history-unavailable">No readings</span>'}
          </div>
        </td>
        <td><span class="last-seen ${seenStatus}">${escapeHtml(seenTime)} · ${seenStatus}</span></td>
        <td><span class="badge ${bandClass(d.signal)}">${escapeHtml(d.signal || "Unknown")}</span></td>
      </tr>`;
    }).join("");
  }

  $("visibleCount").textContent = `${shown.length} of ${devices.length} devices shown`;
  $("exportBtn").classList.toggle("disabled", devices.length === 0);
  $("exportBtn").setAttribute("aria-disabled", String(devices.length === 0));
  $("exportBtn").href = `/api/export.csv?signal=${encodeURIComponent(filter)}`;
}

function renderStats(devices) {
  $("totalCount").textContent = devices.length;
  $("nearCount").textContent = devices.filter((d) => d.rssi != null && d.rssi >= -60).length;
  $("mediumCount").textContent = devices.filter((d) => d.rssi != null && d.rssi >= -75 && d.rssi < -60).length;
  $("farCount").textContent = devices.filter((d) => d.rssi != null && d.rssi < -75).length;
  $("unknownCount").textContent = devices.filter((d) => d.rssi == null).length;
}

function renderWindowsDevices(devices, checkedAt, status) {
  const list = $("windowsDeviceRows");

  const messages = {
    checking: "Windows connected-device enumeration is in progress.",
    success: devices.length
      ? `${devices.length} Windows-connected device(s) could not be safely matched to a BLE row.`
      : "Windows returned no unmatched connected-device records. This does not establish that no BLE devices are nearby.",
    timeout: "Windows connected-device enumeration timed out; no Windows name match was applied.",
    failed: "Windows connected-device enumeration failed; no Windows name match was applied.",
    unsupported: "Windows connected-device enumeration is available only on Windows.",
    not_checked: "Windows enumeration has not run."
  };

  $("windowsDeviceStatus").textContent = messages[status] || messages.not_checked;
  $("windowsCheckedAt").textContent = checkedAt
    ? `Checked ${checkedAt}`
    : status === "checking" ? "Checking…" : "Not checked";

  list.innerHTML = devices.map((device) => `
    <li>
      <span class="windows-device-name">${escapeHtml(displayName(device.name))}</span>
      <code>${escapeHtml(device.address)}</code>
      <small class="section-description">Connected to Windows · BLE signal unavailable — no verified BLE match.</small>
    </li>
  `).join("");
}

async function refreshStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error("The local service returned an error.");

    const data = await res.json();
    lastStatus = data;
    isScanning = data.scanning;

    $("scanBtn").disabled = isScanning;
    $("scanBtn").textContent = isScanning
      ? "Scanning · 15 seconds"
      : "Start 15-second scan";

    const heading = $("rssiHeading");
    if (heading) heading.textContent = isScanning ? "LIVE RSSI" : "LAST RSSI";

    document.querySelector("table").setAttribute("aria-busy", String(isScanning));

    if (data.last_error) {
      $("scanMeta").textContent = "Last scan failed. Previous results are unchanged.";
      if (lastReportedError !== data.last_error) toast(`Scan failed: ${data.last_error}`);
      lastReportedError = data.last_error;
    } else if (data.current_scan_time) {
      $("scanMeta").textContent = `Last successful scan: ${data.current_scan_time}`;
      lastReportedError = null;
    } else {
      $("scanMeta").textContent = "No successful scan yet";
    }

    renderStats(data.current_scan || []);
    renderDevices(data.current_scan || []);
    renderWindowsDevices(
      data.windows_connected_unmatched || [],
      data.windows_connected_checked_at,
      data.windows_connected_status
    );

    if (data.scanning) {
      $("scanMeta").textContent = "Live RSSI updates as BLE advertisements arrive · 15-second scan";
    }
  } catch (err) {
    $("scanMeta").textContent = err.message || "Cannot reach the local Python service. Check the terminal.";
  }
}

async function startScan() {
  if (isScanning) return;
  $("scanBtn").disabled = true;

  try {
    const res = await fetch("/api/scan", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || "Could not start scan.");

    toast("Scan started. Results will update as the scan runs.");
    await refreshStatus();
  } catch (err) {
    toast(err.message);
    $("scanBtn").disabled = false;
  }
}

async function refreshComparison() {
  try {
    const res = await fetch("/api/compare");
    if (!res.ok) throw new Error("Could not load scan comparison.");

    const data = await res.json();

    $("previousScanTime").textContent = data.previous_scan_time || "No previous scan";
    $("currentScanTime").textContent = data.current_scan_time || "No successful scan";
    $("previousScanCount").textContent = `${data.previous_count} devices`;
    $("currentScanCount").textContent = `${data.current_count} devices`;
    $("commonCount").textContent = data.previous_count === 0 ? "—" : data.common.length;
    $("newCount").textContent = data.previous_count === 0 ? "—" : data.new.length;
    $("missingCount").textContent = data.previous_count === 0 ? "—" : data.not_observed.length;

    if (data.previous_count === 0) {
      $("comparisonDetails").textContent = "Run at least two successful scans to compare results.";
      return;
    }

    const section = (title, devices) => `
      <section class="change-group">
        <h3>${title}</h3>
        ${devices.length
          ? `<ul>${devices.map((d) =>
              `<li><span>${escapeHtml(displayName(d.name))}</span><code>${escapeHtml(d.address)}</code></li>`
            ).join("")}</ul>`
          : '<p class="no-changes">None</p>'}
      </section>`;

    $("comparisonDetails").innerHTML = `
      <div class="change-list">
        ${section("Observed in both", data.common)}
        ${section("Newly observed", data.new)}
        ${section("Not observed now", data.not_observed)}
      </div>
      <p class="comparison-caveat">${escapeHtml(data.note)}</p>`;
  } catch (err) {
    $("comparisonDetails").textContent = err.message || "Could not load scan comparison.";
  }
}

$("scanBtn").addEventListener("click", startScan);
$("signalFilter").addEventListener("change", () => {
  if (lastStatus) renderDevices(lastStatus.current_scan || []);
});
$("compareBtn").addEventListener("click", refreshComparison);

refreshStatus();
refreshComparison();
setInterval(refreshStatus, 1500);
setInterval(refreshComparison, 5000);
