const canvas = document.getElementById("arena");
const ctx = canvas.getContext("2d");
const hud = document.getElementById("hud");
const badge = document.getElementById("trial-badge");
const proto = location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(`${proto}://${location.host}/ws`);

let state = null;
let pointerMm = null;
let ptrDirty = false;

ws.onmessage = (ev) => {
	state = JSON.parse(ev.data);
	syncHint(state);
	draw();
	renderHud();
};

function sendJson(obj) {
	if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

function syncHint(s) {
	const el = document.querySelector(".hint");
	if (!el) return;
	if (s.ferret_source === "ace") {
		const n = (s.ace_blobs || []).length;
		el.textContent = n
			? `Spectator HUD. Ace labels ${n} blob(s) on the arena (gold=ferret, teal=toy).`
			: "Spectator HUD. Live Ace ferret + Zaber toy run on the ace-zaber thread; this window cannot add grab or serial lag.";
	} else if (s.zaber && s.zaber.backend === "hardware") {
		el.textContent = "Pointer is the ferret (no Ace delay). Toy is the X-MCC encoder. Start trial (S) to chase.";
	}
}

canvas.addEventListener("mousemove", (e) => {
	if (!state) return;
	// Why: live Ace owns the ferret; pointer must not override the blob.
	if (state.ferret_source === "ace") return;
	const r = canvas.getBoundingClientRect();
	const nx = (e.clientX - r.left) / r.width;
	const ny = (e.clientY - r.top) / r.height;
	pointerMm = {
		x_mm: nx * state.arena.width_mm,
		y_mm: ny * state.arena.height_mm,
	};
	// Why: draw locally now; rAF batches WS so serial chase is not flooded.
	ptrDirty = true;
	draw();
});

function pumpPointer() {
	requestAnimationFrame(pumpPointer);
	if (!ptrDirty || !pointerMm) return;
	ptrDirty = false;
	sendJson({ type: "pointer", ...pointerMm });
}
pumpPointer();

document.querySelectorAll("[data-trial]").forEach((btn) => {
	btn.addEventListener("click", () => sendJson({ type: "trial", cmd: btn.dataset.trial }));
});

window.addEventListener("keydown", (e) => {
	const k = e.key.toLowerCase();
	if (k === "s") sendJson({ type: "trial", cmd: "start" });
	if (k === "e") sendJson({ type: "trial", cmd: "end" });
	if (k === "r") sendJson({ type: "trial", cmd: "reset" });
});

function mmToPx(x, y) {
	const a = state.arena;
	return [(x / a.width_mm) * canvas.width, (y / a.height_mm) * canvas.height];
}

function draw() {
	if (!state) return;
	const w = canvas.width;
	const h = canvas.height;
	ctx.fillStyle = "#0d0f0c";
	ctx.fillRect(0, 0, w, h);
	drawGrid();
	drawTravel();
	drawThreatRings();
	drawCone();
	drawFlee();
	drawGhost();
	drawPrey();
	drawFerret();
	drawAceIds();
}

function drawGrid() {
	ctx.strokeStyle = "#22261e";
	ctx.lineWidth = 1;
	for (let i = 0; i <= 8; i++) {
		const x = (i / 8) * canvas.width;
		const y = (i / 8) * canvas.height;
		ctx.beginPath();
		ctx.moveTo(x, 0);
		ctx.lineTo(x, canvas.height);
		ctx.stroke();
		ctx.beginPath();
		ctx.moveTo(0, y);
		ctx.lineTo(canvas.width, y);
		ctx.stroke();
	}
}

function drawThreatRings() {
	const f = state.ferret_camera;
	if (!f.valid) return;
	const [cx, cy] = mmToPx(f.x_mm, f.y_mm);
	const gsd = canvas.width / state.arena.width_mm;
	const pref = state.policy.preferred_gap_mm || state.policy.threat_distance_mm;
	const minG = state.policy.min_gap_mm || pref * 0.4;
	ctx.strokeStyle = "rgba(226,184,74,0.35)";
	circle(cx, cy, pref * gsd);
	ctx.strokeStyle = "rgba(211,107,94,0.3)";
	circle(cx, cy, minG * gsd);
}

function drawTravel() {
	// Why: travel is mapped onto the full FOV; box is the scaled rail window.
	const z = state.zaber;
	if (!z || z.x_max == null || z.y_max == null) return;
	const [x0, y0] = mmToPx(z.x_min || 0, z.y_min || 0);
	const [x1, y1] = mmToPx(z.x_max, z.y_max);
	ctx.strokeStyle = "rgba(126,200,196,0.5)";
	ctx.lineWidth = 2;
	ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
	const m = state.policy.wall_margin_mm || 0;
	if (m <= 0) return;
	const [ix0, iy0] = mmToPx((z.x_min || 0) + m, (z.y_min || 0) + m);
	const [ix1, iy1] = mmToPx(z.x_max - m, z.y_max - m);
	ctx.strokeStyle = "rgba(126,200,196,0.22)";
	ctx.lineWidth = 1;
	ctx.strokeRect(ix0, iy0, ix1 - ix0, iy1 - iy0);
}

function drawCone() {
	// Soft keep-away no longer uses cone-of-impact flees.
}

function drawFlee() {
	// No discrete flee target marker.
}

function drawGhost() {
	const f = state.ferret_camera;
	if (!f.valid) return;
	const [x, y] = mmToPx(f.x_mm, f.y_mm);
	ctx.fillStyle = "#8a7a4a";
	ctx.globalAlpha = 0.55;
	blob(x, y, 10);
	ctx.globalAlpha = 1;
}

function drawFerret() {
	const f = state.ferret_true;
	// Why: pointer hybrid should not wait for the next HUD snapshot.
	const src = state.ferret_source !== "ace" && pointerMm
		? { x_mm: pointerMm.x_mm, y_mm: pointerMm.y_mm, direction_deg: f.direction_deg, valid: true }
		: f;
	if (!src.valid) return;
	const [x, y] = mmToPx(src.x_mm, src.y_mm);
	ctx.fillStyle = "#e2b84a";
	blob(x, y, 8);
	heading(x, y, src.direction_deg, "#e2b84a");
}

function drawPrey() {
	const p = state.prey;
	const [x, y] = mmToPx(p.x_mm, p.y_mm);
	ctx.fillStyle = "#7ec8c4";
	ctx.beginPath();
	if (ctx.roundRect) {
		ctx.roundRect(x - 8, y - 5, 16, 10, 3);
	} else {
		ctx.rect(x - 8, y - 5, 16, 10);
	}
	ctx.fill();
	heading(x, y, p.direction_deg, "#7ec8c4");
	labelAt(x, y + 20, "encoder", "#7ec8c4");
}

function drawAceIds() {
	// Why: show Ace's ferret vs toy labels on the arena, not only chase markers.
	const blobs = state.ace_blobs || [];
	for (const b of blobs) {
		if (b.x_mm == null || b.y_mm == null) continue;
		const [x, y] = mmToPx(b.x_mm, b.y_mm);
		const color = aceColor(b.label);
		ctx.strokeStyle = color;
		ctx.lineWidth = 2;
		circle(x, y, 18);
		labelAt(x, y, `Ace ${b.label}`, color);
	}
}

function aceColor(label) {
	if (label === "ferret") return "#e2b84a";
	if (label === "toy") return "#7ec8c4";
	return "#9aa190";
}

function labelAt(x, y, text, color) {
	ctx.font = "12px ui-monospace, monospace";
	ctx.lineWidth = 3;
	ctx.strokeStyle = "#0d0f0c";
	ctx.strokeText(text, x + 14, y - 12);
	ctx.fillStyle = color;
	ctx.fillText(text, x + 14, y - 12);
}

function blob(x, y, r) {
	ctx.beginPath();
	ctx.arc(x, y, r, 0, Math.PI * 2);
	ctx.fill();
}

function circle(x, y, r) {
	ctx.beginPath();
	ctx.arc(x, y, r, 0, Math.PI * 2);
	ctx.stroke();
}

function heading(x, y, deg, color) {
	const rad = (-deg * Math.PI) / 180;
	ctx.strokeStyle = color;
	ctx.beginPath();
	ctx.moveTo(x, y);
	ctx.lineTo(x + Math.cos(rad) * 22, y + Math.sin(rad) * 22);
	ctx.stroke();
}

function renderHud() {
	// Why split: keep each HUD block under 45 lines.
	const s = state;
	badge.textContent = s.trial;
	badge.className = "badge " + s.trial;
	hud.innerHTML = hudCamera(s) + hudZaber(s) + hudAnimals(s) + hudDecision(s);
}

function ferretSourceLabel(s) {
	if (s.ferret_source === "ace") return "live Ace blob";
	if (s.zaber && s.zaber.backend === "hardware") return "pointer (no Ace delay)";
	return "pointer delay model";
}

function hudCamera(s) {
	const c = s.camera;
	return `
		<h2>Basler / pylon</h2>
		${row("ferret source", ferretSourceLabel(s), s.ferret_source === "ace" || (s.zaber && s.zaber.backend === "hardware") ? "ok" : "")}
		${row("animal", (s.animal && s.animal.animal) ? `${s.animal.animal} (${s.animal.backend})` : "ferret", s.animal && s.animal.animal === "sphero" ? "ok" : "")}
		${row("this window", "spectator — chase is not on this socket", "ok")}
		${row("model", c.model)}
		${row("backend", c.backend || "sim", c.backend === "pylon" ? "ok" : "")}
		${row("format", `${c.pixel_format} ${s.arena.width_px}×${s.arena.height_px}`)}
		${row("fps cap", c.fps.toFixed(0))}
		${row("exposure", c.exposure_us.toFixed(0) + " µs")}
		${row("USB transfer", c.usb_transfer_ms.toFixed(2) + " ms")}
		${row("MOG2/track", c.tracking_pipeline_ms.toFixed(2) + " ms")}
		${row("grab→host", c.grab_to_host_ms.toFixed(2) + " ms")}
		${row("grab→frame", c.last_grab_to_frame_ms.toFixed(2) + " ms")}
		${row("strategy", c.strategy)}
		${row("delivered / dropped", `${c.delivered} / ${c.dropped}`)}
		${row("GSD", s.arena.gsd_mm_per_px + " mm/px")}
		${row("FOV", `${s.arena.width_mm.toFixed(0)} × ${s.arena.height_mm.toFixed(0)} mm`)}
	`;
}

function hudZaber(s) {
	const z = s.zaber;
	return `
		<h2>Zaber API</h2>
		${row("backend", z.backend || "sim", z.backend === "hardware" ? "ok" : "")}
		${z.loop_error ? row("loop error", z.loop_error, "warn") : ""}
		${row("link", z.comm + " RTT " + z.rtt_ms.toFixed(1) + " ms")}
		${row("busy", String(z.busy), z.busy ? "warn" : "ok")}
		${row("position", `${z.x_mm.toFixed(1)}, ${z.y_mm.toFixed(1)} mm`)}
		${row("encoder", `${(z.enc_x_mm != null ? z.enc_x_mm : z.x_mm).toFixed(1)}, ${(z.enc_y_mm != null ? z.enc_y_mm : z.y_mm).toFixed(1)} mm`)}
		${row("encoder frame", "rails scaled to Ace/Charuco FOV")}
		${row("travel", `rails ${(z.enc_x_min != null ? z.enc_x_min : 0).toFixed(0)}–${(z.enc_x_max != null ? z.enc_x_max : z.x_max).toFixed(0)} × ${(z.enc_y_min != null ? z.enc_y_min : 0).toFixed(0)}–${(z.enc_y_max != null ? z.enc_y_max : z.y_max).toFixed(0)} mm`)}
		${row("velocity", `${z.speed_mm_s.toFixed(0)} mm/s  ${z.heading_deg.toFixed(0)}°`)}
		${row("limits", `${z.max_speed_mm_s} mm/s · ${z.max_accel_mm_s2} mm/s²`)}
		<ul class="calls">${z.api_calls.map((a) => `<li>${a.name} ${esc(a.detail)}</li>`).join("")}</ul>
	`;
}

function hudAnimals(s) {
	const sc = s.scene;
	return `
		<h2>Ferret (camera detection)</h2>
		${row(s.ferret_source === "ace" ? "Ace track" : "world pointer", s.ferret_true.valid ? fmtTrack(s.ferret_true) : "not seen")}
		${row("Ace confidence", (sc.ferret_confidence || 0).toFixed(2), sc.ferret_confidence >= 0.5 ? "ok" : "")}
		${row("camera px→mm", fmtTrack(s.ferret_camera))}
		${row("camera px", s.ferret_camera.valid ? `${s.ferret_camera.x_px.toFixed(0)}, ${s.ferret_camera.y_px.toFixed(0)} px` : "not seen")}
		${aceBlobRows(s)}
		<h2>Toy (Zaber encoder)</h2>
		${row("state", fmtTrack(s.prey))}
		${row("gap", sc.distance_mm.toFixed(0) + " mm")}
		${row("bearing", sc.bearing_deg.toFixed(0) + "°")}
		${row("closing", sc.closing_speed_mm_s.toFixed(0) + " mm/s")}
	`;
}

function hudDecision(s) {
	const d = s.decision;
	return `
		<h2>Chase decision @ ${s.control_hz.toFixed(0)} Hz</h2>
		<div class="reason">${esc(d.reason)}</div>
		${row("preferred gap", (s.policy.preferred_gap_mm || 0).toFixed(0) + " mm")}
		${row("gap error", (d.gap_error_mm || 0).toFixed(0) + " mm (+: too close)")}
		${row("wall push", (d.wall_push || 0).toFixed(2))}
		${row("cmd v", `${d.vx_mm_s.toFixed(0)}, ${d.vy_mm_s.toFixed(0)} mm/s`)}
		${row("cap", (s.policy.max_engage_speed_mm_s || 0).toFixed(0) + " mm/s")}
		${row("policy compute", d.compute_ms.toFixed(3) + " ms")}
		${row("stale stops", String(d.stale_stops), d.stale_stops ? "warn" : "")}
	`;
}

function row(k, v, cls) {
	return `<div class="row"><span class="k">${k}</span><span class="v ${cls || ""}">${v}</span></div>`;
}

function aceBlobRows(s) {
	const blobs = s.ace_blobs || [];
	if (!blobs.length) return row("Ace blobs", "none this frame");
	return blobs.map((b) => row(
		`Ace ${b.label}`,
		`${(b.x_mm || 0).toFixed(0)}, ${(b.y_mm || 0).toFixed(0)} mm · ${(b.x_px || 0).toFixed(0)}, ${(b.y_px || 0).toFixed(0)} px`,
		b.label === "ferret" ? "ok" : "",
	)).join("");
}

function fmtTrack(t) {
	return `${t.x_mm.toFixed(0)}, ${t.y_mm.toFixed(0)} mm · ${t.speed_mm_s.toFixed(0)} mm/s · ${t.direction_deg.toFixed(0)}°`;
}

function esc(s) {
	return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}
