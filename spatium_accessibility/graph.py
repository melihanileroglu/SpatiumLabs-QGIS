"""Distance model ported from service_area.py, independent of QGIS.

Input segments must already be noded. Walking is bidirectional; snap distance
is reported but is not charged, matching the original application.
"""
from heapq import heappop, heappush
from itertools import count
from math import hypot, isfinite


class Cancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel and cancel():
        raise Cancelled("Analiz iptal edildi.")


def parse_distances(text):
    try:
        values = sorted(set(float(v.strip()) for v in text.split(",")))
    except (ValueError, AttributeError):
        raise ValueError("Mesafeleri virgülle ayırın: 400, 800")
    if not values or len(values) > 10 or any(not isfinite(v) or v <= 0 or v > 10000 for v in values):
        raise ValueError("1–10 eşik girin; her eşik 0 ile 10.000 metre arasında olmalı.")
    return values


def node_key(point):
    return tuple(round(float(v), 3) for v in point)


def project(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = hypot(dx, dy)
    if not length:
        raise ValueError("Sıfır uzunluklu yol parçası.")
    t = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length**2))
    snapped = (a[0] + t * dx, a[1] + t * dy)
    return t * length, snapped, hypot(point[0] - snapped[0], point[1] - snapped[1])


def interpolate(a, b, offset, length):
    t = offset / length
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def split_graph(segments, sources):
    splits = {}
    for source in sources:
        splits.setdefault(source["segment"], set()).add(source["offset"])
    graph, edges, source_nodes = {}, [], []

    def key(index, offset, a, b, length):
        if offset <= 1e-6:
            return node_key(a)
        if length - offset <= 1e-6:
            return node_key(b)
        # Mixed key types require a tie-break sequence in Dijkstra.
        return ("split", index, float(offset))

    for index, (a, b) in enumerate(segments):
        length = hypot(b[0] - a[0], b[1] - a[1])
        if length <= 1e-6:
            continue
        offsets = sorted({0.0, length} | splits.get(index, set()))
        for start, end in zip(offsets, offsets[1:]):
            if end - start <= 1e-6:
                continue
            u, v = key(index, start, a, b, length), key(index, end, a, b, length)
            graph.setdefault(u, []).append((v, end - start))
            graph.setdefault(v, []).append((u, end - start))
            edges.append({"u": u, "v": v, "length": end - start,
                          "a": interpolate(a, b, start, length), "b": interpolate(a, b, end, length)})
    for source in sources:
        a, b = segments[source["segment"]]
        source_nodes.append(key(source["segment"], source["offset"], a, b, hypot(b[0]-a[0], b[1]-a[1])))
    return graph, edges, source_nodes


def dijkstra(graph, sources, cutoff, cancel=None):
    distances, queue = {}, []
    sequence = count()
    for source in sources:
        distances[source] = 0.0
        heappush(queue, (0.0, next(sequence), source))
    while queue:
        check_cancel(cancel)
        cost, _, node = heappop(queue)
        if cost != distances.get(node):
            continue
        for neighbor, weight in graph.get(node, []):
            next_cost = cost + weight
            if next_cost <= cutoff and next_cost < distances.get(neighbor, float("inf")):
                distances[neighbor] = next_cost
                heappush(queue, (next_cost, next(sequence), neighbor))
    return distances


def intervals(edge, distances, cutoff):
    length = edge["length"]
    du, dv = distances.get(edge["u"], float("inf")), distances.get(edge["v"], float("inf"))
    parts = []
    if du < cutoff:
        parts.append((0.0, min(length, cutoff - du)))
    if dv < cutoff:
        parts.append((max(0.0, length - (cutoff - dv)), length))
    parts = sorted((a, b) for a, b in parts if b - a > 1e-6)
    if len(parts) == 2 and parts[1][0] <= parts[0][1] + 1e-6:
        return [(parts[0][0], max(parts[0][1], parts[1][1]))]
    return parts


def buffer_parts(edge, distances, cutoff, offroad, chunk=25.0):
    """Original 25m midpoint-buffer approximation, including remaining cost."""
    for start, end in intervals(edge, distances, cutoff):
        cursor = start
        while cursor < end - 1e-6:
            following = min(end, cursor + chunk)
            mid = (cursor + following) / 2.0
            cost = min(distances.get(edge["u"], float("inf")) + mid,
                       distances.get(edge["v"], float("inf")) + edge["length"] - mid)
            radius = min(offroad, max(0.0, cutoff - cost))
            if radius > 0.5:
                yield (interpolate(edge["a"], edge["b"], cursor, edge["length"]),
                       interpolate(edge["a"], edge["b"], following, edge["length"]), radius)
            cursor = following
