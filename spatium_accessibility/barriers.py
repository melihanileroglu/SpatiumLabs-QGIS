"""Closed polygon barriers: clip roads, block snap links and exclude output areas."""
from qgis.core import QgsGeometry, QgsPointXY
from .graph import check_cancel


def prepare_barrier(polygons, cancel=None):
    if not polygons:
        return None
    for geom in polygons:
        check_cancel(cancel)
        if geom.isEmpty() or not geom.isGeosValid():
            raise ValueError('Erişime kapalı bölge geometrisi boş veya geçersiz.')
    merged = QgsGeometry.unaryUnion(polygons)
    if merged.isNull():
        raise ValueError('Kapalı bölgeler birleştirilemedi: '+merged.lastError())
    # Close the boundary too: avoid artificial paths exactly along a restricted edge.
    closed = merged.buffer(0.01, 8)
    if closed.isNull() or closed.isEmpty():
        raise ValueError('Kapalı bölge sınırı oluşturulamadı.')
    return closed


def clip_roads(roads, barrier, cancel=None):
    if barrier is None:
        return roads
    result = []
    for road in roads:
        check_cancel(cancel)
        geom = road.difference(barrier) if road.intersects(barrier) else road
        if geom.isNull():
            raise ValueError('Yol bariyer farkı alınamadı: '+geom.lastError())
        if not geom.isEmpty(): result.append(geom)
    if not result:
        raise ValueError('Kapalı bölgelerden sonra kullanılabilir yol kalmadı.')
    return result


def blocked_point(coord, barrier):
    return barrier is not None and barrier.intersects(QgsGeometry.fromPointXY(QgsPointXY(*coord)))


def blocked_link(origin, snapped, barrier):
    if barrier is None:
        return False
    if origin == snapped:
        return blocked_point(origin, barrier)
    link = QgsGeometry.fromPolylineXY([QgsPointXY(*origin), QgsPointXY(*snapped)])
    return link.intersects(barrier)


def clip_area(geom, barrier):
    if barrier is None or geom.isEmpty():
        return geom
    result = geom.difference(barrier)
    if result.isNull():
        raise ValueError('Hizmet alanından kapalı bölgeler çıkarılamadı: '+result.lastError())
    return result.makeValid()
