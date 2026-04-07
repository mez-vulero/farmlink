// FarmLink Workspace Widgets — Farm Map + Farm Area Chart (with site filter)
(() => {
	const MAP_CONTAINER_ID = "farmlink-farm-map";
	const CHART_CONTAINER_ID = "farmlink-farm-area-chart";
	const DEFAULT_CENTER = { lat: 9.010793, lng: 38.761252 }; // Addis Ababa

	let loader = null;
	let activeMap = null;
	let siteGroups = {};
	let allMarkersGroup = null;
	let currentMapSite = "";
	let areaChartInstance = null;

	function isWorkspacePage() {
		const route = frappe.get_route();
		return (
			route &&
			route[0] &&
			route[0].toLowerCase() === "workspaces" &&
			route[1] &&
			route[1].toLowerCase() === "farmlink"
		);
	}

	// ── Leaflet loader ──────────────────────────────────────────────
	function loadLeaflet() {
		if (window.L && window.L.map) return Promise.resolve();
		if (loader) return loader;
		loader = new Promise((resolve, reject) => {
			if (!document.getElementById("farmlink-leaflet-css")) {
				const link = document.createElement("link");
				link.id = "farmlink-leaflet-css";
				link.rel = "stylesheet";
				link.href = "/assets/frappe/js/lib/leaflet/leaflet.css";
				document.head.appendChild(link);
			}
			if (document.getElementById("farmlink-leaflet-js")) {
				let tries = 0;
				const t = setInterval(() => {
					if (window.L && window.L.map) { clearInterval(t); resolve(); return; }
					if (++tries > 60) { clearInterval(t); reject(new Error("Leaflet timeout")); }
				}, 50);
				return;
			}
			const s = document.createElement("script");
			s.id = "farmlink-leaflet-js";
			s.src = "/assets/frappe/js/lib/leaflet/leaflet.js";
			s.async = true;
			s.onload = () => resolve();
			s.onerror = () => reject(new Error("Failed to load Leaflet"));
			document.head.appendChild(s);
		});
		return loader;
	}

	// ── Shared helpers ──────────────────────────────────────────────
	function buildSiteSelect(id, sites, current, onChange) {
		const sel = document.createElement("select");
		sel.id = id;
		sel.style.cssText =
			"font-size:var(--text-sm);padding:4px 8px;border-radius:var(--border-radius);" +
			"border:1px solid var(--border-color);background:var(--control-bg);" +
			"color:var(--text-color);cursor:pointer;min-width:140px;";
		const allOpt = document.createElement("option");
		allOpt.value = "";
		allOpt.textContent = "All Sites";
		sel.appendChild(allOpt);
		sites.forEach((s) => {
			const opt = document.createElement("option");
			opt.value = s;
			opt.textContent = s;
			sel.appendChild(opt);
		});
		sel.value = current || "";
		sel.addEventListener("change", () => onChange(sel.value));
		return sel;
	}

	function showMessage(el, text) {
		el.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;
			height:100%;min-height:80px;color:var(--text-muted);font-size:var(--text-md);">${text}</div>`;
	}

	function findMainSection() {
		return (
			document.querySelector(".workspace .layout-main-section") ||
			document.querySelector(".page-content .layout-main-section") ||
			document.querySelector(".page-content")
		);
	}

	function makeCardHeader(title) {
		const header = document.createElement("div");
		header.style.cssText =
			"display:flex;align-items:center;justify-content:space-between;padding:var(--padding-md);";
		const h = document.createElement("div");
		h.className = "h6";
		h.style.margin = "0";
		h.textContent = title;
		const right = document.createElement("div");
		right.style.cssText = "display:flex;align-items:center;gap:6px;";
		header.appendChild(h);
		header.appendChild(right);
		return { header, right };
	}

	// ═══════════════════════════════════════════════════════════════
	//  FARM MAP WIDGET
	// ═══════════════════════════════════════════════════════════════
	function destroyMap() {
		if (activeMap) { activeMap.remove(); activeMap = null; }
		siteGroups = {};
		allMarkersGroup = null;
		const el = document.getElementById(MAP_CONTAINER_ID);
		if (el && el._leaflet_id) delete el._leaflet_id;
	}

	function buildMarkers(map, points) {
		siteGroups = {};
		allMarkersGroup = L.layerGroup().addTo(map);
		points.forEach((p) => {
			const marker = L.circleMarker(L.latLng(p.lat, p.lng), {
				radius: 6, color: "#0f5e91", weight: 2,
				fillColor: "#1182c6", fillOpacity: 0.9,
			}).bindTooltip(
				`<b>${p.name || ""}</b>${p.site ? `<br>Site: ${p.site}` : ""}`,
				{ direction: "top" }
			);
			marker._site = p.site || "";
			allMarkersGroup.addLayer(marker);
			if (p.site) {
				if (!siteGroups[p.site]) siteGroups[p.site] = [];
				siteGroups[p.site].push(marker);
			}
		});
	}

	function applyMapFilter(map, site) {
		currentMapSite = site;
		const bounds = L.latLngBounds();
		allMarkersGroup.eachLayer((marker) => {
			const show = !site || marker._site === site;
			const el = marker.getElement ? marker.getElement() : null;
			if (el) el.style.display = show ? "" : "none";
			if (show) bounds.extend(marker.getLatLng());
		});
		if (bounds.isValid()) map.fitBounds(bounds, { padding: [20, 20] });
		else map.setView([DEFAULT_CENTER.lat, DEFAULT_CENTER.lng], 7);
	}

	function getOrCreateMapCard() {
		const existing = document.getElementById(MAP_CONTAINER_ID);
		if (existing) {
			const card = existing.closest(".farmlink-map-card");
			return {
				mapEl: existing,
				headerRight: card ? card.querySelector(".farmlink-map-header-right") : null,
			};
		}
		const main = findMainSection();
		if (!main) return { mapEl: null, headerRight: null };

		const card = document.createElement("div");
		card.className = "frappe-card farmlink-map-card";
		card.style.cssText = "margin-top:var(--margin-md);padding:0;";

		const { header, right } = makeCardHeader("Farm Centers Map");
		right.className = "farmlink-map-header-right";
		card.appendChild(header);

		const mapEl = document.createElement("div");
		mapEl.id = MAP_CONTAINER_ID;
		mapEl.style.cssText = "height:420px;border-radius:0 0 var(--border-radius) var(--border-radius);overflow:hidden;";
		card.appendChild(mapEl);
		main.prepend(card);
		return { mapEl, headerRight: right };
	}

	async function renderMap() {
		const { mapEl, headerRight } = getOrCreateMapCard();
		if (!mapEl) return false;
		if (mapEl.dataset.rendering === "1" || mapEl.dataset.rendered === "1") return true;
		mapEl.dataset.rendering = "1";

		showMessage(mapEl, "Loading map...");
		try {
			await loadLeaflet();
			const data = await frappe.call({ method: "farmlink.api.get_farm_center_points" });
			const { points = [], sites = [] } = data.message || {};

			// Always build the site filter dropdown (populated from Centers)
			if (headerRight) {
				headerRight.innerHTML = "";
				const lbl = document.createElement("span");
				lbl.style.cssText = "font-size:var(--text-sm);color:var(--text-muted);";
				lbl.textContent = "Collection Site:";
				headerRight.appendChild(lbl);
				headerRight.appendChild(
					buildSiteSelect("farmlink-map-site-filter", sites, currentMapSite, (s) => {
						if (activeMap) applyMapFilter(activeMap, s);
					})
				);
			}

			if (!points.length) {
				showMessage(mapEl, "No farm center points recorded yet.");
				mapEl.dataset.rendered = "1";
				return true;
			}

			destroyMap();
			mapEl.innerHTML = "";

			const map = L.map(mapEl, { zoomControl: true, attributionControl: true });
			L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
				maxZoom: 19, attribution: "© OpenStreetMap contributors",
			}).addTo(map);
			buildMarkers(map, points);

			const bounds = L.latLngBounds(points.map((p) => [p.lat, p.lng]));
			if (bounds.isValid()) map.fitBounds(bounds, { padding: [16, 16] });
			else map.setView([DEFAULT_CENTER.lat, DEFAULT_CENTER.lng], 7);

			activeMap = map;
			mapEl.dataset.rendered = "1";
		} catch (e) {
			console.error("Farm map render failed", e);
			showMessage(mapEl, e?.message || "Failed to load map");
			mapEl.dataset.rendered = "1";
		} finally {
			delete mapEl.dataset.rendering;
		}
		return true;
	}

	// ═══════════════════════════════════════════════════════════════
	//  FARM AREA CHART WIDGET
	// ═══════════════════════════════════════════════════════════════
	function getOrCreateChartCard() {
		const existing = document.getElementById(CHART_CONTAINER_ID);
		if (existing) {
			const card = existing.closest(".farmlink-area-card");
			return {
				chartEl: existing,
				headerRight: card ? card.querySelector(".farmlink-area-header-right") : null,
			};
		}
		const main = findMainSection();
		if (!main) return { chartEl: null, headerRight: null };

		// Insert after the map card (or at top if map doesn't exist)
		const mapCard = document.querySelector(".farmlink-map-card");

		const card = document.createElement("div");
		card.className = "frappe-card farmlink-area-card";
		card.style.cssText = "margin-top:var(--margin-md);padding:0;";

		const { header, right } = makeCardHeader("Total Coffee Farm Area by Site");
		right.className = "farmlink-area-header-right";
		card.appendChild(header);

		const chartEl = document.createElement("div");
		chartEl.id = CHART_CONTAINER_ID;
		chartEl.style.cssText = "padding:0 var(--padding-md) var(--padding-md);min-height:250px;";
		card.appendChild(chartEl);

		if (mapCard && mapCard.nextSibling) {
			main.insertBefore(card, mapCard.nextSibling);
		} else if (mapCard) {
			main.appendChild(card);
		} else {
			main.prepend(card);
		}
		return { chartEl, headerRight: right };
	}

	async function renderAreaChart(site) {
		const { chartEl, headerRight } = getOrCreateChartCard();
		if (!chartEl) return;

		// Build filter dropdown (only once)
		if (headerRight && !headerRight.dataset.built) {
			headerRight.dataset.built = "1";
			const lbl = document.createElement("span");
			lbl.style.cssText = "font-size:var(--text-sm);color:var(--text-muted);";
			lbl.textContent = "Collection Site:";
			headerRight.appendChild(lbl);
			headerRight.appendChild(
				buildSiteSelect("farmlink-area-site-filter", [], "", (s) => renderAreaChart(s))
			);
		}

		showMessage(chartEl, "Loading...");
		try {
			const args = {};
			if (site) args.site = site;
			const resp = await frappe.call({ method: "farmlink.api.get_farm_area_by_site", args });
			const { data = [], sites: allSites = [] } = resp.message || {};

			// Update dropdown options if not yet populated
			const sel = document.getElementById("farmlink-area-site-filter");
			if (sel && sel.options.length <= 1 && allSites.length) {
				allSites.forEach((s) => {
					const opt = document.createElement("option");
					opt.value = s;
					opt.textContent = s;
					sel.appendChild(opt);
				});
				if (site) sel.value = site;
			}

			if (!data.length) {
				showMessage(chartEl, site
					? `No farm area data for "${site}".`
					: "No farm area data recorded yet.");
				return;
			}

			chartEl.innerHTML = "";

			const labels = data.map((d) => d.site);
			const values = data.map((d) => d.area);

			if (areaChartInstance) {
				areaChartInstance = null;
			}

			areaChartInstance = new frappe.Chart(chartEl, {
				type: "bar",
				height: 250,
				colors: ["#22c55e"],
				data: {
					labels,
					datasets: [{ name: "Hectares", values }],
				},
				axisOptions: {
					xAxisMode: "tick",
					xIsSeries: false,
				},
				barOptions: { spaceRatio: 0.4 },
				tooltipOptions: {
					formatTooltipY: (d) => `${d} ha`,
				},
			});
		} catch (e) {
			console.error("Farm area chart failed", e);
			showMessage(chartEl, e?.message || "Failed to load chart");
		}
	}

	// ═══════════════════════════════════════════════════════════════
	//  ORCHESTRATION
	// ═══════════════════════════════════════════════════════════════
	function removeWidgets() {
		destroyMap();
		document.querySelector(".farmlink-map-card")?.remove();
		document.querySelector(".farmlink-area-card")?.remove();
		areaChartInstance = null;
	}

	async function renderAll() {
		if (!isWorkspacePage()) {
			removeWidgets();
			return;
		}
		if (document.getElementById(MAP_CONTAINER_ID)?.dataset.rendered === "1") return;

		await renderMap();
		await renderAreaChart();
	}

	function watch() {
		renderAll();
		const observer = new MutationObserver(() => {
			if (isWorkspacePage() && !document.getElementById(MAP_CONTAINER_ID)) {
				renderAll();
			}
		});
		observer.observe(document.body, { childList: true, subtree: true });
		frappe.router.on("change", () => {
			const el = document.getElementById(MAP_CONTAINER_ID);
			if (el) { delete el.dataset.rendered; delete el.dataset.rendering; }
			renderAll();
		});
	}

	$(document).ready(watch);
})();
