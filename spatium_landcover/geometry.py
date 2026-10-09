"""Metric polygon generalization with shared-edge coverage support."""
from math import isfinite

def tolerance_for(job,gsd):
    pixels=float(job.get('smooth_pixels',1.5))
    if not isfinite(pixels) or not 0<=pixels<=5: raise ValueError('Sınır sadeleştirme 0–5 piksel arasında olmalı.')
    if not isfinite(gsd) or gsd<=0: raise ValueError('Piksel çözünürlüğü sonlu ve pozitif olmalı.')
    tolerance=float(job.get('simplify',pixels*gsd))
    if not isfinite(tolerance) or tolerance<0: raise ValueError('Geçersiz sadeleştirme toleransı.')
    return tolerance

def vertex_count(geometries):
    from shapely import get_num_coordinates
    return sum(int(get_num_coordinates(g)) for g in geometries)

def generalize(features,aoi,tolerance,minimum):
    from shapely.geometry import shape,mapping,GeometryCollection
    from shapely import coverage_is_valid,coverage_simplify,make_valid
    from .worker import polygon_parts
    raw=[shape(f['geometry']) for f in features]
    before=vertex_count(raw)
    if not raw or tolerance==0: return features,{'method':'none','vertices_before':before,'vertices_after':before,'tolerance_m':tolerance}
    if not isfinite(tolerance) or tolerance<0: raise ValueError('Sadeleştirme toleransı sonlu ve pozitif olmalı.')
    if coverage_is_valid(raw):
        geometries=coverage_simplify(raw,tolerance,simplify_boundary=True);method='coverage_visvalingam'
    else:
        # Different per-class pixel grids may not have matching shared vertices.
        geometries=[g.simplify(tolerance,preserve_topology=True) for g in raw];method='topology_preserving'
    result=[];accepted=GeometryCollection()
    for feature,geometry in zip(features,geometries):
        geometry=make_valid(geometry).intersection(aoi).difference(accepted)
        retained=[]
        for part in polygon_parts(geometry):
            if part.area<minimum: continue
            retained.append(part)
            properties=dict(feature['properties']);properties.update(object_id=len(result)+1,area_m2=part.area)
            result.append({'geometry':mapping(part),'properties':properties})
        for part in retained: accepted=accepted.union(part)
    after=vertex_count([shape(f['geometry']) for f in result])
    return result,{'method':method,'vertices_before':before,'vertices_after':after,'tolerance_m':tolerance}
