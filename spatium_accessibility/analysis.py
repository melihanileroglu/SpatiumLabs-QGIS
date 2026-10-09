"""Native QGIS geometry implementation of the original distance algorithm."""
from math import hypot

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsSpatialIndex

from .barriers import prepare_barrier, clip_roads, blocked_point, blocked_link, clip_area
from .overlap import exclusive_rings, cumulative_from_rings

from .graph import buffer_parts, check_cancel, dijkstra, intervals, interpolate, project, split_graph


def line_geometry(a, b):
    return QgsGeometry.fromPolylineXY([QgsPointXY(*a), QgsPointXY(*b)])


def polygon(edges, distances, cutoff, offroad, cancel):
    buffers = []
    for edge in edges:
        check_cancel(cancel)
        for a, b, radius in buffer_parts(edge, distances, cutoff, offroad):
            buffers.append(line_geometry(a, b).buffer(radius, 16))
    if not buffers:
        return QgsGeometry()
    # Match the original Shapely geometry.buffer default: 16 per quadrant.
    geometry = QgsGeometry.unaryUnion(buffers)
    if geometry.isNull():
        raise ValueError("Hizmet alanı birleştirilemedi: " + geometry.lastError())
    return geometry.makeValid()


def build_network(roads, points, snap_m, cancel=None, barrier=None, reasons=None):
    """Accept value objects only; no project, layer or GUI objects in worker."""
    check_cancel(cancel)
    if not roads or not points:
        raise ValueError("Yol ve başlangıç noktaları gerekli.")
    roads = clip_roads(roads, barrier, cancel)
    noded = QgsGeometry.unaryUnion(roads)
    if noded.isNull():
        raise ValueError("Yol ağı oluşturulamadı: " + noded.lastError())
    segments = []
    geometries = noded.asGeometryCollection() if noded.isMultipart() else [noded]
    for geom in geometries:
        coords = [(p.x(), p.y()) for p in geom.asPolyline()]
        segments.extend((a, b) for a, b in zip(coords, coords[1:]) if hypot(b[0]-a[0], b[1]-a[1]) > 1e-6)
    if not segments:
        raise ValueError("Yol ağından kullanılabilir çizgi üretilemedi.")
    if len(segments) > 100000:
        raise ValueError("Geliştirme sürümünde en fazla 100.000 yol parçası destekleniyor; alanı küçültün.")
    index = QgsSpatialIndex(flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
    for i, (a, b) in enumerate(segments):
        check_cancel(cancel)
        f = QgsFeature()
        f.setId(i)
        f.setGeometry(line_geometry(a, b))
        index.addFeature(f)
    snapped, skipped = [], []
    for identifier, coord in points:
        check_cancel(cancel)
        if blocked_point(coord, barrier):
            skipped.append((identifier, coord, None))
            if reasons is not None: reasons[identifier] = 'Erişime kapalı bölge içinde'
            continue
        ids = index.nearestNeighbor(QgsPointXY(*coord), 1)
        segment = ids[0]
        offset, snapped_coord, distance = project(coord, *segments[segment])
        if blocked_link(coord, snapped_coord, barrier):
            skipped.append((identifier, coord, distance))
            if reasons is not None: reasons[identifier] = 'Yola bağlanma çizgisi kapalı bölgeden geçiyor'
        elif distance > snap_m:
            skipped.append((identifier, coord, distance))
        else:
            snapped.append({"id": identifier, "segment": segment, "offset": offset,
                            "coord": snapped_coord, "snap_m": distance})
    if not snapped:
        raise ValueError("Hiçbir nokta yol ağına bağlanamadı. Bağlanma mesafesini ve seçili kapalı bölgeleri kontrol edin.")
    graph, edges, source_nodes = split_graph(segments, snapped)
    return graph, edges, source_nodes, snapped, skipped


def calculate(roads, points, cutoffs, snap_m, offroad_m, cancel=None, progress=None, overlap=True, barriers=None):
    barrier = prepare_barrier(barriers, cancel)
    reasons = {}
    graph, edges, source_nodes, snapped, skipped = build_network(roads, points, snap_m, cancel, barrier, reasons)
    cumulative, rings, reachable = [], [], []
    total = len(snapped) * len(cutoffs)
    done = 0
    for source, node in zip(snapped, source_nodes):
        distances = dijkstra(graph, [node], cutoffs[-1], cancel)
        previous = QgsGeometry()
        lower = 0.0
        for cutoff in cutoffs:
            check_cancel(cancel)
            current = clip_area(polygon(edges, distances, cutoff, offroad_m, cancel), barrier)
            if current.isEmpty():
                lower = cutoff
                continue
            # Preserve nested areas despite midpoint approximation at cutoffs.
            if not previous.isEmpty():
                current = current.combine(previous).makeValid()
            ring = current if previous.isEmpty() else current.difference(previous).makeValid()
            if not ring.isEmpty():
                rings.append((source["id"], lower, cutoff, source["snap_m"], ring))
            cumulative.append((source["id"], 0.0, cutoff, source["snap_m"], current))
            previous, lower = current, cutoff
            done += 1
            if progress:
                progress(20 + 75 * done / total)
        for edge in edges:
            check_cancel(cancel)
            for a, b in intervals(edge, distances, cutoffs[-1]):
                reachable.append((source["id"], line_geometry(
                    interpolate(edge["a"], edge["b"], a, edge["length"]),
                    interpolate(edge["a"], edge["b"], b, edge["length"]))))
    if not cumulative:
        raise ValueError("Hizmet alanı oluşmadı. Daha büyük bir mesafe eşiği deneyin.")
    bands = []
    previous, lower = QgsGeometry(), 0.0
    for cutoff in cutoffs:
        parts = [row[4] for row in cumulative if row[2] == cutoff]
        if not parts:
            lower = cutoff
            continue
        merged = QgsGeometry.unaryUnion(parts).makeValid()
        band = merged if previous.isEmpty() else merged.difference(previous).makeValid()
        if not band.isEmpty():
            bands.append(("all", lower, cutoff, 0.0, band))
        previous, lower = merged, cutoff
    if not overlap:
        rings = exclusive_rings(rings, cancel)
        cumulative = cumulative_from_rings(rings, cutoffs)
    return {"areas": cumulative, "rings": rings, "bands": bands,
            "reachable": reachable, "snapped": snapped, "skipped": skipped, "skip_reasons": reasons}
