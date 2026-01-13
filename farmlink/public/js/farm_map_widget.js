// Workspace map widget for farm_center_point markers (Leaflet + OSM)
(() => {
	const MAP_CONTAINER_ID = "farmlink-farm-map";
	const DEFAULT_CENTER = { lat: 9.010793, lng: 38.761252 }; // Addis Ababa

	let loader = null;
	let retryTimer = null;
	let activeMap = null;

	function isWorkspacePage() {
		const route = frappe.get_route();
		// Only render on FarmLink workspace (route: ["Workspaces", "FarmLink"])
		return (
			route &&
			route[0] &&
			route[0].toLowerCase() === "workspaces" &&
			route[1] &&
			route[1].toLowerCase() === "farmlink"
		);
	}

	function loadLeaflet() {
		if (window.L && window.L.map) return Promise.resolve();
		if (loader) return loader;

		loader = new Promise((resolve, reject) => {
			const cssId = "farmlink-leaflet-css";
			const jsId = "farmlink-leaflet-js";

			if (!document.getElementById(cssId)) {
				const link = document.createElement("link");
				link.id = cssId;
				link.rel = "stylesheet";
				link.href = "/assets/frappe/js/lib/leaflet/leaflet.css";
				document.head.appendChild(link);
			}

			if (document.getElementById(jsId)) {
				let tries = 0;
				const timer = setInterval(() => {
					if (window.L && window.L.map) {
						clearInterval(timer);
						resolve();
						return;
					}
					tries += 1;
					if (tries > 60) {
						clearInterval(timer);
						reject(new Error("Leaflet failed to load"));
					}
				}, 50);
				return;
			}

			const s = document.createElement("script");
			s.id = jsId;
			s.src = "/assets/frappe/js/lib/leaflet/leaflet.js";
			s.async = true;
			s.onload = () => resolve();
			s.onerror = () => reject(new Error("Failed to load Leaflet"));
			document.head.appendChild(s);
		});
		return loader;
	}

	function addBaseLayer(map) {
		L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
			maxZoom: 19,
			attribution: "© OpenStreetMap contributors",
		}).addTo(map);
	}

	async function fetchPoints() {
		const { message } = await frappe.call({ method: "farmlink.api.get_farm_center_points" });
		return message || [];
	}

	function destroyMap() {
		if (activeMap) {
			activeMap.remove();
			activeMap = null;
		}
		const el = document.getElementById(MAP_CONTAINER_ID);
		if (el && el._leaflet_id) delete el._leaflet_id;
	}

	async function render() {
		if (!isWorkspacePage()) {
			removeContainer();
			destroyMap();
			return;
		}

		const el = getOrCreateContainer();
		if (!el) {
			scheduleRetry();
			return;
		}
		if (el.dataset.rendering === "1" || el.dataset.rendered === "1") return;
		el.dataset.rendering = "1";

		showMessage(el, "Loading map...");
		try {
			await loadLeaflet();
			const points = await fetchPoints();

			if (!points.length) {
				showMessage(el, "No farm centers found.");
				el.dataset.rendered = "1";
				return;
			}

			destroyMap();
			el.innerHTML = "";

			const map = L.map(el, {
				zoomControl: true,
				attributionControl: true,
			});
			addBaseLayer(map);

			const bounds = L.latLngBounds();
			points.forEach((p) => {
				const pos = L.latLng(p.lat, p.lng);
				L.circleMarker(pos, {
					radius: 6,
					color: "#0f5e91",
					weight: 2,
					fillColor: "#1182c6",
					fillOpacity: 0.9,
				}).addTo(map).bindTooltip(p.name || "", { direction: "top" });
				bounds.extend(pos);
			});

			if (bounds.isValid()) {
				map.fitBounds(bounds, { padding: [16, 16] });
			} else {
				map.setView(DEFAULT_CENTER, 12);
			}

			activeMap = map;
			el.dataset.rendered = "1";
		} catch (e) {
			console.error("Farm map render failed", e);
			showMessage(el, e?.message || "Failed to load map");
			el.dataset.rendered = "1";
		} finally {
			delete el.dataset.rendering;
		}
	}

	function getOrCreateContainer() {
		// Try existing container first
		let el = document.getElementById(MAP_CONTAINER_ID);
		if (el) return el;

		// Find a sensible workspace content area to append to
		const main =
			document.querySelector(".workspace .layout-main-section") ||
			document.querySelector(".page-content .layout-main-section") ||
			document.querySelector(".page-content");
		if (!main) return null;

		// Build a simple card wrapper for the map
		const card = document.createElement("div");
		card.className = "frappe-card";
		card.style.marginTop = "var(--margin-md)";
		card.style.padding = "0";

		const header = document.createElement("div");
		header.className = "frappe-card-header";
		header.style.display = "flex";
		header.style.alignItems = "center";
		header.style.justifyContent = "space-between";
		header.style.padding = "var(--padding-md)";
		header.innerHTML = `<div class="h6" style="margin:0">Farm Centers Map</div>`;
		card.appendChild(header);

		el = document.createElement("div");
		el.id = MAP_CONTAINER_ID;
		el.style.height = "420px";
		el.style.borderRadius = "0 0 var(--border-radius) var(--border-radius)";
		el.style.overflow = "hidden";
		card.appendChild(el);

		main.prepend(card);
		return el;
	}

	function showMessage(el, text) {
		el.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:var(--text-md);">${text}</div>`;
	}

	function scheduleRetry() {
		if (retryTimer) return;
		retryTimer = setTimeout(() => {
			retryTimer = null;
			render();
		}, 300);
	}

	function watch() {
		render();
		const observer = new MutationObserver(() => render());
		observer.observe(document.body, { childList: true, subtree: true });
		// also re-render on route change
		frappe.router.on("change", () => render());
	}

	function removeContainer() {
		const el = document.getElementById(MAP_CONTAINER_ID);
		if (el) {
			const card = el.closest(".frappe-card");
			if (card) card.remove();
			else el.remove();
		}
	}

	$(document).ready(watch);
})();
