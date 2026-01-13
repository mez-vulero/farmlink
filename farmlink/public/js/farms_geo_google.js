// farms_geo_google.js (OSM/Leaflet version)
// DocType: "Farms"
// Fields: farm_center_point (marker), farm_polygon (polygon)

// Ensure Leaflet replaces the default geolocation control for Farms
(function () {
  const TARGET_FIELDS = new Set(["farm_center_point", "farm_polygon"]);
  const Base = frappe.ui.form.ControlGeolocation;
  if (Base && !Base.__farmlink_patched) {
    Base.__farmlink_orig_make_map = Base.prototype.make_map;
    Base.__farmlink_orig_bind_leaflet_data = Base.prototype.bind_leaflet_data;
    Base.prototype.make_map = function () {
      if (cur_frm?.doctype === "Farms" && TARGET_FIELDS.has(this.df.fieldname)) {
        try {
          (this.$input_wrapper || this.$wrapper)?.find?.(".leaflet-container")?.remove?.();
        } catch (e) {}
        return; // custom renderer will handle it
      }
      return Base.__farmlink_orig_make_map.call(this);
    };
    Base.prototype.bind_leaflet_data = function (value) {
      if (cur_frm?.doctype === "Farms" && TARGET_FIELDS.has(this.df.fieldname)) {
        return;
      }
      return Base.__farmlink_orig_bind_leaflet_data.call(this, value);
    };
    Base.__farmlink_patched = true;
  }
})();

