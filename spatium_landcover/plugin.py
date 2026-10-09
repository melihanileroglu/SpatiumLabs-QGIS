"""QGIS UI with isolated model process and durable polygon output."""
import json
import os
import sys
from pathlib import Path
from math import ceil
from qgis.PyQt.QtCore import Qt, QProcess, QProcessEnvironment, QSettings, QTemporaryDir, QStandardPaths, QTimer
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (QAction,QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,
    QPushButton,QFileDialog,QLineEdit,QComboBox,QDoubleSpinBox,QSpinBox,QCheckBox,
    QGroupBox,QProgressBar,QMessageBox,QTabWidget,QFrame,QWidget,QScrollArea,QColorDialog,QGridLayout)
from qgis.core import (QgsProject,QgsGeometry,QgsRectangle,QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,QgsMapLayerProxyModel,QgsVectorLayer,QgsVectorFileWriter,
    QgsSymbol,QgsRendererCategory,QgsCategorizedSymbolRenderer,QgsWkbTypes,QgsDistanceArea,QgsPointXY)
from qgis.gui import QgsMapLayerComboBox,QgsMapTool,QgsRubberBand
from .branding import icon, welcome, Logo
from .planning import tile_count
from .ui import STYLE, CoverPreview

ROOT=Path(__file__).resolve().parent
DEFAULT_MODEL=json.loads((ROOT/'models'/'landcover.json').read_text())

def clean_environment():
    environment=QProcessEnvironment.systemEnvironment()
    for name in ('PYTHONHOME','PYTHONPATH','GDAL_DATA','PROJ_LIB','PROJ_DATA','QT_PLUGIN_PATH'):
        environment.remove(name)
    environment.insert('PYTHONUNBUFFERED','1')
    return environment

class RectangleTool(QgsMapTool):
    def __init__(self,canvas,on_done):
        super().__init__(canvas);self.start=None;self.done=on_done
        self.rubber=QgsRubberBand(canvas,QgsWkbTypes.PolygonGeometry)
        self.rubber.setColor(QColor('#268f9e'));self.rubber.setWidth(2)
    def canvasPressEvent(self,event): self.start=self.toMapCoordinates(event.pos())
    def canvasMoveEvent(self,event):
        if self.start is not None:
            rect=QgsRectangle(self.start,self.toMapCoordinates(event.pos()))
            self.rubber.setToGeometry(QgsGeometry.fromRect(rect),None)
    def canvasReleaseEvent(self,event):
        if self.start is None: return
        rect=QgsRectangle(self.start,self.toMapCoordinates(event.pos()))
        self.start=None;self.rubber.reset(QgsWkbTypes.PolygonGeometry)
        if rect.width()>0 and rect.height()>0: self.done(QgsGeometry.fromRect(rect),self.canvas().mapSettings().destinationCrs())
    def deactivate(self):
        self.rubber.reset(QgsWkbTypes.PolygonGeometry);super().deactivate()
    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Escape:
            self.start=None;self.rubber.reset(QgsWkbTypes.PolygonGeometry)
            self.done(None,None)

