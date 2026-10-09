# Spatium Labs Network

Walking network analysis for QGIS 3.28–3.x. Public preview 0.5.0. GPL-2.0-or-later.

## Install and use

Install the ZIP in **Plugins → Manage and Install Plugins → Install from ZIP**.
Enable **Spatium Labs Network**, then open **Spatium Labs → Network**.
No additional Python packages or accounts are needed for local analysis.

1. Choose Service area, Shortest path, Nearest facility, or Origin–destination table.
2. Choose your road line layer or OpenStreetMap, and the origin point layer.
3. Select a unique point identifier and any target layer needed by the analysis.
4. For service areas enter distances such as `400, 800` in metres.
5. Select polygon barriers if needed; choose overlapping or exclusive outputs.
6. Run the analysis; save to a new GeoPackage or keep temporary project layers.

Service areas have **one ring polygon layer**, with bands `0–400` and `400–800`,
not separate cumulative 0–800 outputs. Colours are editable in the dialog.
The built-in synthetic test dataset can be loaded from the interface.

## Model and limits

Distances are calculated in a local metric UTM CRS. Roads are planar and
bidirectional: this is a walking distance model, not vehicle traffic routing.
Road snapping is reported but its offset is not charged to network distance.
Off-road reach is a buffered approximation, not terrain or door-to-door travel.
Polygon barriers cut service-area roads, exclude blocked origins/snapping links
and are removed from output rings. Barriers do not apply to route/OD analyses.
Bridge/tunnel/grade-separated roads are excluded from downloaded OSM roads;
local layers require explicit confirmation that planar intersections are valid.
Driving one-way rules, turn restrictions, traffic speeds and travel times are not modeled.

OSM requests send the bounding box to https://overpass-api.de and require internet.
Maximum OSM extent: 0.15° × 0.15°; response: 25 MB. Network: 100,000 segments.
Distance thresholds: at most 10, each at most 10,000 m. OD: at most 100 × 100.
OpenStreetMap data is © OpenStreetMap contributors, ODbL:
https://www.openstreetmap.org/copyright . Local road data is not uploaded.

## Türkçe

Yol ve başlangıç katmanlarını seçin, metre cinsinden eşikleri girin ve analizi
çalıştırın. Hizmet alanı tek katmanda ardışık halkalar üretir. Kapalı bölge
poligonları isteğe bağlıdır. Yerel analiz internet gerektirmez; OSM gerektirir.
Bu sürüm çift yönlü yaya mesafesi hesaplar; araç hızı ve trafik modeli değildir.

Support and bug reports: https://github.com/melihanileroglu/SpatiumLabs-QGIS/issues
Include QGIS/OS versions, chosen analysis and a minimal reproducible synthetic example.
Do not upload confidential or licensed data to issues.
