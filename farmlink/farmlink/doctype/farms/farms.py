# Copyright (c) 2025, vulerotech and contributors
# For license information, please see license.txt

import json
import math

from frappe.model.document import Document

# WGS84 mean Earth radius in meters. The polygons we capture are small (<10 ha
# of coffee farm) so an equirectangular projection with a cosine-of-mean-lat
# scale factor is accurate to well under 0.1% — plenty for hectare reporting.
EARTH_RADIUS_M = 6_371_008.8


class Farms(Document):
	def validate(self):
		self._recompute_polygon_area()

	def _recompute_polygon_area(self):
		"""Compute polygon_area_ha from farm_polygon (GeoJSON FeatureCollection).

		Server-side recompute makes the area canonical regardless of what the
		mobile client sent — protects against client-side rounding drift and
		gives reports a single source of truth.
		"""
		raw = self.get("farm_polygon")
		if not raw:
			self.polygon_area_ha = 0
			return

		try:
			data = json.loads(raw) if isinstance(raw, str) else raw
		except (ValueError, TypeError):
			return

		ring = _first_polygon_ring(data)
		if not ring or len(ring) < 4:
			# A valid GeoJSON Polygon needs at least 4 positions (3 + closing).
			self.polygon_area_ha = 0
			return

		self.polygon_area_ha = round(_polygon_area_hectares(ring), 4)


def _first_polygon_ring(geojson):
	"""Return the outer ring [[lng, lat], ...] from the first Polygon feature, or None."""
	if not isinstance(geojson, dict):
		return None

	features = geojson.get("features") if geojson.get("type") == "FeatureCollection" else [geojson]
	for feature in features or []:
		geometry = feature.get("geometry") if feature.get("type") == "Feature" else feature
		if not isinstance(geometry, dict):
			continue
		if geometry.get("type") != "Polygon":
			continue
		coords = geometry.get("coordinates")
		if isinstance(coords, list) and coords and isinstance(coords[0], list):
			return coords[0]
	return None


def _polygon_area_hectares(ring):
	"""Shoelace on an equirectangular projection. ring = [[lng, lat], ...] in degrees."""
	if len(ring) < 3:
		return 0.0

	mean_lat_rad = math.radians(sum(p[1] for p in ring) / len(ring))
	cos_mean_lat = math.cos(mean_lat_rad)

	xs = [math.radians(p[0]) * EARTH_RADIUS_M * cos_mean_lat for p in ring]
	ys = [math.radians(p[1]) * EARTH_RADIUS_M for p in ring]

	area_m2 = 0.0
	n = len(ring)
	for i in range(n):
		j = (i + 1) % n
		area_m2 += xs[i] * ys[j] - xs[j] * ys[i]
	return abs(area_m2) / 2.0 / 10_000.0
