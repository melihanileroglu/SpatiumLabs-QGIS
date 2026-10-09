"""Professional native Qt workbench, using QGIS layer/field selectors."""
from qgis.PyQt.QtWidgets import (QAbstractItemView, QColorDialog, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QProgressBar, QScrollArea, QTabWidget, QTableWidget, QTextBrowser, QVBoxLayout, QWidget)
from qgis.PyQt.QtCore import Qt, QByteArray, QRectF
from qgis.PyQt.QtGui import QColor, QPainter
from qgis.PyQt.QtSvg import QSvgRenderer
from .preview import svg, legend_html
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox


STYLE = """
QDialog#spatiumWorkbench { background: #f1f5f9; color: #172b42; font-size: 11px; }
QFrame#header { background: #102c42; border-radius: 9px; }
QLabel#brand { color: #ffffff; font-size: 18px; font-weight: 700; }
QLabel#subtitle { color: #a9c7d9; font-size: 11px; }
QLabel#badge { color: #a8f0dc; background: #1a4657; border-radius: 4px; padding: 6px 12px; }
QFrame#card { background: #ffffff; border: 1px solid #d8e2ec; border-radius: 8px; }
QLabel#section { color: #142f45; font-size: 13px; font-weight: 600; }
QLabel#hint { color: #62778c; font-size: 11px; }
QLabel#metric { color: #167e76; font-size: 26px; font-weight: 700; }
QTabWidget::pane { border: 0; }
QTabBar::tab { padding: 8px 14px; background: #e7edf4; color: #5a7087; margin-right: 5px; border-radius: 5px; }
QTabBar::tab:selected { background: #ffffff; color: #167e76; font-weight: 600; }
QLineEdit, QComboBox, QDoubleSpinBox { min-height: 22px; padding: 3px 7px; border: 1px solid #cbd8e5; border-radius: 4px; background: #fff; color: #172b42; }
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus { border-color: #18998a; }
QCheckBox { color: #294258; spacing: 8px; }
QPushButton { min-height: 24px; padding: 4px 14px; border-radius: 5px; border: 1px solid #c9d6e2; background: #ffffff; color: #26455c; }
QPushButton:hover { background: #eaf4f2; border-color: #16998a; }
QPushButton#primary { background: #168a7d; color: #ffffff; border: 0; font-weight: 600; }
QPushButton#primary:hover { background: #10766b; }
QPushButton:disabled { color: #9aacba; background: #e5ecf2; border-color: #d6e0e8; }
QTableWidget { background: #ffffff; color: #172b42; border: 1px solid #d8e2ec; gridline-color: #edf2f7; }
QHeaderView::section { background: #eaf0f6; color: #38536b; border: 0; padding: 8px; font-weight: 600; }
QProgressBar { border: 0; background: #e3ecf3; border-radius: 4px; height: 8px; }
QProgressBar::chunk { background: #168a7d; border-radius: 4px; }
QScrollArea { border: 0; background: transparent; }
QTextBrowser { background: #ffffff; color: #294258; border: 1px solid #d8e2ec; padding: 14px; }
"""


class AreaPreview(QWidget):
    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin
        self.setFixedHeight(174)

    def paintEvent(self, event):
        renderer = QSvgRenderer(QByteArray(svg(self.plugin.analysis_type.currentIndex(),
            self.plugin.band_colors, self.plugin.cutoffs.text()).encode('utf-8')))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width = min(self.width(), 260)
        height = width * 174 / 260
        renderer.render(painter, QRectF((self.width()-width)/2, (174-height)/2, width, height))
        painter.end()


def label(text, name=None):
    item = QLabel(text)
    item.setWordWrap(True)
    if name:
        item.setObjectName(name)
    return item


def card(title, hint):
    frame = QFrame()
    frame.setObjectName('card')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)
    layout.addWidget(label(title, 'section'))
    layout.addWidget(label(hint, 'hint'))
    form = QFormLayout()
    form.setHorizontalSpacing(20)
    form.setVerticalSpacing(7)
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    layout.addLayout(form)
    return frame, layout, form


