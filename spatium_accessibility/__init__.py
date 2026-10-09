"""QGIS plugin entry point; geometry libraries load only inside QGIS."""


def classFactory(iface):
    from .plugin import AccessibilityPlugin
    return AccessibilityPlugin(iface)
