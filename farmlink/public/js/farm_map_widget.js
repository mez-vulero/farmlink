// Workspace map widget for farm_center_point markers
(() => {
	const MAP_CONTAINER_ID = "farmlink-farm-map";
	const DEFAULT_CENTER = { lat: 9.010793, lng: 38.761252 }; // Addis Ababa
	const LIBS = "drawing";

	let loader = null;
	let retryTimer = null;
	function loadGoogleMaps() {
		if (window.google && window.google.maps) return Promise.resolve();
		if (loader) return loader;
		const key = frappe.boot?.google_maps_api_key;
		if (!key) return Promise.reject(new Error("Missing Google Maps API key"));

		loader = new Promise((resolve, reject) => {
			const s = document.createElement("script");
			s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&libraries=${LIBS}`;
			s.async = true;
			s.onload = () => resolve();
			s.onerror = () => reject(new Error("Failed to load Google Maps"));
			document.head.appendChild(s);
		});
		return loader;
	}

	async function fetchPoints() {
		const { message } = await frappe.call({ method: "farmlink.api.get_farm_center_points" });
		return message || [];
	}

	async function render() {
		const el = getOrCreateContainer();
		if (!el) {
			scheduleRetry();
			return;
		}
		if (el.dataset.rendered) return;

		showMessage(el, "Loading map...");
		try {
			await loadGoogleMaps();
			const points = await fetchPoints();

			const centerMarkerIcon = () => ({
				path: google.maps.SymbolPath.CIRCLE,
				fillColor: "#1182c6",
				fillOpacity: 0.92,
				strokeColor: "#0f5e91",
				strokeOpacity: 0.9,
				strokeWeight: 2,
				scale: 8,
			});

			const map = new google.maps.Map(el, {
				center: DEFAULT_CENTER,
				zoom: points.length ? 6 : 12,
				mapTypeControl: false,
				streetViewControl: false,
				fullscreenControl: true,
			});

			if (points.length) {
				const bounds = new google.maps.LatLngBounds();
				points.forEach((p) => {
					const pos = new google.maps.LatLng(p.lat, p.lng);
					new google.maps.Marker({
						position: pos,
						map,
						title: p.name,
						icon: centerMarkerIcon(),
						optimized: true,
					});
					bounds.extend(pos);
				});
				map.fitBounds(bounds);
			} else {
				showMessage(el, "No farm centers found.");
			}
			el.dataset.rendered = "1";
		} catch (e) {
			console.error("Farm map render failed", e);
			showMessage(el, e?.message || "Failed to load map");
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

	$(document).ready(watch);
})();
