"""Development QGIS plugin. Commercial enforcement requires the server worker."""
import json
from datetime import datetime, timezone
from pathlib import Path
from itertools import islice
from time import monotonic

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox, QTableWidgetItem
from qgis.core import (QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsFeature, QgsFeatureRequest, QgsField, QgsGeometry,
                       QgsPointXY, QgsProject, QgsRectangle, QgsTask, QgsVectorFileWriter,
                       QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsSymbol,
                       QgsVectorLayer, QgsWkbTypes, QgsVariantUtils)

from .branding import icon, welcome
from . import osm
from .analysis import calculate
from .routes_analysis import calculate_routes
from .preview import legend_html
from .graph import parse_distances


class AnalysisTask(QgsTask):
    def __init__(self, inputs, on_finished):
        super().__init__("Spatium Network · Hizmet alanı", QgsTask.CanCancel)
        self.inputs, self.on_finished = inputs, on_finished
        self.result, self.error = None, None

    def run(self):
        try:
            roads = self.inputs["roads"]
            if self.inputs["source"] == "osm":
                downloaded = osm.download(self.inputs["bbox"], self.isCanceled)
                context = self.inputs["context"]
                transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"),
                                                   self.inputs["crs"], context)
                roads = []
                for coords in downloaded:
                    geom = QgsGeometry.fromPolylineXY([QgsPointXY(*c) for c in coords])
                    geom.transform(transform)
                    roads.append(geom)
            self.setProgress(20)
            if self.inputs['mode'] == 'service':
                self.result = calculate(roads, self.inputs["points"], self.inputs["cutoffs"],
                                        self.inputs["snap"], self.inputs["offroad"], self.isCanceled,
                                        self.setProgress, overlap=self.inputs["overlap"], barriers=self.inputs["barriers"])
            else:
                self.result = calculate_routes(roads, self.inputs['points'], self.inputs['targets'],
                    self.inputs['snap'], self.inputs['cutoffs'][-1], self.inputs['mode'],
                    self.inputs['same_layer'], self.isCanceled, self.setProgress)
            return not self.isCanceled()
        except Exception as exc:
            self.error = str(exc)
            return False

    def finished(self, successful):
        self.on_finished(self, successful)


def output_layer(name, geometry_type, fields, rows, crs):
    layer = QgsVectorLayer(geometry_type + "?crs=" + crs.authid(), name, "memory")
    provider = layer.dataProvider()
    provider.addAttributes([QgsField(field, kind) for field, kind in fields])
    layer.updateFields()
    features = []
    for attrs, geometry in rows:
        f = QgsFeature(layer.fields())
        f.setAttributes(attrs)
        geom = QgsGeometry(geometry)
        if geometry_type.startswith("Multi") and not geom.isNull():
            geom.convertToMultiType()
        if not geom.isNull():
            f.setGeometry(geom)
        features.append(f)
    if not provider.addFeatures(features)[0]:
        raise ValueError("Sonuç katmanı oluşturulamadı: " + name)
    layer.updateExtents()
    return layer