def build_dialog(plugin):
    dialog = QDialog(plugin.iface.mainWindow())
    dialog.setObjectName('spatiumWorkbench')
    dialog.setWindowTitle('Spatium Labs | Network · Hizmet alanı')
    dialog.resize(980, 740)
    dialog.setMinimumSize(800, 620)
    dialog.setStyleSheet(STYLE)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(22, 18, 22, 18)
    root.setSpacing(10)
    header = QFrame()
    header.setObjectName('header')
    head = QHBoxLayout(header)
    head.setContentsMargins(16, 12, 16, 12)
    titles = QVBoxLayout()
    titles.addWidget(label('SPATIUM LABS  /  Network', 'brand'))
    titles.addWidget(label('Hizmet alanı · Yaya ağı', 'subtitle'))
    from .branding import Logo, icon
    dialog.setWindowIcon(icon())
    head.addWidget(Logo(48))
    head.addLayout(titles, 1)
    head.addWidget(label('YAYA  ·  MESAFE', 'badge'))
    root.addWidget(header)

    tabs = QTabWidget()
    plugin.tabs = tabs
    root.addWidget(tabs, 1)
    setup = QWidget()
    tabs.addTab(setup, 'Analiz')
    setup_layout = QHBoxLayout(setup)
    setup_layout.setContentsMargins(0, 14, 0, 0)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    content = QWidget()
    cards = QVBoxLayout(content)
    cards.setContentsMargins(0, 0, 8, 0)
    cards.setSpacing(12)
    scroll.setWidget(content)
    setup_layout.addWidget(scroll, 3)
    plugin.input_panel = content

    frame, layout, form = card('Veri', 'Yol kaynağını ve başlangıç noktalarını seçin.')
    plugin.analysis_type = QComboBox()
    plugin.analysis_type.addItems(['Hizmet alanı', 'En kısa yol', 'En yakın tesis', 'Başlangıç–hedef mesafe tablosu'])
    form.addRow('Analiz türü', plugin.analysis_type)
    plugin.source = QComboBox()
    plugin.source.addItems(['Kullanıcı yol ağı', 'OpenStreetMap'])
    form.addRow('Veri kaynağı', plugin.source)
    plugin.roads = QgsMapLayerComboBox()
    plugin.roads.setFilters(QgsMapLayerProxyModel.LineLayer)
    form.addRow('Yol ağı katmanı', plugin.roads)
    plugin.import_button = QPushButton('Yol verisi ekle…')
    plugin.import_button.clicked.connect(plugin.import_roads)
    form.addRow('', plugin.import_button)
    plugin.points = QgsMapLayerComboBox()
    plugin.points.setFilters(QgsMapLayerProxyModel.PointLayer)
    form.addRow('Başlangıç katmanı', plugin.points)
    plugin.id_field = QgsFieldComboBox()
    plugin.id_field.setAllowEmptyFieldName(True)
    plugin.id_field.setLayer(plugin.points.currentLayer())
    plugin.id_field.setField('')
    plugin.id_field.setToolTip('Benzersiz durak/tesis kimliği. Boşsa QGIS özellik kimliği kullanılır.')
    form.addRow('Benzersiz kimlik alanı', plugin.id_field)
    plugin.points.layerChanged.connect(plugin.id_field.setLayer)
    plugin.selected = QCheckBox('Yalnızca seçili başlangıçlar')
    form.addRow('', plugin.selected)
    plugin.targets_panel = QWidget()
    target_form = QFormLayout(plugin.targets_panel)
    target_form.setContentsMargins(0, 0, 0, 0)
    plugin.targets = QgsMapLayerComboBox()
    plugin.targets.setFilters(QgsMapLayerProxyModel.PointLayer)
    target_form.addRow('Hedef / tesis katmanı', plugin.targets)
    plugin.target_id = QgsFieldComboBox()
    plugin.target_id.setAllowEmptyFieldName(True)
    plugin.target_id.setLayer(plugin.targets.currentLayer())
    plugin.target_id.setField('')
    plugin.targets.layerChanged.connect(plugin.target_id.setLayer)
    target_form.addRow('Hedef kimlik alanı', plugin.target_id)
    plugin.target_selected = QCheckBox('Yalnızca seçili hedefler')
    target_form.addRow('', plugin.target_selected)
    target_form.addRow(label('En kısa yolda başlangıç ve hedef noktalarını aşağıdan seçin. Aynı katman kullanılırsa en yakın tesis ve tablo analizlerinde noktanın kendisi hariç tutulur.', 'hint'))
    plugin.origin_feature = QComboBox()
    plugin.target_feature = QComboBox()
    plugin.endpoint_panel = QWidget()
    endpoint_form = QFormLayout(plugin.endpoint_panel)
    endpoint_form.setContentsMargins(0, 0, 0, 0)
    endpoint_form.addRow('Başlangıç noktası', plugin.origin_feature)
    endpoint_form.addRow('Hedef noktası', plugin.target_feature)
    layout.addWidget(plugin.targets_panel)
    layout.addWidget(plugin.endpoint_panel)
    cards.addWidget(frame)

    frame, layout, form = card('Analiz ayarları', 'Yaya ağı üzerinde metre cinsinden mesafe hesabı.')
    plugin.service_panel = QWidget()
    service_form = QFormLayout(plugin.service_panel)
    service_form.setContentsMargins(0, 0, 0, 0)
    form.addRow(plugin.service_panel)
    plugin.cutoffs = QLineEdit('400, 800')
    plugin.cutoffs.setPlaceholderText('Örnek: 400, 800, 1200')
    service_form.addRow('Mesafe eşikleri', plugin.cutoffs)
    plugin.overlap = QComboBox()
    plugin.overlap.addItems(['Örtüşmeye izin ver', 'Örtüşmeyi kaldır'])
    plugin.overlap.setToolTip('Farklı noktaların alanları. Örtüşme kaldırılırken küçük mesafe bandı; eşit bantta girdi nokta sırası önceliklidir.')
    service_form.addRow('Poligon örtüşmesi', plugin.overlap)
    plugin.route_limit_panel = QWidget()
    route_form = QFormLayout(plugin.route_limit_panel)
    route_form.setContentsMargins(0, 0, 0, 0)
    plugin.route_limit = QDoubleSpinBox()
    plugin.route_limit.setRange(1, 10000)
    plugin.route_limit.setValue(3000)
    plugin.route_limit.setSuffix(' m')
    route_form.addRow('Azami ağ mesafesi', plugin.route_limit)
    route_form.addRow(label('Limit içindeki yaya rotaları hesaplanır. Bulunamayan mesafeler boş bırakılır ve durum alanında açıklanır.', 'hint'))
    form.addRow(plugin.route_limit_panel)
    plugin.use_barriers = QCheckBox('Erişime kapalı bölgeleri dışla')
    plugin.barrier_layer = QgsMapLayerComboBox()
    plugin.barrier_layer.setFilters(QgsMapLayerProxyModel.PolygonLayer)
    plugin.barrier_layer.setAllowEmptyLayer(True)
    plugin.barrier_layer.setLayer(None)
    plugin.barrier_layer.setEnabled(False)
    plugin.use_barriers.toggled.connect(plugin.barrier_layer.setEnabled)
    service_form.addRow(plugin.use_barriers)
    service_form.addRow('Kapalı bölge katmanı', plugin.barrier_layer)
    service_form.addRow(label('Askeri alan, şantiye veya özel mülk: yollar, yola bağlantılar ve sonuç alanları kapalı poligonlardan geçmez.', 'hint'))
    advanced_toggle = QCheckBox('Gelişmiş ağ ayarları')
    form.addRow('', advanced_toggle)
    advanced = QWidget()
    advanced_form = QFormLayout(advanced)
    advanced_form.setContentsMargins(0, 0, 0, 0)
    form.addRow(advanced)
    advanced.setVisible(False)
    advanced_toggle.toggled.connect(advanced.setVisible)
    plugin.snap = QDoubleSpinBox()
    plugin.snap.setRange(0, 1000)
    plugin.snap.setValue(10)
    plugin.snap.setSuffix(' m')
    plugin.snap.setToolTip('Bu mesafeden uzak başlangıçlar atlanır; raporda gösterilir.')
    advanced_form.addRow('Yola bağlanma', plugin.snap)
    plugin.offroad = QDoubleSpinBox()
    plugin.offroad.setRange(1, 200)
    plugin.offroad.setValue(50)
    plugin.offroad.setSuffix(' m')
    plugin.offroad.setToolTip('Erişilebilir yol çevresindeki yaklaşık hizmet alanının azami genişliği.')
    advanced_form.addRow('Yol çevresi payı', plugin.offroad)
    plugin.planar = QCheckBox('Ağ düzlemsel; kesişen yollar bağlantı oluşturabilir')
    advanced_form.addRow('', plugin.planar)
    cards.addWidget(frame)

    frame, layout, form = card('Kayıt', 'Kalıcı sonuç için bir GeoPackage dosyası seçin.')
    plugin.run_name = QLineEdit('Network · Hizmet alanı')
    form.addRow('Çalışma adı', plugin.run_name)
    plugin.output_path = QLineEdit()
    plugin.output_path.setPlaceholderText('Boş bırakılırsa geçici QGIS katmanları')
    choose = QPushButton('GeoPackage seç…')
    choose.clicked.connect(plugin.choose_output)
    row = QHBoxLayout()
    row.addWidget(plugin.output_path, 1)
    row.addWidget(choose)
    form.addRow('Kayıt konumu', row)
    cards.addWidget(frame)
    cards.addStretch()

    aside = QFrame()
    aside.setObjectName('card')
    aside.setMinimumWidth(240)
    aside.setMaximumWidth(290)
    plugin.appearance_panel = aside
    side = QVBoxLayout(aside)
    side.setContentsMargins(18, 18, 18, 18)
    plugin.preview_title = label('Hizmet alanı', 'section')
    side.addWidget(plugin.preview_title)
    plugin.band_colors = ['#facc15', '#f97316', '#dc2626']
    plugin.preview = AreaPreview(plugin)
    side.addWidget(plugin.preview)
    side.addWidget(label('Şematik çıktı örneği', 'hint'))
    plugin.preview_legend = label('', 'hint')
    side.addWidget(plugin.preview_legend)
    plugin.color_widgets = []
    for title, index in [('Dış alan', 2), ('Orta alan', 1), ('İç alan', 0)]:
        button = QPushButton(title)
        def apply_style(button=button, index=index, title=title):
            button.setText(title + '  ' + plugin.band_colors[index].upper())
            button.setStyleSheet('QPushButton { border-left: 8px solid %s; text-align: left; }' % plugin.band_colors[index])
        def choose_color(checked=False, index=index, apply_style=apply_style):
            color = QColorDialog.getColor(QColor(plugin.band_colors[index]), dialog, 'Alan rengini seç')
            if color.isValid():
                plugin.band_colors[index] = color.name()
                apply_style()
                plugin.refresh_summary()
        apply_style()
        button.clicked.connect(choose_color)
        side.addWidget(button)
        plugin.color_widgets.append(button)
    color_hint = label('Tek eşikte iç renk; iki eşikte iç ve dış renk kullanılır.', 'hint')
    side.addWidget(color_hint)
    plugin.color_widgets.append(color_hint)
    side.addSpacing(10)
    side.addWidget(label('Çalışma özeti', 'section'))
    plugin.summary = label('Katmanlarınızı seçin.', 'hint')
    side.addWidget(plugin.summary)
    side.addSpacing(16)
    side.addWidget(label('Girdi kontrolü', 'section'))
    plugin.validation = label('Analiz öncesi CRS, kimlik, geometri ve çalışma alanını kontrol edin.', 'hint')
    side.addWidget(plugin.validation)
    plugin.validate_button = QPushButton('Girdileri doğrula')
    plugin.validate_button.clicked.connect(plugin.validate_inputs)
    side.addWidget(plugin.validate_button)
    side.addStretch()
    plugin.demo_button = QPushButton('Örnek veri yükle')
    plugin.demo_button.clicked.connect(plugin.load_demo)
    # Optional demo belongs in help, away from the primary analysis flow.
    setup_layout.addWidget(aside, 1)

    results = QWidget()
    results_layout = QVBoxLayout(results)
    results_layout.setContentsMargins(0, 14, 0, 0)
    metrics = QHBoxLayout()
    plugin.metric_labels = {}
    for key, title in [('accepted', 'Ağa bağlanan'), ('skipped', 'Atlanan'), ('layers', 'Çıktı katmanı')]:
        frame, layout, form = card(title, '')
        value = label('—', 'metric')
        plugin.metric_labels[key] = value
        layout.addWidget(value)
        metrics.addWidget(frame)
    results_layout.addLayout(metrics)
    plugin.result_info = label('Analiz tamamlandığında katmanlar ve veri kalitesi özeti burada görünür.', 'hint')
    results_layout.addWidget(plugin.result_info)
    plugin.result_table = QTableWidget(0, 4)
    plugin.result_table.setHorizontalHeaderLabels(['Başlangıç kimliği', 'Durum', 'Yola uzaklık (m)', 'Açıklama'])
    plugin.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    plugin.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    plugin.result_table.setAlternatingRowColors(True)
    results_layout.addWidget(plugin.result_table, 1)
    tabs.addTab(results, 'Sonuçlar')

    help_page = QTextBrowser()
    help_page.setOpenExternalLinks(True)
    help_page.setHtml('''<h2>Yöntem ve veri kalitesi</h2><p>Bu araç çift yönlü, mesafeye dayalı <b>yaya hizmet alanı</b> üretir.
    Araç süreleri ve dakika izokronları hesaplanmaz. Mesafeler başlangıçların merkezine uygun yerel UTM CRS'de ölçülür.</p>
    <h3>Ağ analizleri</h3><p>En kısa yol: bir başlangıç ve hedef. En yakın tesis: her başlangıç için ağda en kısa mesafeli tesis. Başlangıç–hedef tablosu: tüm çiftlerin ağ mesafesi, en fazla 100 × 100 kayıt. Azami mesafe 10.000 m; limit dışı veya kopuk ağlarda mesafe boş kalır. Aynı katmanda noktanın kendisi tesis olarak seçilmez. Çift yönlü yaya modeli; süre, araç tek yönü ve dönüş kısıtları hesaplanmaz.</p><h3>Erişime kapalı bölgeler</h3><p>Hizmet alanında isteğe bağlı poligon bariyerleri yol parçalarını keser, kapalı bölge içindeki başlangıçları ve bölgeden geçen yola bağlanma çizgilerini dışlar. Sonuç poligonlarından da bu bölgeler çıkarılır. Sınır 1 cm kapalı kabul edilir. Özel kapı/izin veya geçiş istisnası modellenmez. Bu seçim yalnızca hizmet alanına uygulanır.</p><h3>Topoloji</h3><p>Kullanıcı ağındaki düzlemsel kesişimler düğüm olur. Köprü/tünel içeren katmanları bu modele dahil etmeyin.
    OSM'de köprü, tünel ve farklı seviye etiketli yollar dışlanır; bazı erişimler eksik kalabilir.</p>
    <h3>Ağa bağlanma ve tamponlama</h3><p>Başlangıçlar en yakın yol parçasına bağlanır; tolerans dışındakiler raporlanır.
    Bağlanma mesafesi ağ bütçesinden düşmez. Yol dışı pay, kalan bütçe ile sınırlı 25 m parçalı yaklaşık tamponlamadır.
    Bina/barikat ve gerçek yürüme yüzeyi modelde yoktur.</p><h3>Sonuçlar</h3>
    <p>Tek poligon katmanı: her başlangıç için ardışık mesafe bantları. Örneğin 400, 800 eşikleri 0–400 ve 400–800 m poligonları üretir. Kümülatif 0–800 poligonu üretilmez.
    Halkalar çift sayımı önler; farklı durakların alanlarında örtüşmeyi seçebilirsiniz. Örtüşme kaldırılırken küçük mesafe bandı önceliklidir; eşit bantta girdi nokta sırası kullanılır. En yakın tesis bölümlendirmesi değildir. Alan birimi m²'dir.</p>
    <h3>Örnek veri</h3><p>112 yol, 6 durak, 8 nüfus bölgesi, 6 hizmet noktası. 10 m toleransta 4 durak bağlanır, 2 durak atlanır.
    Nüfus ve hizmet katmanları ayrıca örtüşme analizi için sağlanır; otomatik nüfus/POI özeti henüz yoktur.</p>
    <h3>Kaynak ve sürüm</h3><p>0.3.0 geliştirme sürümü. Yerel analiz gerçek ücret veya kredi tüketmez.
    <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors / ODbL</a>.
    Kendi yol/başlangıç verileri sunucuya yüklenmez; OSM için noktalar ve mesafeden hesaplanan alan Overpass servisine gönderilir.</p>''')
    help_container = QWidget()
    help_layout = QVBoxLayout(help_container)
    help_layout.addWidget(help_page)
    help_layout.addWidget(plugin.demo_button)
    tabs.addTab(help_container, 'Yardım')

    footer = QFrame()
    footer.setObjectName('card')
    bottom = QVBoxLayout(footer)
    status_row = QHBoxLayout()
    plugin.status = label('Hazır · Girdileri seçerek başlayın.', 'hint')
    status_row.addWidget(plugin.status, 1)
    plugin.cancel = QPushButton('İptal')
    plugin.cancel.setEnabled(False)
    plugin.cancel.clicked.connect(lambda: plugin.task.cancel() if plugin.task else None)
    plugin.start = QPushButton('Analizi çalıştır  →')
    plugin.start.setObjectName('primary')
    plugin.start.clicked.connect(plugin.run)
    status_row.addWidget(plugin.cancel)
    status_row.addWidget(plugin.start)
    bottom.addLayout(status_row)
    plugin.progress = QProgressBar()
    plugin.progress.setTextVisible(False)
    plugin.progress.setMaximumHeight(8)
    bottom.addWidget(plugin.progress)
    root.addWidget(footer)
    plugin.source.currentIndexChanged.connect(plugin.source_changed)
    for selector in (plugin.roads, plugin.points):
        selector.layerChanged.connect(plugin.refresh_summary)
    for field in (plugin.cutoffs,):
        field.textChanged.connect(plugin.refresh_summary)
    plugin.snap.valueChanged.connect(plugin.refresh_summary)
    plugin.offroad.valueChanged.connect(plugin.refresh_summary)
    plugin.selected.toggled.connect(plugin.refresh_summary)
    plugin.points.layerChanged.connect(plugin.refresh_endpoints)
    plugin.targets.layerChanged.connect(plugin.refresh_endpoints)
    plugin.id_field.fieldChanged.connect(plugin.refresh_endpoints)
    plugin.target_id.fieldChanged.connect(plugin.refresh_endpoints)
    plugin.refresh_endpoints()
    plugin.analysis_type.currentIndexChanged.connect(plugin.mode_changed)
    plugin.route_limit.valueChanged.connect(plugin.refresh_summary)
    plugin.use_barriers.toggled.connect(plugin.refresh_summary)
    plugin.barrier_layer.layerChanged.connect(plugin.refresh_summary)
    plugin.source_changed(0)
    plugin.mode_changed(0)
    plugin.refresh_summary()
    return dialog
