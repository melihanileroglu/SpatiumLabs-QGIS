"""Partition rings by distance band, then input point order (stable priority)."""

def exclusive_rings(rows, cancel=None):
    occupied = None
    result = []
    # Python's stable sort preserves input point order for equal thresholds.
    for row in sorted(rows, key=lambda r: r[2]):
        if cancel and cancel():
            raise RuntimeError('Analiz iptal edildi.')
        geom = row[4] if occupied is None else row[4].difference(occupied).makeValid()
        if geom.isNull():
            raise ValueError('Örtüşmeyen alan üretilemedi: ' + geom.lastError())
        if geom.isEmpty():
            continue
        result.append((*row[:4], geom))
        occupied = geom if occupied is None else occupied.combine(geom).makeValid()
        if occupied.isNull():
            raise ValueError('Alan birleştirilemedi: ' + occupied.lastError())
    return result


def cumulative_from_rings(rows, cutoffs):
    result = []
    for sid in dict.fromkeys(r[0] for r in rows):
        previous = None
        snap = next(r[3] for r in rows if r[0] == sid)
        for cutoff in cutoffs:
            parts = [r[4] for r in rows if r[0] == sid and r[2] == cutoff]
            for geom in parts:
                previous = geom if previous is None else previous.combine(geom).makeValid()
            if previous is not None and not previous.isEmpty():
                result.append((sid, 0.0, cutoff, snap, previous))
    return result
