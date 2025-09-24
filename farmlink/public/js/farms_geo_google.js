// farms_geo_google.js (NO SEARCH VERSION)
// DocType: "farms"
// Fields: farm_center_point (marker), farm_polygon (polygon via DrawingManager)

// --- Stop Leaflet for just these fields anywhere (safe with global app_include_js)
console.log("farms_geo_google.js LOADED");
(function () {
  const TARGET_FIELDS = new Set(["farm_center_point", "farm_polygon"]);
  const Base = frappe.ui.form.ControlGeolocation;
  if (Base && !Base.__geo_patched) {
    const orig_make_map = Base.prototype.make_map;
    Base.prototype.make_map = function () {
      if (TARGET_FIELDS.has(this.df.fieldname)) {
        try { (this.$input_wrapper || this.$wrapper)?.find?.(".leaflet-container")?.remove?.(); } catch (e) {}
        return; // we'll render Google Maps in our form refresh handler
      }
      return orig_make_map.call(this);
    };
    Base.__geo_patched = true;
  }
})();

(function () {
  // ---------- CONFIG ----------
  const CENTER_FIELD = "farm_center_point";
  const POLY_FIELD   = "farm_polygon";
  const DEFAULT_CENTER = { lat: 9.010793, lng: 38.761252 }; // Addis Ababa
  const MAP_HEIGHT = "300px";
  const LIBS = "drawing,geometry"; // add geometry for helpers (no Places)

  // ---------- Google Maps loader ----------
  let _gmapsLoader = null;
  function loadGoogleMaps() {
    if (window.google && window.google.maps) return Promise.resolve();
    if (_gmapsLoader) return _gmapsLoader;

    const key = frappe.boot?.google_maps_api_key;
    if (!key) {
      frappe.msgprint("Google Maps API key not found on boot. Ensure boot_session sets frappe.boot.google_maps_api_key.");
      return Promise.reject(new Error("Missing Google Maps key"));
    }

    _gmapsLoader = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&libraries=${LIBS}`;
      s.async = true;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error("Failed to load Google Maps"));
      document.head.appendChild(s);
    });
    return _gmapsLoader;
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
      return ring.map(([lng, lat]) => ({ lat, lng }));
    }
    // Array of {lat,lng}
    if (Array.isArray(val) && val.length && val[0].lat != null && val[0].lng != null) {
      return val;
    }
    const p = parsePoint(val);
    return p ? [p] : null;
  }

  // ---------- serializers ----------
  function polygonToGeoJSON(path) {
    const coords = [];
    for (let i = 0; i < path.getLength(); i++) {
      const ll = path.getAt(i);
      coords.push([ll.lng(), ll.lat()]);
    }
    // close ring
    if (coords.length && (coords[0][0] !== coords[coords.length - 1][0] || coords[0][1] !== coords[coords.length - 1][1])) {
      coords.push([coords[0][0], coords[0][1]]);
    }
    return JSON.stringify({ type: "Polygon", coordinates: [coords] });
  }

  function pointToJSON(latLng) {
    return JSON.stringify({ lat: latLng.lat(), lng: latLng.lng() });
  }

  // ---------- UI helpers ----------
  function ensureMount(df, id) {
    const wrapper = df.$wrapper?.get(0);
    if (!wrapper) return null;
    const mount = wrapper.querySelector(".control-input-wrapper") || wrapper;
    mount.innerHTML = `<div id="${id}" style="height:${MAP_HEIGHT}; border-radius:8px;"></div>`;
    return document.getElementById(id);
  }

  function addControl(map, label, onClick, position = google.maps.ControlPosition.TOP_LEFT) {
    const btn = document.createElement("button");
    btn.textContent = label;
    btn.className = "btn btn-xs";
    btn.style.margin = "8px";
    btn.onclick = onClick;
    map.controls[position].push(btn);
    return btn;
  }

  // ---------- renderers ----------
  function renderCenterPoint(frm) {
    const df = frm.fields_dict[CENTER_FIELD];
    if (!df || df.df.fieldtype !== "Geolocation") return;

    const mount = ensureMount(df, `gmap_${CENTER_FIELD}`);
    if (!mount) return;

    const current = parsePoint(frm.doc[CENTER_FIELD]) || DEFAULT_CENTER;

    const map = new google.maps.Map(mount, {
      center: current,
      zoom: (current === DEFAULT_CENTER) ? 12 : 15,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: true,
    });

    const marker = new google.maps.Marker({ position: current, map, draggable: true });

    const sync = () => frm.set_value(CENTER_FIELD, pointToJSON(marker.getPosition()));
    marker.addListener("dragend", sync);
    map.addListener("click", (e) => { marker.setPosition(e.latLng); sync(); });

    // Locate me (GPS blue dot + accuracy; also updates the field)
    let myLocMarker = null, myLocCircle = null;
    addControl(map, "Locate me", () => {
      if (!navigator.geolocation) {
        frappe.msgprint("Geolocation is not available in this browser.");
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const ll = new google.maps.LatLng(pos.coords.latitude, pos.coords.longitude);

          // Show blue dot + accuracy circle
          if (!myLocMarker) {
            myLocMarker = new google.maps.Marker({
              position: ll,
              map,
              title: "You are here",
              icon: { path: google.maps.SymbolPath.CIRCLE, scale: 6 }
            });
          } else {
            myLocMarker.setPosition(ll);
          }
          const radius = pos.coords.accuracy || 50;
          if (!myLocCircle) {
            myLocCircle = new google.maps.Circle({
              map, center: ll, radius,
              strokeOpacity: 0.3, fillOpacity: 0.1
            });
          } else {
            myLocCircle.setCenter(ll);
            myLocCircle.setRadius(radius);
          }

          // Move the center marker to GPS and save
          marker.setPosition(ll);
          sync();

          map.panTo(ll);
          map.setZoom(16);
        },
        (err) => frappe.msgprint("Could not get your location: " + err.message),
        { enableHighAccuracy: true, maximumAge: 15000, timeout: 10000 }
      );
    }, google.maps.ControlPosition.TOP_RIGHT);

    // react to external changes
    frm.events[CENTER_FIELD] = function (_frm) {
      const val = parsePoint(_frm.doc[CENTER_FIELD]);
      if (val) {
        const pos = new google.maps.LatLng(val.lat, val.lng);
        marker.setPosition(pos);
        map.panTo(pos);
      }
    };

    frm.__gmaps = frm.__gmaps || {};
    frm.__gmaps.center = { map, marker, myLocMarker, myLocCircle };
  }

  function renderPolygon(frm) {
    const df = frm.fields_dict[POLY_FIELD];
    if (!df || df.df.fieldtype !== "Geolocation") return;

    const mount = ensureMount(df, `gmap_${POLY_FIELD}`);
    if (!mount) return;

    const parsed = parsePolygon(frm.doc[POLY_FIELD]);
    const center = parsed && parsed.length ? parsed[0] : (parsePoint(frm.doc[CENTER_FIELD]) || DEFAULT_CENTER);

    const map = new google.maps.Map(mount, {
      center,
      zoom: (center === DEFAULT_CENTER) ? 12 : 15,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: true,
    });

    let polygon = null;
    let drawingManager = null;
    let editMode = !!(parsed && parsed.length >= 3);
    let myLocMarker = null, myLocCircle = null;

    function savePolygon() {
      if (!polygon) { frm.set_value(POLY_FIELD, ""); return; }
      const path = polygon.getPath();
      const json = polygonToGeoJSON(path);
      if (frm.doc[POLY_FIELD] !== json) frm.set_value(POLY_FIELD, json);
    }

    function attachPathListeners(poly) {
      const path = poly.getPath();
      path.addListener("insert_at", savePolygon);
      path.addListener("remove_at", savePolygon);
      path.addListener("set_at",    savePolygon);

      // Leaflet-like: right-click vertex to delete
      google.maps.event.addListener(poly, "rightclick", (e) => {
        if (typeof e.vertex === "number") {
          path.removeAt(e.vertex);
          savePolygon();
        }
      });
    }

    // Initialize existing polygon (if any)
    if (parsed && parsed.length >= 3) {
      polygon = new google.maps.Polygon({
        paths: parsed,
        map,
        editable: true,
        draggable: false,
        geodesic: true,
      });
      attachPathListeners(polygon);
      const bounds = new google.maps.LatLngBounds();
      parsed.forEach(p => bounds.extend(p));
      map.fitBounds(bounds);
    }

    // Drawing manager (Polygon only). Double-click to finish.
    drawingManager = new google.maps.drawing.DrawingManager({
      drawingMode: parsed ? null : google.maps.drawing.OverlayType.POLYGON,
      drawingControl: false, // we'll provide our own buttons
      polygonOptions: {
        editable: true,
        draggable: false,
        geodesic: true,
      },
      map,
    });

    google.maps.event.addListener(drawingManager, "overlaycomplete", (e) => {
      if (e.type === google.maps.drawing.OverlayType.POLYGON) {
        if (polygon) polygon.setMap(null);
        polygon = e.overlay;                  // already on map
        drawingManager.setDrawingMode(null);  // stop drawing
        attachPathListeners(polygon);
        savePolygon();
        editMode = true;
        editBtn.textContent = "Edit: On";
      }
    });

    // --- Controls for Leaflet parity ---

    // Start Drawing
    const drawBtn = addControl(map, "Start Drawing", () => {
      drawingManager.setDrawingMode(google.maps.drawing.OverlayType.POLYGON);
    });

    // Edit toggle
    const editBtn = addControl(map, `Edit: ${editMode ? "On" : "Off"}`, () => {
      editMode = !editMode;
      if (polygon) polygon.setEditable(editMode);
      editBtn.textContent = `Edit: ${editMode ? "On" : "Off"}`;
    });

    // Clear polygon
    addControl(map, "Clear", () => {
      if (polygon) { polygon.setMap(null); polygon = null; }
      frm.set_value(POLY_FIELD, "");
      drawingManager.setDrawingMode(google.maps.drawing.OverlayType.POLYGON);
      editMode = false;
      editBtn.textContent = "Edit: Off";
    });

    // Locate me (device GPS blue dot + accuracy circle)
    addControl(map, "Locate me", () => {
      if (!navigator.geolocation) {
        frappe.msgprint("Geolocation is not available in this browser.");
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const ll = new google.maps.LatLng(pos.coords.latitude, pos.coords.longitude);
          if (!myLocMarker) {
            myLocMarker = new google.maps.Marker({
              position: ll,
              map,
              title: "You are here",
              icon: { path: google.maps.SymbolPath.CIRCLE, scale: 6 }
            });
          } else {
            myLocMarker.setPosition(ll);
          }
          const radius = pos.coords.accuracy || 50;
          if (!myLocCircle) {
            myLocCircle = new google.maps.Circle({
              map, center: ll, radius,
              strokeOpacity: 0.3, fillOpacity: 0.1
            });
          } else {
            myLocCircle.setCenter(ll);
            myLocCircle.setRadius(radius);
          }
          map.panTo(ll);
          map.setZoom(16);
        },
        (err) => frappe.msgprint("Could not get your location: " + err.message),
        { enableHighAccuracy: true, maximumAge: 15000, timeout: 10000 }
      );
    }, google.maps.ControlPosition.TOP_RIGHT);

    // Keep map in sync if the field changes programmatically
    frm.events[POLY_FIELD] = function (_frm) {
      const newParsed = parsePolygon(_frm.doc[POLY_FIELD]);
      if (!newParsed || newParsed.length < 3) return;

      if (polygon) polygon.setMap(null);
      polygon = new google.maps.Polygon({
        paths: newParsed, map, editable: true, draggable: false, geodesic: true
      });
      attachPathListeners(polygon);

      const bounds = new google.maps.LatLngBounds();
      newParsed.forEach(p => bounds.extend(p));
      map.fitBounds(bounds);

      editMode = true;
      editBtn.textContent = "Edit: On";
    };

    frm.__gmaps = frm.__gmaps || {};
    frm.__gmaps.poly = { map, polygon, drawingManager, myLocMarker, myLocCircle };
  }

  // ---------- wire up ----------
  // IMPORTANT: use the exact DocType name. If your doctype is lowercase "farms", keep it here.
  frappe.ui.form.on("Farms", {
    async refresh(frm) {
      try { await loadGoogleMaps(); } catch (e) { console.error(e); return; }
      renderCenterPoint(frm);
      renderPolygon(frm);
    },
    [CENTER_FIELD]: function (frm) {
      if (frm.__gmaps?.center) {
        const { map, marker } = frm.__gmaps.center;
        const p = parsePoint(frm.doc[CENTER_FIELD]);
        if (p) { const pos = new google.maps.LatLng(p.lat, p.lng); marker.setPosition(pos); map.panTo(pos); }
      }
    },
    [POLY_FIELD]: function (frm) {
      if (frm.__gmaps?.poly?.map) {
        const { map, polygon: oldPoly } = frm.__gmaps.poly;
        const newParsed = parsePolygon(frm.doc[POLY_FIELD]);
        if (!newParsed || newParsed.length < 3) return;

        if (oldPoly) oldPoly.setMap(null);
        const newPoly = new google.maps.Polygon({
          paths: newParsed, map, editable: true, draggable: false, geodesic: true
        });

        // attach listeners + save
        const path = newPoly.getPath();
        const save = () => frm.set_value(POLY_FIELD, polygonToGeoJSON(path));
        path.addListener("insert_at", save);
        path.addListener("remove_at", save);
        path.addListener("set_at",    save);

        // right-click to remove vertex
        google.maps.event.addListener(newPoly, "rightclick", (e) => {
          if (typeof e.vertex === "number") { path.removeAt(e.vertex); save(); }
        });

        frm.__gmaps.poly.polygon = newPoly;

        const bounds = new google.maps.LatLngBounds();
        newParsed.forEach(p => bounds.extend(p));
        map.fitBounds(bounds);
      }
    }
  });
})();
