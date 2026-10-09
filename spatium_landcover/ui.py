"""Earth workbench design, kept consistent with the Network plugin."""
from html import escape
from qgis.PyQt.QtCore import QByteArray, QRectF
from qgis.PyQt.QtGui import QPainter
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import QWidget

STYLE = '\nQDialog#spatiumWorkbench { background: #f1f5f9; color: #172b42; font-size: 11px; }\nQFrame#header { background: #102c42; border-radius: 9px; }\nQLabel#brand { color: #ffffff; font-size: 18px; font-weight: 700; }\nQLabel#subtitle { color: #a9c7d9; font-size: 11px; }\nQLabel#badge { color: #a8f0dc; background: #1a4657; border-radius: 4px; padding: 6px 12px; }\nQFrame#card { background: #ffffff; border: 1px solid #d8e2ec; border-radius: 8px; }\nQLabel#section { color: #142f45; font-size: 13px; font-weight: 600; }\nQLabel#hint { color: #62778c; font-size: 11px; }\nQLabel#metric { color: #167e76; font-size: 26px; font-weight: 700; }\nQTabWidget::pane { border: 0; }\nQTabBar::tab { padding: 8px 14px; background: #e7edf4; color: #5a7087; margin-right: 5px; border-radius: 5px; }\nQTabBar::tab:selected { background: #ffffff; color: #167e76; font-weight: 600; }\nQLineEdit, QComboBox, QDoubleSpinBox { min-height: 22px; padding: 3px 7px; border: 1px solid #cbd8e5; border-radius: 4px; background: #fff; color: #172b42; }\nQLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus { border-color: #18998a; }\nQCheckBox { color: #294258; spacing: 8px; }\nQPushButton { min-height: 24px; padding: 4px 14px; border-radius: 5px; border: 1px solid #c9d6e2; background: #ffffff; color: #26455c; }\nQPushButton:hover { background: #eaf4f2; border-color: #16998a; }\nQPushButton#primary { background: #168a7d; color: #ffffff; border: 0; font-weight: 600; }\nQPushButton#primary:hover { background: #10766b; }\nQPushButton:disabled { color: #9aacba; background: #e5ecf2; border-color: #d6e0e8; }\nQTableWidget { background: #ffffff; color: #172b42; border: 1px solid #d8e2ec; gridline-color: #edf2f7; }\nQHeaderView::section { background: #eaf0f6; color: #38536b; border: 0; padding: 8px; font-weight: 600; }\nQProgressBar { border: 0; background: #e3ecf3; border-radius: 4px; height: 8px; }\nQProgressBar::chunk { background: #168a7d; border-radius: 4px; }\nQScrollArea { border: 0; background: transparent; }\nQTextBrowser { background: #ffffff; color: #294258; border: 1px solid #d8e2ec; padding: 14px; }\n\nQGroupBox { background: white; color: #142f45; font-size: 13px; font-weight: 600; border: 1px solid #d8e2ec; border-radius: 8px; margin-top: 10px; padding: 16px 12px 12px; }\nQGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 4px; }\nQLabel { color: #294258; font-size: 11px; }\nQPushButton#swatch { min-height: 15px; min-width: 22px; max-width: 22px; padding: 2px; }\n'

def preview_svg(classes):
    colors={c['id']:c['color'] for c in classes}
    def color(i): return escape(colors.get(i,'#dce5ed'),quote=True)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="170" viewBox="0 0 300 170">
    <rect width="300" height="170" rx="9" fill="#edf3f6"/>
    <path d="M8 8H128V65H8Z" fill="{color(7)}"/>
    <path d="M162 8H292V60H162Z" fill="{color(4)}"/>
    <path d="M8 110H108V162H8Z" fill="{color(3)}"/>
    <path d="M178 105H292V162H178Z" fill="{color(2)}"/>
    <path d="M114 170L138 0H158L134 170Z M0 72H300V98H0Z" fill="{color(5)}"/>
    <path d="M174 110H222V140H174Z" fill="{color(7)}"/>
    <path d="M235 110H290V140H235Z" fill="{color(8)}"/>
    <g fill="{color(1)}" stroke="#ffffff" stroke-width="2">
      <path d="M18 16H52V45H18Z M65 16H101V50H65Z"/>
    </g></svg>'''

class CoverPreview(QWidget):
    def __init__(self):
        super().__init__(); self.classes=[]; self.setMinimumHeight(170)
    def setClasses(self, classes):
        self.classes=classes; self.update()
    def paintEvent(self, event):
        renderer=QSvgRenderer(QByteArray(preview_svg(self.classes).encode()))
        painter=QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        width=min(self.width(),300); height=width*170/300
        renderer.render(painter,QRectF((self.width()-width)/2,(self.height()-height)/2,width,height)); painter.end()
