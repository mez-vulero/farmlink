// Workspace map widget for farm_center_point markers
(() => {
	const MAP_CONTAINER_ID = "farmlink-farm-map";
	const DEFAULT_CENTER = { lat: 9.010793, lng: 38.761252 }; // Addis Ababa
	const LIBS = "drawing";

	let loader = null;
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
		const el = document.getElementById(MAP_CONTAINER_ID);
		if (!el || el.dataset.rendered) return;
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
			}
			el.dataset.rendered = "1";
		} catch (e) {
			console.error("Farm map render failed", e);
		}
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