(function () {
  // ---------- CONFIG ----------
  const CENTER_FIELD = "farm_center_point";
  const POLY_FIELD = "farm_polygon";
  const DEFAULT_CENTER = { lat: 9.010793, lng: 38.761252 }; // Addis Ababa
  const MAP_HEIGHT = "300px";

  // ---------- Leaflet loader ----------
  let _leafletLoader = null;
  function loadLeaflet() {
    if (window.L && window.L.map) return Promise.resolve();
    if (_leafletLoader) return _leafletLoader;

    _leafletLoader = new Promise((resolve, reject) => {
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

    return _leafletLoader;
  }

  function addBaseLayer(map) {
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors",
    }).addTo(map);
  }

  // ---------- value parsers ----------
  function parsePoint(val) {
    if (!val) return null;
    if (typeof val === "object") return (val.lat != null && val.lng != null) ? val : null;
    try {
      const o = JSON.parse(val);
      if (o && (("lat" in o) || ("latitude" in o)) && (("lng" in o) || ("longitude" in o))) {
        return { lat: o.lat ?? o.latitude, lng: o.lng ?? o.longitude };
      }
    } catch {}
    if (typeof val === "string") {
      const m = val.match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/);
      if (m) {
        return { lat: parseFloat(m[1]), lng: parseFloat(m[2]) };
      }
    }
    return null;
  }

  function parsePolygon(val) {
    if (!val) return null;
    if (typeof val === "string") {
      try { val = JSON.parse(val); } catch { return null; }
    }
    // GeoJSON Polygon -> [{lat,lng}, ...]
    if (val && val.type === "Polygon" && Array.isArray(val.coordinates) && Array.isArray(val.coordinates[0])) {
      const ring = val.coordinates[0]; // [[lng,lat],...]
      const cleaned = ring.slice();
      if (cleaned.length > 1) {
        const first = cleaned[0];
        const last = cleaned[cleaned.length - 1];
        if (first[0] === last[0] && first[1] === last[1]) cleaned.pop();
      }
      return cleaned.map(([lng, lat]) => ({ lat, lng }));
    }
    // Array of {lat,lng}
    if (Array.isArray(val) && val.length && val[0].lat != null && val[0].lng != null) {
      return val;
    }
    const p = parsePoint(val);
    return p ? [p] : null;
  }

  // ---------- serializers ----------
  function polygonToGeoJSON(latlngs) {
    const coords = [];
    for (let i = 0; i < latlngs.length; i++) {
      const ll = latlngs[i];
      coords.push([ll.lng, ll.lat]);
    }
    // close ring
    if (coords.length && (coords[0][0] !== coords[coords.length - 1][0] || coords[0][1] !== coords[coords.length - 1][1])) {
      coords.push([coords[0][0], coords[0][1]]);
    }
    return JSON.stringify({ type: "Polygon", coordinates: [coords] });
  }

  function pointToJSON(latLng) {
    if (!latLng) return "";
    const lat = (typeof latLng.lat === "function") ? latLng.lat() : latLng.lat;
    const lng = (typeof latLng.lng === "function") ? latLng.lng() : latLng.lng;
    return JSON.stringify({ lat, lng });
  }

  // ---------- UI helpers ----------
  function ensureMount(df, id) {
    const wrapper = df.$wrapper?.get(0);
    if (!wrapper) return null;
    const mount = wrapper.querySelector(".control-input-wrapper") || wrapper;
    mount.innerHTML = `<div id="${id}" style="height:${MAP_HEIGHT}; border-radius:8px;"></div>`;
    return document.getElementById(id);
  }

  function showFieldMessage(df, text) {
    const wrapper = df?.$wrapper?.get(0);
    if (!wrapper) return;
    const mount = wrapper.querySelector(".control-input-wrapper") || wrapper;
    mount.innerHTML = `<div class="text-muted" style="padding:6px 0;">${text}</div>`;
  }

  function addControl(map, label, onClick, position = "topleft") {
    const Control = L.Control.extend({
      onAdd: function () {
        const btn = L.DomUtil.create("button", "btn btn-xs");
        btn.type = "button";
        btn.textContent = label;
        L.DomEvent.disableClickPropagation(btn);
        L.DomEvent.disableScrollPropagation(btn);
        L.DomEvent.on(btn, "click", (e) => {
          L.DomEvent.preventDefault(e);
          onClick();
        });
        return btn;
      },
    });
    const control = new Control({ position });
    control.addTo(map);
    return control;
  }

  function vertexIcon() {
    return L.divIcon({
      className: "farmlink-vertex-icon",
      html: '<div style="width:10px;height:10px;border:2px solid #1182c6;border-radius:50%;background:#ffffff"></div>',
      iconSize: [10, 10],
      iconAnchor: [5, 5],
    });
  }

  function nearestSegmentInsertIndex(latlngs, point, map, thresholdPx = 10) {
    if (latlngs.length < 2) return latlngs.length;
    let bestIdx = latlngs.length;
    let bestDist = Infinity;

    const p = map.latLngToLayerPoint(point);
    for (let i = 0; i < latlngs.length; i++) {
      const a = map.latLngToLayerPoint(latlngs[i]);
      const b = map.latLngToLayerPoint(latlngs[(i + 1) % latlngs.length]);
      const ax = a.x, ay = a.y;
      const bx = b.x, by = b.y;
      const dx = bx - ax;
      const dy = by - ay;
      const len2 = dx * dx + dy * dy || 1;
      let t = ((p.x - ax) * dx + (p.y - ay) * dy) / len2;
      t = Math.max(0, Math.min(1, t));
      const projX = ax + t * dx;
      const projY = ay + t * dy;
      const dist2 = (p.x - projX) * (p.x - projX) + (p.y - projY) * (p.y - projY);
      if (dist2 < bestDist) {
        bestDist = dist2;
        bestIdx = i + 1;
      }
    }
    if (Math.sqrt(bestDist) > thresholdPx) return null;
    return bestIdx;
  }

  // ---------- renderers ----------
  function renderCenterPoint(frm) {
    const df = frm.fields_dict[CENTER_FIELD];
    if (!df || df.df.fieldtype !== "Geolocation") return;

    const mount = ensureMount(df, `osm_${CENTER_FIELD}`);
    if (!mount) return;

    if (frm.__farmlink_maps?.center?.map) {
      frm.__farmlink_maps.center.map.remove();
    }

    const current = parsePoint(frm.doc[CENTER_FIELD]) || DEFAULT_CENTER;

    const map = L.map(mount, {
      zoomControl: true,
      attributionControl: true,
    });
    addBaseLayer(map);
    map.setView(current, current === DEFAULT_CENTER ? 12 : 15);

    const marker = L.marker(current, { draggable: true }).addTo(map);

    const sync = () => frm.set_value(CENTER_FIELD, pointToJSON(marker.getLatLng()));
    marker.on("dragend", sync);
    map.on("click", (e) => { marker.setLatLng(e.latlng); sync(); });

    // Locate me (GPS blue dot + accuracy; also updates the field)
    let myLocMarker = null;
    let myLocCircle = null;
    addControl(map, "Locate me", () => {
      if (!navigator.geolocation) {
        frappe.msgprint("Geolocation is not available in this browser.");
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const ll = L.latLng(pos.coords.latitude, pos.coords.longitude);

          if (!myLocMarker) {
            myLocMarker = L.circleMarker(ll, { radius: 6, color: "#2563eb", fillOpacity: 0.9 }).addTo(map);
          } else {
            myLocMarker.setLatLng(ll);
          }
          const radius = pos.coords.accuracy || 50;
          if (!myLocCircle) {
            myLocCircle = L.circle(ll, { radius, color: "#2563eb", opacity: 0.3, fillOpacity: 0.1 }).addTo(map);
          } else {
            myLocCircle.setLatLng(ll);
            myLocCircle.setRadius(radius);
          }

          marker.setLatLng(ll);
          sync();

          map.panTo(ll);
          map.setZoom(16);
        },
        (err) => frappe.msgprint("Could not get your location: " + err.message),
        { enableHighAccuracy: true, maximumAge: 15000, timeout: 10000 }
      );
    }, "topright");

    setTimeout(() => map.invalidateSize(), 0);

    // react to external changes
    frm.events[CENTER_FIELD] = function (_frm) {
      const val = parsePoint(_frm.doc[CENTER_FIELD]);
      if (val) {
        marker.setLatLng(val);
        map.panTo(val);
      }
    };

    frm.__farmlink_maps = frm.__farmlink_maps || {};
    frm.__farmlink_maps.center = { map, marker, myLocMarker, myLocCircle };
  }

  function renderPolygon(frm) {
    const df = frm.fields_dict[POLY_FIELD];
    if (!df || df.df.fieldtype !== "Geolocation") return;

    const mount = ensureMount(df, `osm_${POLY_FIELD}`);
    if (!mount) return;

    if (frm.__farmlink_maps?.poly?.map) {
      frm.__farmlink_maps.poly.map.remove();
    }

    const parsed = parsePolygon(frm.doc[POLY_FIELD]);
    const center = parsed && parsed.length ? parsed[0] : (parsePoint(frm.doc[CENTER_FIELD]) || DEFAULT_CENTER);

    const map = L.map(mount, {
      zoomControl: true,
      attributionControl: true,
    });
    addBaseLayer(map);
    map.setView(center, center === DEFAULT_CENTER ? 12 : 15);

    frm.__farmlink_maps = frm.__farmlink_maps || {};
    frm.__farmlink_maps.poly = frm.__farmlink_maps.poly || {};
    frm.__farmlink_maps.poly.map = map;

    let polygon = null;
    let drawing = false;
    let drawPoints = [];
    let draftLine = null;
    let editMode = !!(parsed && parsed.length >= 3);
    let vertexMarkers = [];
    let myLocMarker = null;
    let myLocCircle = null;

    function savePolygon() {
      if (!polygon) { frm.set_value(POLY_FIELD, ""); return; }
      const latlngs = (polygon.getLatLngs()[0] || []).map((ll) => ({ lat: ll.lat, lng: ll.lng }));
      const json = polygonToGeoJSON(latlngs);
      if (frm.doc[POLY_FIELD] !== json) frm.set_value(POLY_FIELD, json);
    }

    function setPolygon(latlngs, opts = {}) {
      if (polygon) polygon.remove();
      polygon = L.polygon(latlngs, {
        color: "#1182c6",
        weight: 2,
        fillOpacity: 0.2,
      }).addTo(map);
      frm.__farmlink_maps.poly.polygon = polygon;
      if (!opts.skipSave) savePolygon();
      refreshVertexMarkers();
    }

    function clearPolygon() {
      if (polygon) polygon.remove();
      polygon = null;
      frm.__farmlink_maps.poly.polygon = null;
      refreshVertexMarkers();
      frm.set_value(POLY_FIELD, "");
    }

    function setDrawing(active) {
      drawing = active;
      if (drawing) {
        drawPoints = [];
        if (draftLine) draftLine.remove();
        draftLine = L.polyline([], { color: "#1182c6", weight: 2, dashArray: "4,6" }).addTo(map);
        map.doubleClickZoom.disable();
      } else {
        if (draftLine) draftLine.remove();
        draftLine = null;
        map.doubleClickZoom.enable();
      }
    }

    function finishDrawing() {
      if (drawPoints.length >= 3) {
        setPolygon(drawPoints);
        editMode = true;
        updateEditLabel();
      }
      setDrawing(false);
    }

    function refreshVertexMarkers() {
      vertexMarkers.forEach((m) => m.remove());
      vertexMarkers = [];
      if (!polygon || !editMode) return;

      const latlngs = polygon.getLatLngs()[0] || [];
      latlngs.forEach((ll, idx) => {
        const marker = L.marker(ll, { draggable: true, icon: vertexIcon() }).addTo(map);
        marker.on("drag", () => {
          latlngs[idx] = marker.getLatLng();
          polygon.setLatLngs([latlngs]);
        });
        marker.on("dragend", () => savePolygon());
        marker.on("contextmenu", (e) => {
          if (e.originalEvent) L.DomEvent.stop(e.originalEvent);
          latlngs.splice(idx, 1);
          if (latlngs.length < 3) {
            clearPolygon();
            return;
          }
          polygon.setLatLngs([latlngs]);
          savePolygon();
          refreshVertexMarkers();
        });
        marker.on("click", (e) => {
          if (e.originalEvent) L.DomEvent.stop(e.originalEvent);
        });
        vertexMarkers.push(marker);
      });
    }

    function updateEditLabel() {
      if (editBtn && editBtn.getContainer) {
        const el = editBtn.getContainer();
        if (el) el.textContent = `Edit: ${editMode ? "On" : "Off"}`;
      }
    }

    function insertVertex(latlng) {
      if (!polygon || !editMode || drawing) return;
      const latlngs = polygon.getLatLngs()[0] || [];
      if (latlngs.length < 2) return;
      const insertAt = nearestSegmentInsertIndex(latlngs, latlng, map);
      if (insertAt == null) return;
      latlngs.splice(insertAt, 0, latlng);
      polygon.setLatLngs([latlngs]);
      savePolygon();
      refreshVertexMarkers();
    }

    map.on("click", (e) => {
      if (drawing) {
        drawPoints.push(e.latlng);
        if (draftLine) draftLine.setLatLngs(drawPoints);
        return;
      }
      insertVertex(e.latlng);
    });

    map.on("dblclick", (e) => {
      if (!drawing) return;
      if (e.originalEvent) L.DomEvent.stop(e.originalEvent);
      finishDrawing();
    });

    // Initialize existing polygon (if any)
    if (parsed && parsed.length >= 3) {
      setPolygon(parsed, { skipSave: true });
      const bounds = L.latLngBounds(parsed.map((p) => [p.lat, p.lng]));
      map.fitBounds(bounds, { padding: [16, 16] });
    }

    // --- Controls ---
    const drawBtn = addControl(map, "Start Drawing", () => setDrawing(true));
    const editBtn = addControl(map, `Edit: ${editMode ? "On" : "Off"}`, () => {
      editMode = !editMode;
      updateEditLabel();
      refreshVertexMarkers();
    });
    addControl(map, "Clear", () => {
      clearPolygon();
      setDrawing(true);
      editMode = false;
      updateEditLabel();
    });

    // Locate me (device GPS blue dot + accuracy circle)
    addControl(map, "Locate me", () => {
      if (!navigator.geolocation) {
        frappe.msgprint("Geolocation is not available in this browser.");
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const ll = L.latLng(pos.coords.latitude, pos.coords.longitude);
          if (!myLocMarker) {
            myLocMarker = L.circleMarker(ll, { radius: 6, color: "#2563eb", fillOpacity: 0.9 }).addTo(map);
          } else {
            myLocMarker.setLatLng(ll);
          }
          const radius = pos.coords.accuracy || 50;
          if (!myLocCircle) {
            myLocCircle = L.circle(ll, { radius, color: "#2563eb", opacity: 0.3, fillOpacity: 0.1 }).addTo(map);
          } else {
            myLocCircle.setLatLng(ll);
            myLocCircle.setRadius(radius);
          }
          map.panTo(ll);
          map.setZoom(16);
        },
        (err) => frappe.msgprint("Could not get your location: " + err.message),
        { enableHighAccuracy: true, maximumAge: 15000, timeout: 10000 }
      );
    }, "topright");

    setTimeout(() => map.invalidateSize(), 0);

    // Keep map in sync if the field changes programmatically
    frm.events[POLY_FIELD] = function (_frm) {
      const newParsed = parsePolygon(_frm.doc[POLY_FIELD]);
      if (!newParsed || newParsed.length < 3) return;
      setPolygon(newParsed, { skipSave: true });
      const bounds = L.latLngBounds(newParsed.map((p) => [p.lat, p.lng]));
      map.fitBounds(bounds, { padding: [16, 16] });
      editMode = true;
      updateEditLabel();
    };

    frm.__farmlink_maps = frm.__farmlink_maps || {};
    frm.__farmlink_maps.poly = { map, polygon, drawBtn, editBtn, myLocMarker, myLocCircle };
  }

  // ---------- wire up ----------
  // IMPORTANT: use the exact DocType name.
  frappe.ui.form.on("Farms", {
    async refresh(frm) {
      try {
        await loadLeaflet();
      } catch (e) {
        console.warn("[farmlink] Leaflet unavailable for Farms geolocation.", e?.message || e);
        showFieldMessage(frm.fields_dict[CENTER_FIELD], e?.message || "Leaflet failed to load");
        showFieldMessage(frm.fields_dict[POLY_FIELD], e?.message || "Leaflet failed to load");
        return;
      }
      renderCenterPoint(frm);
      renderPolygon(frm);
    },
  });
})();
