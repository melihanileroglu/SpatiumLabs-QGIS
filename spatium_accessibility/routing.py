"""Bounded shortest-path trees with predecessors, independent of QGIS."""
from heapq import heappush, heappop
from itertools import count
from .graph import check_cancel


def shortest_tree(graph, source, limit, cancel=None):
    distances, previous = {source: 0.0}, {}
    queue, sequence = [(0.0, 0, source)], count(1)
    while queue:
        check_cancel(cancel)
        cost, _, node = heappop(queue)
        if cost != distances.get(node):
            continue
        for other, weight in graph.get(node, []):
            candidate = cost + weight
            if candidate <= limit and candidate < distances.get(other, float('inf')):
                distances[other], previous[other] = candidate, node
                heappush(queue, (candidate, next(sequence), other))
    return distances, previous


def path_nodes(previous, source, target):
    path = [target]
    while path[-1] != source:
        if path[-1] not in previous:
            return []
        path.append(previous[path[-1]])
    return list(reversed(path))