class AccessibilityPlugin:
    def __init__(self, iface):
        self.iface, self.action, self.dialog, self.task = iface, None, None, None

    def initGui(self):
        self.action = QAction(icon(), "Network", self.iface.mainWindow())
        self.action.triggered.connect(self.show)
        self.iface.addPluginToMenu("Spatium Labs", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.task:
            self.task.cancel()
            self.task.on_finished = lambda *_: None
        if self.dialog:
            self.dialog.close()
            self.dialog.deleteLater()
        self.iface.removePluginMenu("Spatium Labs", self.action)
        self.iface.removeToolBarIcon(self.action)

    def show(self):
        if self.dialog:
            self.dialog.show()
            self.dialog.raise_()
            return
        if not welcome(self.iface.mainWindow(), "Network"): return
        from .ui import build_dialog
        self.dialog = build_dialog(self)
        project = QgsProject.instance()
        if project.readEntry('Spatium', 'preset', '')[0] == 'besiktas':
            for layer in project.mapLayers().values():
                if isinstance(layer, QgsVectorLayer) and 'layername=besiktas_points' in layer.source():
                    self.points.setLayer(layer)
                    self.id_field.setField('nokta_id')
                    self.targets.setLayer(layer)
                    self.target_id.setField('nokta_id')
                    if self.target_feature.count() > 1: self.target_feature.setCurrentIndex(1)
                    self.source.setCurrentIndex(1)
                    self.cutoffs.setText('400, 800')
                    self.snap.setValue(100)
                    self.offroad.setValue(50)
                    self.run_name.setText('Beşiktaş · 400 / 800 m')
                    self.refresh_summary()
                    break
        self.dialog.show()

    def refresh_endpoints(self, *_):
        for selector, field, combo in [(self.points,self.id_field,self.origin_feature),
                                       (self.targets,self.target_id,self.target_feature)]:
            old = combo.currentData()
            combo.clear()
            layer = selector.currentLayer()
            if layer:
                name = field.currentField()
                for feature in islice(layer.getFeatures(), 100):
                    value = str(feature[name]) if name else str(feature.id())
                    combo.addItem(value, feature.id())
                if old is not None:
                    index = combo.findData(old)
                    if index >= 0: combo.setCurrentIndex(index)

    def apply_test_package(self, idx):
        project = QgsProject.instance()
        if project.readEntry('Spatium', 'preset', '')[0] != 'istanbul_network':
            return
        mode = ['service','shortest','nearest','matrix'][idx]
        layers = {str(layer.customProperty('spatium/test_role')): layer
                  for layer in project.mapLayers().values()
                  if isinstance(layer, QgsVectorLayer) and layer.customProperty('spatium/test_mode') == mode}
        if not all(role in layers for role in ('origin','road')):
            return
        self.source.setCurrentIndex(0)
        self.roads.setLayer(layers['road'])
        self.points.setLayer(layers['origin'])
        self.id_field.setField('nokta_id')
        if 'target' in layers:
            self.targets.setLayer(layers['target'])
            self.target_id.setField('nokta_id')
        self.selected.setChecked(False)
        self.target_selected.setChecked(False)
        self.planar.setChecked(True)
        self.snap.setValue(30)
        self.cutoffs.setText('400, 800')
        self.route_limit.setValue(3000)
        self.run_name.setText('İstanbul · ' + self.analysis_type.currentText())
        for group in project.layerTreeRoot().children():
            for test_mode, prefix in [('service','01 ·'),('shortest','02 ·'),('nearest','03 ·'),('matrix','04 ·')]:
                if group.name().startswith(prefix):
                    group.setItemVisibilityChecked(test_mode == mode)
                    group.setExpanded(test_mode == mode)
        self.status.setText('Test paketi hazır · Sentetik yol ağı / İstanbul, Beşiktaş')

    def mode_changed(self, idx):
        self.apply_test_package(idx)
        routing = idx != 0
        self.targets_panel.setVisible(routing)
        self.endpoint_panel.setVisible(idx == 1)
        self.selected.setEnabled(idx != 1)
        self.target_selected.setEnabled(idx != 1)
        self.route_limit_panel.setVisible(routing)
        self.service_panel.setVisible(not routing)
        for widget in self.color_widgets:
            widget.setVisible(not routing)
        self.offroad.setEnabled(not routing)
        self.start.setText('Analizi çalıştır  →')
        self.refresh_summary()

    def source_changed(self, idx):
        self.roads.setEnabled(idx == 0)
        self.import_button.setEnabled(idx == 0)
        self.planar.setEnabled(idx == 0)
        self.refresh_summary()

    def refresh_summary(self, *_):
        if hasattr(self, 'preview_legend'):
            self.preview_title.setText(self.analysis_type.currentText())
            self.preview_legend.setText(legend_html(self.analysis_type.currentIndex(), self.band_colors, self.cutoffs.text()))
            self.preview.update()
        layer = self.points.currentLayer()
        road = self.roads.currentLayer()
        source = 'OpenStreetMap / otomatik alan' if self.source.currentIndex() else (road.name() if road else 'Yol katmanı seçilmedi')
        count = layer.selectedFeatureCount() if layer and self.selected.isChecked() else (layer.featureCount() if layer else 0)
        crs = layer.crs().authid() if layer else '—'
        self.summary.setText('Kaynak: %s\nBaşlangıç: %d\nGirdi CRS: %s\nEşikler: %s m\nBağlanma: %g m\nYol dışı pay: %g m' %
            (source, count, crs, self.cutoffs.text(), self.snap.value(), self.offroad.value()))
        if hasattr(self, 'analysis_type') and self.analysis_type.currentIndex():
            self.summary.setText('%s\nKaynak: %s\nAzami ağ mesafesi: %g m\nYola bağlanma: %g m' % (self.analysis_type.currentText(),source,self.route_limit.value(),self.snap.value()))
        if self.analysis_type.currentIndex() == 0 and self.use_barriers.isChecked():
            self.summary.setText(self.summary.text() + '\nKapalı bölgeler: ' + (self.barrier_layer.currentLayer().name() if self.barrier_layer.currentLayer() else 'Katman seçin'))
        self.validation.setText('Parametreler değiştiyse çalıştırmadan önce yeniden doğrulayın.')

    def validate_inputs(self):
        try:
            inputs = self.prepare()
            self.validation.setText('✓ Girdiler geçerli\n%d başlangıç · %d yol özelliği\nAnaliz CRS: %s\n%s' % (
                len(inputs['points']), len(inputs['roads']), inputs['crs'].authid(),
                'OSM indirme analizde yapılacak.' if inputs['source'] == 'osm' else 'Topoloji ağ oluşturulurken denetlenecek.'))
        except Exception as exc:
            self.validation.setText('Düzeltme gerekli\n' + str(exc))

    def choose_output(self):
        path, _ = QFileDialog.getSaveFileName(self.dialog, 'Yeni GeoPackage çıktı dosyası', 'spatium_sonuc.gpkg', 'GeoPackage (*.gpkg)')
        if path:
            self.output_path.setText(path if path.lower().endswith('.gpkg') else path + '.gpkg')

    def load_demo(self):
        path = Path(__file__).parent / 'demo' / 'spatium_demo.gpkg'
        if not path.exists():
            QMessageBox.warning(self.dialog, 'Örnek veri', 'Örnek GeoPackage pakette bulunamadı.')
            return
        project = QgsProject.instance()
        group = project.layerTreeRoot().addGroup('Spatium · Sentetik test verisi')
        layers = {}
        for key, title, color in [('demo_population','Nüfus bölgeleri','#d5e1e8'),
                                  ('demo_roads','Yol ağı','#698697'),
                                  ('demo_services','Hizmet noktaları','#d89736'),
                                  ('demo_stops','Başlangıç durakları','#148d7c')]:
            layer = QgsVectorLayer(str(path) + '|layername=' + key, title, 'ogr')
            if not layer.isValid():
                raise ValueError('Örnek katman okunamadı: ' + key)
            layer.renderer().symbol().setColor(QColor(color))
            if key == 'demo_population':
                layer.setOpacity(0.35)
            project.addMapLayer(layer, False)
            group.insertLayer(0, layer)
            layers[key] = layer
        extent = QgsCoordinateTransform(layers['demo_roads'].crs(),
            self.iface.mapCanvas().mapSettings().destinationCrs(), project.transformContext()).transformBoundingBox(layers['demo_roads'].extent())
        extent.scale(1.15)
        self.iface.mapCanvas().setExtent(extent)
        self.iface.mapCanvas().refresh()
        self.source.setCurrentIndex(0)
        self.roads.setLayer(layers['demo_roads'])
        self.points.setLayer(layers['demo_stops'])
        self.id_field.setField('stop_id')
        self.targets.setLayer(layers['demo_stops'])
        self.target_id.setField('stop_id')
        if self.target_feature.count() > 1: self.target_feature.setCurrentIndex(1)
        self.planar.setChecked(True)
        self.cutoffs.setText('400, 800')
        self.snap.setValue(10)
        self.offroad.setValue(50)
        self.run_name.setText('Sentetik ağ · 400 / 800 m')
        self.refresh_summary()
        self.status.setText('Örnek veri hazır · Beklenen: 4 bağlanan, 2 atlanan başlangıç.')

    def import_roads(self):
        # Native QGIS dialog supports choosing layers within GPKG / FileGDB.
        self.iface.actionAddOgrLayer().trigger()

    def prepare(self):
        project = QgsProject.instance()
        context = project.transformContext()
        layer = self.points.currentLayer()
        if not layer or not layer.isValid() or not layer.crs().isValid():
            raise ValueError("Geçerli CRS'si olan bir başlangıç nokta katmanı seçin.")
        mode = ['service','shortest','nearest','matrix'][self.analysis_type.currentIndex()]
        cutoffs = parse_distances(self.cutoffs.text()) if mode == 'service' else [self.route_limit.value()]
        transform_web = QgsCoordinateTransform(layer.crs(), QgsCoordinateReferenceSystem("EPSG:4326"), context)
        if mode == 'shortest':
            fid = self.origin_feature.currentData()
            if fid is None: raise ValueError('Başlangıç noktası seçin.')
            features = [layer.getFeature(fid)]
        else:
            features = list(islice(layer.getSelectedFeatures() if self.selected.isChecked() else layer.getFeatures(), 101))
        if not 1 <= len(features) <= 100:
            raise ValueError("Geliştirme sürümünde 1–100 başlangıç noktası seçin.")
        web_points = []
        for f in features:
            geom = f.geometry()
            if geom.isEmpty() or geom.isMultipart() or QgsWkbTypes.geometryType(geom.wkbType()) != QgsWkbTypes.PointGeometry:
                raise ValueError("Boş veya çok parçalı başlangıç noktası var; tek noktalara dönüştürün.")
            web_points.append(transform_web.transform(QgsPointXY(geom.asPoint())))
        west, east = min(p.x() for p in web_points), max(p.x() for p in web_points)
        south, north = min(p.y() for p in web_points), max(p.y() for p in web_points)
        if east - west > 2 or north - south > 2 or south < -80 or north > 84:
            raise ValueError("Başlangıç noktaları yerel UTM analizi için çok geniş bir alana yayılıyor.")
        lon, lat = (west + east) / 2, (south + north) / 2
        zone = min(60, max(1, int((lon + 180) / 6) + 1))
        crs = QgsCoordinateReferenceSystem("EPSG:%d" % ((32600 if lat >= 0 else 32700) + zone))
        transform_metric = QgsCoordinateTransform(layer.crs(), crs, context)
        field = self.id_field.currentField()
        identifiers = []
        for feature in features:
            if not field:
                identifiers.append(str(feature.id()))
            else:
                value = feature[field]
                identifiers.append('' if QgsVariantUtils.isNull(value) else str(value).strip())
        if any(not value for value in identifiers) or len(set(identifiers)) != len(identifiers):
            raise ValueError('Başlangıç kimlikleri boş veya tekrarlı. Benzersiz bir alan seçin.')
        points = [(identifier, tuple_xy(transform_metric.transform(QgsPointXY(f.geometry().asPoint())))) for identifier, f in zip(identifiers, features)]
        targets = []
        same_layer = False
        if mode != 'service':
            target_layer = self.targets.currentLayer()
            if not target_layer or not target_layer.isValid() or not target_layer.crs().isValid():
                raise ValueError('Geçerli hedef/tesis nokta katmanı seçin.')
            if mode == 'shortest':
                fid = self.target_feature.currentData()
                if fid is None: raise ValueError('Hedef noktası seçin.')
                target_features = [target_layer.getFeature(fid)]
            else:
                target_features = list(islice(target_layer.getSelectedFeatures() if self.target_selected.isChecked() else target_layer.getFeatures(), 101))
            if not 1 <= len(target_features) <= 100:
                raise ValueError('1–100 hedef/tesis noktası seçin.')
            to_metric = QgsCoordinateTransform(target_layer.crs(), crs, context)
            to_web = QgsCoordinateTransform(target_layer.crs(), QgsCoordinateReferenceSystem('EPSG:4326'), context)
            target_field = self.target_id.currentField()
            for feature in target_features:
                geom = feature.geometry()
                if geom.isEmpty() or geom.isMultipart() or QgsWkbTypes.geometryType(geom.wkbType()) != QgsWkbTypes.PointGeometry:
                    raise ValueError('Hedefler tek nokta geometrisi olmalı.')
                web = to_web.transform(QgsPointXY(geom.asPoint()))
                if not (-80 <= web.y() <= 84) or abs(web.x()-lon)>2 or abs(web.y()-lat)>2:
                    raise ValueError('Hedefler yerel analiz alanına yakın olmalı (en fazla 2°).')
                value = feature[target_field] if target_field else feature.id()
                if QgsVariantUtils.isNull(value) or not str(value).strip():
                    raise ValueError('Hedef kimlikleri boş olamaz.')
                targets.append((str(value).strip(), tuple_xy(to_metric.transform(QgsPointXY(geom.asPoint())))))
            if len({sid for sid,_ in targets}) != len(targets):
                raise ValueError('Hedef kimlikleri benzersiz olmalı.')
            same_layer = target_layer.id() == layer.id()
            if same_layer:
                # Identity comparisons must use the same field for both roles.
                if target_field != field:
                    raise ValueError('Aynı katman için başlangıç ve hedef kimlik alanlarını aynı seçin.')
            if mode == 'shortest' and (len(points) != 1 or len(targets) != 1):
                raise ValueError('En kısa yol için bir başlangıç ve bir hedef seçin. Katmandaki seçimleri kullanabilirsiniz.')
        coverage_points = points + targets
        margin = cutoffs[-1] + self.snap.value() + self.offroad.value() + 100
        bounds = QgsRectangle(min(p[0] for _, p in coverage_points)-margin, min(p[1] for _, p in coverage_points)-margin,
                              max(p[0] for _, p in coverage_points)+margin, max(p[1] for _, p in coverage_points)+margin)
        barriers = []
        barrier_name = None
        if mode == 'service' and self.use_barriers.isChecked():
            barrier_layer = self.barrier_layer.currentLayer()
            if not barrier_layer or not barrier_layer.isValid() or not barrier_layer.crs().isValid():
                raise ValueError('Geçerli CRS olan erişime kapalı bölge poligon katmanı seçin.')
            transform = QgsCoordinateTransform(barrier_layer.crs(), crs, context)
            inverse = QgsCoordinateTransform(crs, barrier_layer.crs(), context)
            request = QgsFeatureRequest().setFilterRect(inverse.transformBoundingBox(bounds))
            for feature in barrier_layer.getFeatures(request):
                geom = QgsGeometry(feature.geometry())
                if geom.isEmpty() or QgsWkbTypes.geometryType(geom.wkbType()) != QgsWkbTypes.PolygonGeometry or not geom.isGeosValid():
                    raise ValueError('Kapalı bölge geometrisi geçersiz (özellik %s). Geometrileri Düzelt aracını kullanın.' % feature.id())
                geom = QgsGeometry(geom.constGet().segmentize())
                geom.transform(transform)
                barriers.append(geom)
                if len(barriers) > 10000: raise ValueError('En fazla 10.000 kapalı bölge poligonu desteklenir.')
            barrier_name = barrier_layer.name()
        roads, bbox = [], None
        source = "user_network" if self.source.currentIndex() == 0 else "osm"
        if source == "user_network":
            if not self.planar.isChecked():
                raise ValueError("Düzlemsel ağ doğrulamasını işaretleyin. Köprü/tünel içeren ağlar bu prototipte desteklenmiyor.")
            road_layer = self.roads.currentLayer()
            if not road_layer or not road_layer.isValid() or not road_layer.crs().isValid():
                raise ValueError("Geçerli CRS'si olan bir yol çizgi katmanı seçin.")
            to_road = QgsCoordinateTransform(crs, road_layer.crs(), context)
            request = QgsFeatureRequest().setFilterRect(to_road.transformBoundingBox(bounds))
            to_metric = QgsCoordinateTransform(road_layer.crs(), crs, context)
            for f in road_layer.getFeatures(request):
                geom = QgsGeometry(f.geometry())
                if geom.isEmpty():
                    continue
                if not geom.isGeosValid():
                    raise ValueError("Yol geometrisi geçersiz (özellik %s). Önce Geometrileri Düzelt aracını kullanın." % f.id())
                geom = QgsGeometry(geom.constGet().segmentize())
                geom.transform(to_metric)
                roads.append(geom)
                if len(roads) > 50000:
                    raise ValueError("En fazla 50.000 yol özelliği; çalışma alanını küçültün.")
            if not roads:
                raise ValueError('Başlangıçların çevresinde yol geometrisi bulunamadı. Yol CRS ve konumunu kontrol edin.')
        else:
            coverage = QgsCoordinateTransform(crs, QgsCoordinateReferenceSystem("EPSG:4326"), context).transformBoundingBox(bounds)
            bbox = (coverage.yMinimum(), coverage.xMinimum(), coverage.yMaximum(), coverage.xMaximum())
            osm.validate_bbox(bbox)
        output = self.output_path.text().strip()
        if output:
            target = Path(output).expanduser()
            if target.suffix.lower() != '.gpkg':
                raise ValueError('Kalıcı çıktı için .gpkg uzantısı kullanın.')
            if target.exists() or target.with_suffix('.metadata.json').exists() or target.with_suffix('.summary.csv').exists():
                raise ValueError('Çıktı dosyası veya yan raporu zaten var. Yeni bir dosya adı seçin.')
            if not target.parent.is_dir():
                raise ValueError('Çıktı klasörü bulunamadı.')
            output = str(target)
        return {"barriers": barriers, "barrier_name": barrier_name, "mode": mode, "targets": targets, "same_layer": same_layer, "output": output, "name": self.run_name.text().strip() or 'Network · Hizmet alanı', "id_field": field, "roads": roads, "points": points, "cutoffs": cutoffs, "snap": self.snap.value(),
                "overlap": self.overlap.currentIndex() == 0, "colors": list(self.band_colors), "offroad": self.offroad.value(), "crs": crs, "context": context, "source": source, "bbox": bbox}

    def run(self):
        if self.task:
            return
        try:
            inputs = self.prepare()
        except Exception as exc:
            QMessageBox.warning(self.dialog, "Analiz girdileri", str(exc))
            return
        self.started_at = monotonic()
        self.input_panel.setEnabled(False)
        self.appearance_panel.setEnabled(False)
        self.validate_button.setEnabled(False)
        self.demo_button.setEnabled(False)
        self.start.setEnabled(False)
        self.cancel.setEnabled(True)
        self.progress.setValue(0)
        self.status.setText("OSM indiriliyor / ağ hesaplanıyor…")
        self.task = AnalysisTask(inputs, self.completed)
        self.task.progressChanged.connect(lambda value: self.progress.setValue(int(value)))
        QgsApplication.taskManager().addTask(self.task)

    def completed(self, task, successful):
        self.task = None
        self.input_panel.setEnabled(True)
        self.appearance_panel.setEnabled(True)
        self.validate_button.setEnabled(True)
        self.demo_button.setEnabled(True)
        self.start.setEnabled(True)
        self.cancel.setEnabled(False)
        if not successful:
            self.status.setText("İptal edildi." if task.isCanceled() else "Analiz başarısız: " + (task.error or "Bilinmeyen hata"))
            return
        try:
            layers = self.layers(task.result, task.inputs["crs"], task.inputs)
            stamp = datetime.now(timezone.utc).isoformat()
            group = QgsProject.instance().layerTreeRoot().addGroup(task.inputs['name'] + ' · ' + datetime.now().strftime('%H:%M:%S'))
            for layer in layers:
                layer.setCustomProperty("spatium/source", task.inputs["source"])
                layer.setCustomProperty("spatium/overlap", task.inputs["overlap"])
                layer.setCustomProperty("spatium/created_utc", stamp)
                layer.setCustomProperty("spatium/model", "bidirectional_walking_distance_midpoint_25m" if task.inputs["mode"] == "service" else "bidirectional_walking_shortest_distance")
                if task.inputs["source"] == "osm":
                    layer.setCustomProperty("spatium/attribution", "© OpenStreetMap contributors — ODbL")
                QgsProject.instance().addMapLayer(layer, False)
                group.insertLayer(0, layer)
            self.progress.setValue(100)
            self.status.setText("Tamamlandı: %d nokta bağlandı, %d nokta atlandı. %s" % (
                len(task.result["snapped"]), len(task.result["skipped"]),
                "© OpenStreetMap contributors" if task.inputs["source"] == "osm" else "Kullanıcı yol ağı"))
            self.show_results(task.result, layers, task.inputs)
            self.save_results(layers, task.inputs, stamp)
        except Exception as exc:
            QMessageBox.warning(self.dialog, "Sonuç kaydı", str(exc))

    def show_results(self, result, layers, inputs):
        self.last_result = result
        self.metric_labels['accepted'].setText(str(len(result['snapped'])))
        self.metric_labels['skipped'].setText(str(len(result['skipped'])))
        self.metric_labels['layers'].setText(str(len(layers)))
        self.result_info.setText('%s · %s · %.1f sn · Metre / m² · %s' % (
            inputs['name'], inputs['crs'].authid(), monotonic() - self.started_at,
            '© OpenStreetMap contributors' if inputs['source'] == 'osm' else 'Kullanıcı yol ağı'))
        records = [(s['id'], 'Bağlandı', s['snap_m'], 'Ağ hesabına dahil') for s in result['snapped']]
        records += [(sid, 'Atlandı', distance, result.get('skip_reasons', {}).get(sid, 'Bağlanma toleransı dışında')) for sid, coord, distance in result['skipped']]
        self.result_table.setRowCount(len(records))
        for row, (sid, state, distance, reason) in enumerate(records):
            for col, text in enumerate([sid, state, '—' if distance is None else '%g' % round(distance,3), reason]):
                self.result_table.setItem(row, col, QTableWidgetItem(text))
        if inputs['mode'] != 'service':
            self.result_info.setText(self.result_info.text() + '\nRota bulunamayan kayıtlar çıktının status alanında belirtilir; mesafeler çift yönlü yaya ağı üzerinde hesaplanır.')
        if inputs['mode'] != 'service':
            self.result_table.setHorizontalHeaderLabels(['Başlangıç', 'Hedef / tesis', 'Ağ mesafesi (m)', 'Durum'])
            self.result_table.setRowCount(len(result['routes']))
            labels = {'ok':'Rota bulundu', 'snap_failed':'Yola bağlanamadı',
                      'unreachable_or_over_limit':'Kopuk ağ veya limit dışında',
                      'no_facility_within_limit':'Limit içinde tesis bulunamadı'}
            for row,(sid,tid,distance,state,geom) in enumerate(result['routes']):
                for col,value in enumerate([sid,tid,'—' if distance is None else '%g' % round(distance,2),labels.get(state,state)]):
                    self.result_table.setItem(row,col,QTableWidgetItem(value))
        else:
            self.result_table.setHorizontalHeaderLabels(['Başlangıç kimliği', 'Durum', 'Yola uzaklık (m)', 'Açıklama'])
        self.tabs.setCurrentIndex(1)

    def layers(self, result, crs, inputs):
        if inputs.get('mode', 'service') != 'service':
            fields = [('source_id', QVariant.String), ('target_id', QVariant.String),
                      ('distance_m', QVariant.Double), ('status', QVariant.String)]
            rows = [([sid,tid,distance,status],geom) for sid,tid,distance,status,geom in result['routes']]
            matrix = inputs['mode'] == 'matrix'
            title = {'shortest':'En kısa yol', 'nearest':'En yakın tesis', 'matrix':'Başlangıç–hedef mesafeleri'}[inputs['mode']]
            layer = output_layer(title, 'None' if matrix else 'LineString', fields, rows, crs)
            if not matrix:
                layer.renderer().symbol().setColor(QColor('#2563eb'))
            return [layer]
        fields = [("source_id", QVariant.String), ("from_m", QVariant.Double),
                  ("to_m", QVariant.Double), ("band", QVariant.String),
                  ("snap_m", QVariant.Double), ("area_m2", QVariant.Double)]
        rows = [([sid, low, high, '%g–%g m' % (low, high), snap, geom.area()], geom)
                for sid, low, high, snap, geom in result['rings']]
        layer = output_layer('Hizmet alanı · Mesafe bantları', 'MultiPolygon', fields, rows, crs)
        categories = []
        cutoffs = inputs['cutoffs']
        palette = inputs['colors']
        lower = 0
        for idx, cutoff in enumerate(cutoffs):
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setColor(QColor(palette[0 if len(cutoffs) == 1 else round(idx * 2 / (len(cutoffs) - 1))]))
            categories.append(QgsRendererCategory(cutoff, symbol, '%g–%g m' % (lower, cutoff)))
            lower = cutoff
        layer.setRenderer(QgsCategorizedSymbolRenderer('to_m', categories))
        layer.setOpacity(0.65)
        return [layer]

    def save_results(self, layers, inputs, stamp):
        path = inputs['output']
        if not path:
            return
        target = Path(path)
        if target.suffix.lower() != ".gpkg":
            target = target.with_suffix(".gpkg")
        if target.exists() or target.with_suffix('.metadata.json').exists() or target.with_suffix('.summary.csv').exists():
            raise ValueError("Mevcut dosya korunuyor. Yeni bir GeoPackage adı seçin; sonuçlar QGIS'te mevcut.")
        for i, layer in enumerate(layers):
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = "service_area" if inputs["mode"] == "service" else inputs["mode"]
            options.actionOnExistingFile = (QgsVectorFileWriter.CreateOrOverwriteFile if i == 0 else QgsVectorFileWriter.CreateOrOverwriteLayer)
            result = QgsVectorFileWriter.writeAsVectorFormatV3(layer, str(target), QgsProject.instance().transformContext(), options)
            if result[0] != QgsVectorFileWriter.NoError:
                raise ValueError("GeoPackage kaydı tamamlanamadı (kısmi dosya olabilir): " + str(result[1]))
        metadata = {"version": "0.4.0", "analysis": inputs["mode"], "barrier_layer": inputs["barrier_name"], "barrier_count": len(inputs["barriers"]), "run_name": inputs["name"], "id_field": inputs["id_field"], "created_utc": stamp, "source": inputs["source"],
                    "overlap": inputs["overlap"], "overlap_priority": "smallest distance band, then input point order", "colors_inner_to_outer": inputs["colors"], "distances_m": inputs["cutoffs"], "snap_m": inputs["snap"], "offroad_m": inputs["offroad"],
                    "crs": inputs["crs"].authid(), "bbox_wgs84": inputs["bbox"],
                    "model": "bidirectional walking; 25m midpoint buffer; snap distance not charged",
                    "attribution": "© OpenStreetMap contributors — ODbL" if inputs["source"] == "osm" else None}
        # Keep provenance inside the same GeoPackage rather than separate files.
        import sqlite3
        with sqlite3.connect(target) as db:
            db.execute('CREATE TABLE IF NOT EXISTS gpkg_metadata (id INTEGER PRIMARY KEY ASC, md_scope TEXT NOT NULL DEFAULT \'dataset\', md_standard_uri TEXT NOT NULL, mime_type TEXT NOT NULL DEFAULT \'text/xml\', metadata TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS gpkg_metadata_reference (reference_scope TEXT NOT NULL, table_name TEXT, column_name TEXT, row_id_value INTEGER, timestamp DATETIME NOT NULL, md_file_id INTEGER NOT NULL, md_parent_id INTEGER)')
            db.execute('CREATE TABLE IF NOT EXISTS gpkg_extensions (table_name TEXT, column_name TEXT, extension_name TEXT NOT NULL, definition TEXT NOT NULL, scope TEXT NOT NULL, UNIQUE(table_name,column_name,extension_name))')
            for table in ('gpkg_metadata', 'gpkg_metadata_reference'):
                db.execute('INSERT INTO gpkg_extensions VALUES (?,NULL,?,?,?)', (table, 'gpkg_metadata', 'http://www.geopackage.org/spec/#extension_metadata', 'read-write'))
            cursor = db.execute('INSERT INTO gpkg_metadata (md_scope,md_standard_uri,mime_type,metadata) VALUES (?,?,?,?)', ('dataset','https://spatiumlabs.com/network','application/json',json.dumps(metadata,ensure_ascii=False)))
            db.execute('INSERT INTO gpkg_metadata_reference VALUES (?,?,?,?,?,?,?)', ('table','service_area' if inputs['mode']=='service' else inputs['mode'],None,None,stamp,cursor.lastrowid,None))
        self.status.setText(self.status.text() + "\nKaydedildi: " + str(target))


def tuple_xy(point):
    return (point.x(), point.y())
