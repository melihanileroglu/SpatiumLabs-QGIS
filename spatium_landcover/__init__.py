"""Spatium Labs Vision: image extraction independent of Network."""

def classFactory(iface):
    from .plugin import EarthPlugin
    return EarthPlugin(iface)