class EarthPlugin:
    def __init__(self,iface):
        self.iface=iface;self.dialog=None;self.process=None;self.aoi=None;self.aoi_crs=None
        self.settings=QSettings();self.model=json.loads(json.dumps(DEFAULT_MODEL));self.tool=None;self.temp=None
        self.capture_pending=False
    def initGui(self):
        self.action=QAction(icon(), 'Vision',self.iface.mainWindow())
        self.action.triggered.connect(self.show)
        self.iface.addPluginToMenu('Spatium Labs',self.action)
        self.iface.addToolBarIcon(self.action)
    def unload(self):
        self.capture_pending=False
        self.restore_capture_layers()
        if self.process: self.process.kill();self.process.waitForFinished(3000)
        if self.tool and self.iface.mapCanvas().mapTool() is self.tool:
            self.iface.mapCanvas().unsetMapTool(self.tool)
        if self.dialog: self.dialog.close();self.dialog.deleteLater()
        self.iface.removePluginMenu('Spatium Labs',self.action);self.iface.removeToolBarIcon(self.action)
    def show(self):
        if self.dialog: self.dialog.show();self.dialog.raise_();return
        if not welcome(self.iface.mainWindow(), 'Vision'): return
        for node in QgsProject.instance().layerTreeRoot().findLayers():
            layer=node.layer()
            if layer:
                try:
                    if json.loads(layer.customProperty('spatium/earth_run','{}')).get('engine')=='reference':
                        layer.setName('Vision · Sentetik test poligonları');node.setItemVisibilityChecked(False)
                except (ValueError,TypeError): pass
        self.dialog=QDialog(self.iface.mainWindow());self.dialog.setWindowTitle('Spatium Labs | Vision')
        self.dialog.setWindowIcon(icon())
        self.dialog.resize(1040,760);self.dialog.setObjectName('spatiumWorkbench')
        layout=QVBoxLayout(self.dialog);layout.setContentsMargins(20,20,20,16);layout.setSpacing(12)
        self.dialog.setStyleSheet(STYLE)
        header=QFrame();header.setObjectName('header');head=QHBoxLayout(header);head.setContentsMargins(20,16,20,16)
        branding=QVBoxLayout();brand=QLabel('SPATIUM / VISION');brand.setObjectName('brand');branding.addWidget(brand)
        subtitle=QLabel('Görüntüden nesne ve arazi örtüsü çıkarımı');subtitle.setObjectName('subtitle');branding.addWidget(subtitle)
        head.addWidget(Logo(48));head.addLayout(branding);head.addStretch();badge=QLabel('RGB · POLİGON');badge.setObjectName('badge');head.addWidget(badge);layout.addWidget(header)
        tabs=QTabWidget();layout.addWidget(tabs,1)
        analysis=QWidget();row=QHBoxLayout(analysis);row.setContentsMargins(0,8,0,0);row.setSpacing(12)
        scroll=QScrollArea();scroll.setWidgetResizable(True);content=QWidget();left=QVBoxLayout(content);left.setContentsMargins(0,0,8,0);left.setSpacing(10);scroll.setWidget(content);row.addWidget(scroll,3)
        sidebar=QFrame();sidebar.setObjectName('card');sidebar.setMinimumWidth(280);sidebar.setMaximumWidth(340)
        right=QVBoxLayout(sidebar);right.setContentsMargins(16,16,16,16);right.setSpacing(12);row.addWidget(sidebar,1);tabs.addTab(analysis,'01  Analiz kurulumu')
        source=QGroupBox('01 / Görüntü ve analiz alanı');form=QFormLayout(source);left.addWidget(source)
        self.source_mode=QComboBox();self.source_mode.addItems(['Görünen harita görüntüsü','Yerel RGB dosyası']);form.addRow('Analiz kaynağı',self.source_mode)
        self.raster=QgsMapLayerComboBox();self.raster.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.raster.setAllowEmptyLayer(True);form.addRow('RGB görüntü',self.raster)
        load=QPushButton('Görüntü aç…');load.clicked.connect(self.load_raster);form.addRow('',load)
        draw=QPushButton('Haritada alan çiz');draw.clicked.connect(self.draw)
        polygon=QPushButton('Seçili poligonları kullan');polygon.clicked.connect(self.use_polygon)
        buttons=QHBoxLayout();buttons.addWidget(draw);buttons.addWidget(polygon);form.addRow('Analiz alanı',buttons)
        self.area_label=QLabel('Alan seçilmedi');self.area_label.setWordWrap(True);form.addRow('',self.area_label)
        self.metadata_panel=QWidget();metadata_form=QFormLayout(self.metadata_panel);metadata_form.setContentsMargins(0,0,0,0)
        self.rights=QLineEdit();self.rights.setPlaceholderText('Kaynak ve kullanım izni / lisansı');metadata_form.addRow('Görüntü kaynağı',self.rights)
        self.date=QLineEdit();self.date.setPlaceholderText('YYYY-AA-GG');metadata_form.addRow('Görüntü tarihi',self.date)
        self.metadata_button=QPushButton('Kaynak bilgisi');self.metadata_button.setCheckable(True);self.metadata_button.toggled.connect(self.metadata_panel.setVisible)
        form.addRow('',self.metadata_button);form.addRow(self.metadata_panel);self.metadata_panel.hide()
        hint=QLabel('Görünen harita modunda ekranda yüklenmiş görüntü kullanılır. Seçilen alan küçük parçalarda gerçek modele verilir. Ekran dışında görüntü indirilmez; ayrıntı mevcut yakınlaştırma düzeyiyle sınırlıdır.');hint.setWordWrap(True);hint.setObjectName('hint');form.addRow(hint)
        model=QGroupBox('02 / Model ve hedefler');mf=QFormLayout(model);left.addWidget(model)
        self.model_label=QLabel(self.model['name']);self.model_label.setWordWrap(True);mf.addRow('Etkin model',self.model_label)
        self.preset=QComboBox();self.preset.addItems(['Arazi örtüsü + binalar','Yalnızca binalar']);self.preset.currentIndexChanged.connect(self.select_preset);mf.insertRow(0,'Analiz türü',self.preset)
        custom=QPushButton('Model profili aç…');custom.clicked.connect(self.choose_model)
        self.class_layout=QGridLayout();self.class_rows=[];mf.addRow('Hedefler',self.class_layout);self.class_checks=[];self.populate_classes()
        self.threshold=QDoubleSpinBox();self.threshold.setRange(.05,.95);self.threshold.setDecimals(4);self.threshold.setSingleStep(.05);self.threshold.setValue(self.model.get('threshold',.3));self.threshold.setToolTip('Seçilen sınıflara uygulanır. Skor doğruluk yüzdesi değildir.');mf.addRow('Skor eşiği',self.threshold)
        self.minimum=QDoubleSpinBox();self.minimum.setRange(0,1000000);self.minimum.setValue(4);self.minimum.setSuffix(' m²');mf.addRow('En küçük poligon',self.minimum)
        self.smoothing=QComboBox();self.smoothing.addItems(['Kapalı · özgün sınırlar','Hafif','Dengeli','Güçlü']);self.smoothing.setCurrentIndex(2);self.smoothing.setToolTip('Piksel basamaklarını ve vertex sayısını azaltır. Bina köşeleri yuvarlatılmaz.');mf.addRow('Sınır sadeleştirme',self.smoothing)
        self.size=QComboBox();self.size.addItems(['256 piksel','512 piksel','768 piksel']);self.size.setCurrentIndex(1);mf.addRow('Parça boyutu',self.size)
        self.path=QLineEdit();output=QPushButton('GeoPackage seç…');output.clicked.connect(self.choose_output)
        outrow=QHBoxLayout();outrow.addWidget(self.path);outrow.addWidget(output);left.addLayout(outrow)
        left.addStretch()
        preview_title=QLabel('Çıktı önizlemesi');preview_title.setObjectName('section');right.addWidget(preview_title)
        self.cover_preview=CoverPreview();right.addWidget(self.cover_preview)
        self.preview=QLabel();self.preview.setWordWrap(True);right.addWidget(self.preview)
        summary_title=QLabel('Çalışma özeti');summary_title.setObjectName('section');right.addWidget(summary_title)
        self.summary=QLabel();self.summary.setWordWrap(True);self.summary.setObjectName('hint');right.addWidget(self.summary)
        note=QLabel('Tek poligon katmanı • Sınıfa göre renkler\n\nÖnizleme şematiktir. Model sonuçlarını görüntü üzerinde kontrol edip düzeltebilirsiniz. Yol çıktısı yüzey poligonudur; ağ çizgisi değildir.');note.setWordWrap(True);note.setObjectName('hint');right.addWidget(note);right.addStretch()
        self.update_preview()
        training=QDialog();tf=QFormLayout(training);tabs.addTab(training,'02  Doğrulama ve eğitim')
        guide=QLabel('Çıktı poligonlarını QGIS düzenleme araçlarıyla düzeltin. class_id alanını kontrol edin; yalnızca doğruladığınız poligonlarda review = accepted yapın. Eksik nesneleri ekleyin. Arka plan örneklerine class_id = 0 verin. Diğer pikseller eğitimde yok sayılır.');guide.setWordWrap(True);tf.addRow(guide)
        self.labels=QgsMapLayerComboBox();self.labels.setFilters(QgsMapLayerProxyModel.PolygonLayer);tf.addRow('Doğrulanmış poligonlar',self.labels)
        export=QPushButton('Eğitim veri seti hazırla…');export.clicked.connect(self.export_training);tf.addRow(export)
        explain=QLabel('RGB görüntü + sınıf maskeleri, mekânsal train/validation/test blokları halinde kaydedilir. Bu sürüm model eğitimini çalıştırmaz. Eğitilmiş bir anlamsal segmentasyon modelini ONNX profiliyle yeniden kullanabilirsiniz.');explain.setWordWrap(True);tf.addRow(explain)
        settings=QDialog();sf=QFormLayout(settings);tabs.addTab(settings,'Model ortamı');sf.addRow('Özel model',custom)
        self.python=QLineEdit(self.settings.value('Spatium/Earth/python',''));sf.addRow('Ayrı Python ortamı',self.python)
        select=QPushButton('Python seç…');select.clicked.connect(self.choose_python);sf.addRow(select)
        install=QPushButton('Model bağımlılıklarını ayrı ortama kur');install.clicked.connect(self.setup);sf.addRow(install)
        check=QPushButton('Ortamı kontrol et');check.clicked.connect(self.check_environment);sf.addRow(check)
        help=QLabel('Python 3.10–3.12 kullanın. Kurulum yeni bir sanal ortam oluşturur; QGIS Python’una paket kurulmaz. Hazır model ilk analizde indirilir ve önbelleğe alınır. İndirme internet ve disk alanı gerektirir. Görüntünüz uzak bir analiz servisine gönderilmez.');help.setWordWrap(True);sf.addRow(help)
        imagery=QDialog();imf=QFormLayout(imagery);tabs.addTab(imagery,'Lisanslı görüntü servisi')
        explanation=QLabel('İndirme ve analiz izni olan kendi XYZ sağlayıcınızın profilini seçin. Haritada çizdiğiniz alan, sağlayıcının tanımladığı özgün zoom seviyesinde otomatik indirilip RGB GeoTIFF olarak açılır. Daha yüksek zoom ile sahte ayrıntı üretilmez. Google Earth/Maps desteklenmez.');explanation.setWordWrap(True);imf.addRow(explanation)
        self.provider=None;self.provider_label=QLabel('Sağlayıcı seçilmedi');imf.addRow('Sağlayıcı',self.provider_label)
        choose=QPushButton('Sağlayıcı profili seç…');choose.clicked.connect(self.choose_provider);imf.addRow(choose)
        acquire_button=QPushButton('Seçilen alanın görüntüsünü al…');acquire_button.clicked.connect(self.acquire);imf.addRow(acquire_button)
        self.status=QLabel('Hazır');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.progress=QProgressBar();layout.addWidget(self.progress)
        footer=QHBoxLayout();self.cancel=QPushButton('İptal');self.cancel.setEnabled(False);self.cancel.clicked.connect(self.cancel_process)
        self.run_button=QPushButton('Analizi çalıştır  →');self.run_button.setObjectName('primary');self.run_button.clicked.connect(self.run);footer.addStretch();footer.addWidget(self.cancel);footer.addWidget(self.run_button);layout.addLayout(footer)
        self.raster.layerChanged.connect(self.source_changed);self.size.currentIndexChanged.connect(self.refresh);self.source_mode.currentIndexChanged.connect(self.source_changed)
        self.dialog.finished.connect(self.on_closed)
        if QgsProject.instance().readEntry('Spatium','preset','')[0]=='istanbul_earth':
            for layer in QgsProject.instance().mapLayers().values():
                if layer.type()==1 and layer.source().endswith('istanbul_earth.tif'):
                    self.raster.setLayer(layer)
                    self.path.setText(str(Path(QgsProject.instance().homePath())/'Earth_Results.gpkg'))
                if isinstance(layer,QgsVectorLayer) and 'istanbul_earth_labels.gpkg' in layer.source(): self.labels.setLayer(layer)
        self.refresh();self.dialog.show()
    def populate_classes(self):
        for widget in self.class_rows: self.class_layout.removeWidget(widget);widget.deleteLater()
        self.class_rows=[];self.class_checks=[]
        for index,cls in enumerate(self.model['classes']):
            item=QWidget();row=QHBoxLayout(item);row.setContentsMargins(0,0,0,0);row.setSpacing(8)
            check=QCheckBox(cls['name']);check.setChecked(True);check.toggled.connect(self.update_preview)
            swatch=QPushButton();swatch.setObjectName('swatch');swatch.setToolTip('Çıktı rengini seç')
            swatch.setStyleSheet('background:'+cls['color']+';');swatch.clicked.connect(lambda _,c=cls,b=swatch:self.choose_color(c,b))
            row.addWidget(check,1);row.addWidget(swatch);self.class_layout.addWidget(item,index//2,index%2)
            self.class_rows.append(item);self.class_checks.append((check,cls))
    def choose_color(self,cls,button):
        color=QColorDialog.getColor(QColor(cls['color']),self.dialog,'Çıktı rengi')
        if color.isValid(): cls['color']=color.name();button.setStyleSheet('background:'+color.name()+';');self.update_preview()
    def update_preview(self,*_):
        if not hasattr(self,'cover_preview'): return
        from html import escape
        selected=[c for check,c in self.class_checks if check.isChecked()]
        self.cover_preview.setClasses(selected)
        self.preview.setText(''.join('<span style="color:'+c['color']+'">■</span> '+escape(c['name'])+'<br>' for c in selected))
    def select_preset(self,index):
        if index>1: return
        try:
            self.require_idle()
            self.model=json.loads((ROOT/'models'/('landcover.json' if index==0 else 'buildings.json')).read_text())
            self.model_label.setText(self.model['name']);self.populate_classes();self.threshold.setValue(self.model.get('threshold',.3));self.update_preview()
        except Exception as exc: self.error(str(exc))
    def error(self,message): QMessageBox.warning(self.dialog,'Spatium Vision',message)
    def require_idle(self):
        if self.capture_pending: raise ValueError('Harita görüntüsü hazırlanıyor; lütfen bekleyin.')
        if self.process and self.process.state()!=QProcess.NotRunning: raise ValueError('Önce mevcut işlem tamamlanmalı.')
    def restore_capture_layers(self):
        for node in getattr(self,'hidden_vectors',[]):
            try: node.setItemVisibilityChecked(True)
            except RuntimeError: pass  # A layer may have been removed during capture.
        self.hidden_vectors=[]
    def on_closed(self,*_):
        self.capture_pending=False
        self.restore_capture_layers()
        if self.process and self.process.state()!=QProcess.NotRunning: self.cancel_process()
        else: self.run_button.setEnabled(True)
    def choose_python(self):
        path,_=QFileDialog.getOpenFileName(self.dialog,'Python yürütücüsü')
        if path: self.python.setText(path);self.settings.setValue('Spatium/Earth/python',path)
    def load_raster(self):
        path,_=QFileDialog.getOpenFileName(self.dialog,'Koordinatlı RGB görüntü','','Görüntü (*.tif *.tiff *.vrt *.jpg *.jpeg *.png)')
        if path:
            layer=self.iface.addRasterLayer(path,Path(path).stem)
            if layer and layer.isValid(): self.raster.setLayer(layer)
    def choose_output(self):
        path,_=QFileDialog.getSaveFileName(self.dialog,'Yeni çıktı dosyası','','GeoPackage (*.gpkg)')
        if path: self.path.setText(path if path.lower().endswith('.gpkg') else path+'.gpkg')
    def choose_model(self):
        path,_=QFileDialog.getOpenFileName(self.dialog,'Model profili','','JSON (*.json)')
        if not path: return
        try:
            model=json.loads(Path(path).read_text())
            if model.get('schema')!=1 or model.get('engine') not in ('grounded_sam','building_onnx','landcover_hybrid','onnx'): raise ValueError('Geçersiz model profili.')
            ids=[c['id'] for c in model['classes']]
            if len(set(ids))!=len(ids) or not ids or any(not isinstance(i,int) or not 1<=i<=254 for i in ids): raise ValueError('Sınıf kimlikleri geçersiz.')
            for c in model['classes']:
                if not c.get('name') or not QColor(c.get('color','')).isValid(): raise ValueError('Sınıf adı ve rengi gerekli.')
            if model['engine']=='onnx':
                model['weights']=str((Path(path).parent/model['weights']).resolve())
                if not Path(model['weights']).is_file(): raise ValueError('ONNX ağırlığı bulunamadı.')
            self.model=model;self.model_label.setText(model['name']);self.populate_classes()
            self.preset.blockSignals(True)
            if self.preset.count()==2: self.preset.addItem('Özel model profili')
            self.preset.setCurrentIndex(2);self.preset.blockSignals(False)
            self.threshold.setValue(model.get('threshold',.3))
            self.update_preview()
        except Exception as exc: self.error(str(exc))
    def choose_provider(self):
        from .imagery import validate_provider
        path,_=QFileDialog.getOpenFileName(self.dialog,'Lisanslı XYZ profili','','JSON (*.json)')
        if path:
            try:
                self.provider=validate_provider(json.loads(Path(path).read_text()))
                self.provider_label.setText(self.provider.get('name','XYZ')+' · özgün zoom '+str(self.provider['native_zoom']))
            except Exception as exc: self.error(str(exc))
    def acquire(self):
        try:
            self.require_idle()
            if not self.aoi or not self.provider: raise ValueError('Önce analiz alanını çizin ve izinli sağlayıcı profilini seçin.')
            path,_=QFileDialog.getSaveFileName(self.dialog,'Yeni RGB görüntü','','GeoTIFF (*.tif)')
            if not path: return
            if not path.lower().endswith('.tif'): path+='.tif'
            if Path(path).exists(): raise ValueError('Görüntü çıktısı mevcut; yeni bir ad seçin.')
            job={'schema':1,'operation':'acquire','provider':self.provider,'aoi':json.loads(self.aoi.asJson()),
                'aoi_crs':self.aoi_crs.toWkt(),'output':path}
            self.start_job(job,'acquire')
        except Exception as exc: self.error(str(exc))
    def draw(self):
        if self.process and self.process.state()!=QProcess.NotRunning: return
        canvas=self.iface.mapCanvas();self.previous_tool=canvas.mapTool()
        self.tool=RectangleTool(canvas,self.area_selected);self.dialog.hide();canvas.setMapTool(self.tool)
    def area_selected(self,geom,crs):
        if geom is not None: self.aoi,self.aoi_crs=geom,crs
        if self.tool and self.iface.mapCanvas().mapTool() is self.tool:
            if self.previous_tool: self.iface.mapCanvas().setMapTool(self.previous_tool)
            else: self.iface.mapCanvas().unsetMapTool(self.tool)
        self.dialog.show();self.refresh()
    def use_polygon(self):
        layer=self.iface.activeLayer()
        if not isinstance(layer,QgsVectorLayer) or layer.geometryType()!=QgsWkbTypes.PolygonGeometry:
            self.error('Katman panelinde bir poligon katmanı seçin.');return
        selected=layer.selectedFeatures()
        if not selected: self.error('Önce analiz alanı poligonlarını seçin.');return
        self.area_selected(QgsGeometry.unaryUnion([f.geometry() for f in selected]),layer.crs())
    def source_changed(self,*_):
        self.rights.clear();self.date.clear()
        self.metadata_button.setChecked(self.source_mode.currentIndex()==1)
        layer=self.raster.currentLayer()
        if self.source_mode.currentIndex()==1 and layer and Path(layer.source().split('|')[0]).is_file() and layer.source().endswith('istanbul_earth.tif') and QgsProject.instance().readEntry('Spatium','preset','')[0]=='istanbul_earth':
            self.rights.setText('CC0 · Spatium Labs sentetik İstanbul test görüntüsü')
        self.refresh()
        if not self.process or self.process.state()==QProcess.NotRunning:
            if self.source_mode.currentIndex()==1 and layer and not Path(layer.source().split('|')[0]).is_file():
                self.status.setText('Bu katman görüntü servisi. Görüntü aç… ile koordinatlı RGB dosyası seçin veya Lisanslı görüntü servisi sekmesini kullanın.')
            else: self.status.setText('Hazır')
    def refresh(self,*_):
        layer=self.raster.currentLayer();text='Kaynak görüntü seçin.'
        if self.source_mode.currentIndex()==0:
            self.raster.setEnabled(False)
            canvas=self.iface.mapCanvas();self.run_button.setEnabled(not self.process or self.process.state()==QProcess.NotRunning)
            self.summary.setText('Kaynak: Görünen harita\nAlan: Seçilen bölge veya harita görünümü\nÇözünürlük: Mevcut yakınlaştırma\nÇıktı: Sınıflandırılmış poligonlar')
            self.area_label.setText('Çizdiğiniz / seçtiğiniz alan kullanılacak.' if self.aoi else 'Görünen haritanın tamamı kullanılacak.')
            return
        self.raster.setEnabled(True)
        supported=bool(layer and layer.isValid() and layer.crs().isValid() and Path(layer.source().split('|')[0]).is_file() and layer.bandCount()>=3)
        idle=not self.process or self.process.state()==QProcess.NotRunning
        self.run_button.setEnabled(supported and idle)
        if layer and layer.isValid() and not Path(layer.source().split('|')[0]).is_file():
            text=f'{layer.name()}\nKaynak türü: harita/görüntü servisi\n\nBu katmandan yerel analiz yapılamıyor. Servis katmanının piksel boyutu, görüntünün gerçek çözünürlüğünü göstermez.\n\nGörüntü aç… ile koordinatlı RGB dosyası seçin. Test için Sentetik RGB · 0.25 m/piksel katmanını kullanabilirsiniz.'
        elif layer and layer.isValid():
            text=f'{layer.name()}\nCRS: {layer.crs().authid()}\nKaynak piksel: {layer.rasterUnitsPerPixelX():.6g} × {layer.rasterUnitsPerPixelY():.6g} (CRS birimi)'
            measure=QgsDistanceArea();measure.setSourceCrs(layer.crs(),QgsProject.instance().transformContext());measure.setEllipsoid('WGS84')
            center=layer.extent().center();resolution=measure.measureLine(center,QgsPointXY(center.x()+layer.rasterUnitsPerPixelX(),center.y()))
            text+=f'\nYaklaşık GSD: {resolution:.2f} m/piksel'
            if resolution>1: text+='\nKüçük bina ayrıntıları için kaynak çözünürlüğü yetersiz olabilir.'
            if self.aoi and self.aoi_crs:
                try:
                    geom=QgsGeometry(self.aoi);geom.transform(QgsCoordinateTransform(self.aoi_crs,layer.crs(),QgsProject.instance()))
                    rect=geom.boundingBox().intersect(layer.extent())
                    w=max(0,ceil(rect.width()/layer.rasterUnitsPerPixelX()));h=max(0,ceil(rect.height()/layer.rasterUnitsPerPixelY()))
                    size=[256,512,768][self.size.currentIndex()]
                    text+=f'\nAlan görüntüsü: yaklaşık {w} × {h} piksel\nParça sayısı: yaklaşık {tile_count(w,h,size)}\nSınır payı: 64 piksel\nÖzgün çözünürlük korunur.'
                except Exception as exc: text+='\nAlan dönüşümü: '+str(exc)
        self.summary.setText(text)
        if self.aoi:
            measure=QgsDistanceArea();measure.setSourceCrs(self.aoi_crs,QgsProject.instance().transformContext());measure.setEllipsoid('WGS84')
            rect=self.aoi.boundingBox()
            width=measure.measureLine(QgsPointXY(rect.xMinimum(),rect.yMinimum()),QgsPointXY(rect.xMaximum(),rect.yMinimum()))
            height=measure.measureLine(QgsPointXY(rect.xMinimum(),rect.yMinimum()),QgsPointXY(rect.xMinimum(),rect.yMaximum()))
            self.area_label.setText(f'Alan sınırı: yaklaşık {width:.1f} × {height:.1f} m')
    def job(self):
        layer=self.raster.currentLayer()
        if not layer or not layer.isValid() or not layer.crs().isValid(): raise ValueError('CRS tanımlı bir RGB görüntü seçin.')
        path=layer.source().split('|')[0]
        if not Path(path).is_file(): raise ValueError('Yerel koordinatlı görüntü dosyası gerekli; WMS/XYZ ekran görüntüsü analiz kaynağı değildir.')
        if not self.aoi: raise ValueError('Haritada analiz alanı çizin veya seçili poligonları kullanın.')
        if not self.rights.text().strip(): raise ValueError('Görüntünün kaynak ve kullanım izni bilgisini yazın.')
        classes=[cls for check,cls in self.class_checks if check.isChecked()]
        if not classes: raise ValueError('En az bir hedef sınıf seçin.')
        return {'schema':1,'raster':path,'aoi':json.loads(self.aoi.asJson()),'aoi_crs':self.aoi_crs.toWkt(),
            'rights_note':self.rights.text().strip(),'imagery_date':self.date.text().strip(),
            'classes':classes,'engine':self.model['engine'],'model':self.model,
            'threshold':self.threshold.value(),'min_area':self.minimum.value(),'smooth_pixels':[0,.75,1.5,3][self.smoothing.currentIndex()],
            'tile_size':[256,512,768][self.size.currentIndex()],'halo':64,'output':self.path.text().strip()}
    def start(self,program,args,operation):
        self.require_idle()
        self.operation=operation;self.messages='';self.buffer='';self.was_cancelled=False
        self.process=QProcess(self.dialog);self.process.setProcessEnvironment(clean_environment())
        environment=self.process.processEnvironment()
        default_cache=str(Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation))/'spatium-earth'/'models')
        environment.insert('HF_HOME',self.settings.value('Spatium/Earth/model_cache',default_cache))
        self.process.setProcessEnvironment(environment)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.process_error)
        self.process.start(program,args);self.run_button.setEnabled(False);self.cancel.setEnabled(True)
        self.progress.setValue(0);self.status.setText('Model ortamı başlatılıyor…')
    def start_job(self,job,operation):
        self.require_idle()
        python=self.python.text().strip()
        if not Path(python).is_file(): raise ValueError('Model ortamı sekmesinde ayrı Python yürütücüsünü seçin.')
        self.settings.setValue('Spatium/Earth/python',python)
        self.temp=QTemporaryDir();path=Path(self.temp.path())/'job.json';path.write_text(json.dumps(job,ensure_ascii=False))
        self.current_job=job;self.start(python,[str(ROOT/'worker.py'),str(path)],operation)
    def run(self):
        try:
            self.require_idle()
            if self.source_mode.currentIndex()==0:
                self.capture_map();return
            job=self.job()
            if not job['output'] or Path(job['output']).exists(): raise ValueError('Yeni bir GeoPackage çıktı adı seçin.')
            self.start_job(job,'inference')
        except Exception as exc: self.error(str(exc))
    def capture_map(self):
        canvas=self.iface.mapCanvas()
        if canvas.rotation()!=0: raise ValueError('Görüntü analizi için harita dönüşünü 0° yapın.')
        if not self.path.text().strip() or Path(self.path.text().strip()).exists(): raise ValueError('Yeni bir GeoPackage çıktı adı seçin.')
        if not Path(self.python.text().strip()).is_file(): raise ValueError('Model ortamındaki Python yolunu kontrol edin.')
        if not any(check.isChecked() for check,cls in self.class_checks): raise ValueError('En az bir hedef seçin.')
        if not any(layer.type()==1 for layer in canvas.layers()): raise ValueError('Haritada uydu görüntüsü katmanını açın.')
        # Never let old candidate polygons become detector inputs.
        self.hidden_vectors=[]
        for node in QgsProject.instance().layerTreeRoot().findLayers():
            layer=node.layer()
            if isinstance(layer,QgsVectorLayer) and node.isVisible():
                node.setItemVisibilityChecked(False)
                self.hidden_vectors.append(node)
        self.run_button.setEnabled(False);self.status.setText('Harita görüntüsü hazırlanıyor…')
        canvas.refresh();self.capture_attempts=0
        self.capture_pending=True
        QTimer.singleShot(300,self.capture_ready)
    def capture_ready(self):
        if not self.capture_pending: return
        canvas=self.iface.mapCanvas()
        if canvas.isDrawing():
            self.capture_attempts+=1
            if self.capture_attempts<100: QTimer.singleShot(300,self.capture_ready);return
            self.capture_pending=False
            self.restore_capture_layers()
            self.error('Harita görüntüsü yüklenemedi. Görüntü yüklenince yeniden deneyin.');self.refresh();return
        try:
            self.capture_pending=False
            self.temp=QTemporaryDir();snapshot=Path(self.temp.path())/'visible_map.png'
            canvas.saveAsImage(str(snapshot))
            if not snapshot.is_file(): raise ValueError('Harita görüntüsü kaydedilemedi.')
            extent=canvas.mapSettings().visibleExtent();crs=canvas.mapSettings().destinationCrs()
            aoi=QgsGeometry(self.aoi) if self.aoi else QgsGeometry.fromRect(extent)
            aoi_crs=self.aoi_crs if self.aoi else crs
            job={'schema':1,'raster':str(snapshot),'snapshot_bounds':[extent.xMinimum(),extent.yMinimum(),extent.xMaximum(),extent.yMaximum()],
                'snapshot_crs':crs.toWkt(),'aoi':json.loads(aoi.asJson()),'aoi_crs':aoi_crs.toWkt(),
                'rights_note':self.rights.text().strip() or 'User-selected visible QGIS map; source terms apply',
                'imagery_date':self.date.text().strip(),'engine':self.model['engine'],'model':self.model,
                'classes':[cls for check,cls in self.class_checks if check.isChecked()],
                'threshold':self.threshold.value(),'min_area':self.minimum.value(),'smooth_pixels':[0,.75,1.5,3][self.smoothing.currentIndex()],'tile_size':[256,512,768][self.size.currentIndex()],
                'halo':64,'output':self.path.text().strip(),'input_kind':'visible_map'}
            path=Path(self.temp.path())/'job.json';path.write_text(json.dumps(job,ensure_ascii=False))
            self.current_job=job;self.start(self.python.text().strip(),[str(ROOT/'worker.py'),str(path)],'inference')
        except Exception as exc: self.error(str(exc));self.refresh()
        finally:
            self.restore_capture_layers()
    def run_synthetic(self):
        try:
            self.require_idle();job=self.job()
            if QgsProject.instance().readEntry('Spatium','preset','')[0]!='istanbul_earth': raise ValueError('Önce Istanbul_Earth.qgz sentetik test projesini açın.')
            if not job['output'] or Path(job['output']).exists(): raise ValueError('Yeni bir GeoPackage çıktı adı seçin.')
            job['engine']='reference';job['classes']=[c for c in DEFAULT_MODEL['classes'] if c['id'] in (1,2,3)];job['model']={}
            self.start_job(job,'inference')
        except Exception as exc: self.error(str(exc))
    def export_training(self):
        try:
            self.require_idle()
            job=self.job();layer=self.labels.currentLayer()
            if not layer or not {'class_id','review'} <= set(layer.fields().names()): raise ValueError('Etiket katmanı class_id ve review alanlarını içermeli.')
            folder=QFileDialog.getExistingDirectory(self.dialog,'Eğitim veri setinin kaydedileceği üst klasör')
            if not folder: return
            self.temp=QTemporaryDir();annotation=Path(self.temp.path())/'annotations.geojson'
            opts=QgsVectorFileWriter.SaveVectorOptions();opts.driverName='GeoJSON';opts.fileEncoding='UTF-8'
            result=QgsVectorFileWriter.writeAsVectorFormatV3(layer,str(annotation),QgsProject.instance().transformContext(),opts)
            if result[0]!=QgsVectorFileWriter.NoError: raise ValueError('Etiketler dışarı aktarılamadı: '+str(result))
            # Copy annotations into the job-owned temporary directory created by start_job.
            content=annotation.read_text();job.update(operation='export_training',annotation_crs=layer.crs().toWkt(),dataset=str(Path(folder)/'Spatium_Training'))
            python=self.python.text().strip()
            if not Path(python).is_file(): raise ValueError('Ayrı Python ortamını seçin.')
            path=Path(self.temp.path())/'job.json';job['annotations']=str(annotation);path.write_text(json.dumps(job,ensure_ascii=False))
            self.current_job=job;self.start(python,[str(ROOT/'worker.py'),str(path)],'training')
        except Exception as exc: self.error(str(exc))
    def setup(self):
        try:
            self.require_idle()
            python=self.python.text().strip()
            if not Path(python).is_file(): raise ValueError('Python 3.10–3.12 yürütücüsünü seçin.')
            env=Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))/'spatium-earth'/'environment'
            env.parent.mkdir(parents=True,exist_ok=True)
            self.install_environment=env
            self.start(python,[str(ROOT/'bootstrap.py'),str(env)],'setup')
        except Exception as exc: self.error(str(exc))
    def check_environment(self):
        try:
            self.start(self.python.text().strip(),['-c','import rasterio, shapely, fiona, pyproj, torch, transformers, onnxruntime; print("Model ortamı hazır")'],'check')
        except Exception as exc: self.error(str(exc))
    def read_output(self):
        raw=bytes(self.process.readAllStandardOutput()).decode('utf-8',errors='replace')
        self.messages=(self.messages+raw)[-12000:];self.buffer+=raw
        while '\n' in self.buffer:
            line,self.buffer=self.buffer.split('\n',1)
            try:
                data=json.loads(line)
                if 'progress' in data: self.progress.setValue(int(data['progress']));self.status.setText(data['message'])
                if 'error' in data: self.status.setText(data['error'])
            except (ValueError,TypeError):
                if line.strip(): self.status.setText(line[-250:])
    def process_error(self,error):
        if error==QProcess.FailedToStart:
            self.run_button.setEnabled(True);self.cancel.setEnabled(False)
            self.refresh()
            self.status.setText('Model ortamı başlatılamadı; Python yolunu kontrol edin.')
    def cancel_process(self):
        self.was_cancelled=True
        if self.process: self.process.kill()
    def finished(self,code,status):
        self.read_output();self.run_button.setEnabled(True);self.cancel.setEnabled(False)
        self.refresh()
        if self.was_cancelled:
            if self.operation=='inference':
                output=Path(self.current_job['output']);output.with_name(output.stem+'.tmp.gpkg').unlink(missing_ok=True)
            if self.operation=='training':
                import shutil
                folder=Path(self.current_job['dataset'])
                if folder.is_dir() and not (folder/'dataset.json').exists(): shutil.rmtree(folder)
            if self.operation=='acquire': Path(self.current_job['output']).with_suffix('.tmp.tif').unlink(missing_ok=True)
            self.status.setText('İşlem iptal edildi.');return
        if code!=0 or status!=QProcess.NormalExit:
            self.status.setText('İşlem tamamlanamadı.');self.error(self.messages[-3500:]);return
        if self.operation=='setup':
            python=self.install_environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            self.python.setText(str(python));self.settings.setValue('Spatium/Earth/python',str(python))
            self.status.setText('Ayrı model ortamı hazır.');return
        if self.operation=='acquire':
            layer=self.iface.addRasterLayer(self.current_job['output'],Path(self.current_job['output']).stem)
            if layer and layer.isValid(): self.raster.setLayer(layer)
            self.rights.setText(self.current_job['provider']['license_note']);self.status.setText('Görüntü hazır; hedefleri seçip poligonları çıkarın.')
        elif self.operation=='inference':
            name='Vision · Sentetik test poligonları' if self.current_job['engine']=='reference' else 'Vision · Görüntüden çıkarılan adaylar'
            layer=QgsVectorLayer(self.current_job['output']+'|layername=objects',name,'ogr')
            if not layer.isValid(): self.error('Çıktı QGIS katmanı olarak açılamadı.');return
            categories=[]
            for cls in self.current_job['classes']:
                symbol=QgsSymbol.defaultSymbol(layer.geometryType());symbol.setColor(QColor(cls['color']));symbol.setOpacity(.55)
                categories.append(QgsRendererCategory(cls['id'],symbol,cls['name']))
            layer.setRenderer(QgsCategorizedSymbolRenderer('class_id',categories))
            layer.setCustomProperty('spatium/earth_run',json.dumps(self.current_job,ensure_ascii=False))
            QgsProject.instance().addMapLayer(layer,False)
            group=QgsProject.instance().layerTreeRoot().addGroup('Spatium Vision');group.addLayer(layer)
            self.labels.setLayer(layer);self.progress.setValue(100)
            self.status.setText(f'{layer.featureCount()} aday poligon hazır; inceleyip düzeltin.')
        elif self.operation=='training': self.status.setText('Eğitim veri seti hazır: '+self.current_job['dataset'])
        else: self.status.setText('Model ortamı hazır.')
