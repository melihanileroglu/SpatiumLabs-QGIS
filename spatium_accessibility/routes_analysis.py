"""Metric walking route analyses, using the same noded/snap model as service area."""
from qgis.core import QgsGeometry, QgsPointXY
from .analysis import build_network
from .graph import check_cancel
from .routing import shortest_tree, path_nodes


def calculate_routes(roads, origins, targets, snap, limit, mode, same_layer=False, cancel=None, progress=None):
    points = [('O:'+sid,coord) for sid,coord in origins] + [('T:'+sid,coord) for sid,coord in targets]
    graph, edges, nodes, snapped, skipped = build_network(roads, points, snap, cancel)
    node_by_id = {s['id']: n for s,n in zip(snapped,nodes)}
    coords = {}
    for edge in edges:
        coords[edge['u']],coords[edge['v']] = edge['a'],edge['b']
    rows=[]
    for i,(sid,_) in enumerate(origins):
        check_cancel(cancel)
        origin=node_by_id.get('O:'+sid)
        distances,previous=shortest_tree(graph,origin,limit,cancel) if origin is not None else ({},{})
        candidates=[]
        for tid,_ in targets:
            if same_layer and sid == tid and mode != 'shortest':
                continue
            target=node_by_id.get('T:'+tid)
            distance=distances.get(target)
            status='ok' if distance is not None else ('snap_failed' if origin is None or target is None else 'unreachable_or_over_limit')
            geom=QgsGeometry()
            if distance is not None and mode != 'matrix':
                path=path_nodes(previous,origin,target)
                route=[QgsPointXY(*coords[n]) for n in path]
                if len(route)==1: route.append(QgsPointXY(route[0]))
                geom=QgsGeometry.fromPolylineXY(route)
            candidates.append((sid,tid,distance,status,geom))
        if mode=='nearest':
            valid=[r for r in candidates if r[3]=='ok']
            rows.append(min(valid,key=lambda r:r[2]) if valid else (sid,'',None,'snap_failed' if origin is None else 'no_facility_within_limit',QgsGeometry()))
        else:
            rows.extend(candidates)
        if progress: progress(20+75*(i+1)/len(origins))
    return {'routes':rows,'snapped':snapped,'skipped':skipped}
