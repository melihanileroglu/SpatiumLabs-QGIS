# Sentetik CBS test senaryosu

Bu veri seti tamamen yapaydır; gerçek yol, nüfus veya kurum bilgisi içermez. CRS: WGS 84 / UTM 35N (EPSG:32635), birim metre. Referans konumu yalnızca koordinatların makul bir CRS'de bulunması içindir.

Eklentide **Örnek projeyi yükle** düğmesiyle dört katman eklenir: 112 yol, 6 durak, 8 nüfus bölgesi, 6 hizmet noktası. Katmanlar ayrıca `spatium_demo.gpkg` içinden doğrudan QGIS'e sürüklenebilir.

1. Yol: `demo_roads`; başlangıç: `demo_stops`; kimlik: `stop_id`.
2. Eşikler 400, 800 m; bağlanma 10 m; yol dışı pay 50 m. Düzlemsel ağ doğrulamasını işaretleyin.
3. Kontrol: S01, S02, S04, S06 bağlanır; S03 (15 m), S05 (50 m) atlanır. Bağlanma çizgisi maliyet bütçesinden düşmez.
4. S04 kopuk ağ adasındadır. Erişilebilir yolları ana ızgaraya geçmemeli.
5. Bağlanmayı 20 m yapın: S03 de kabul edilir. 60 m yapın: bütün duraklar kabul edilir.
6. Her durağın 800 m kümülatif poligonu 400 m poligonunu kapsamalı; 400–800 m halkası 0–400 m halkasıyla alan olarak çakışmamalı.
7. Parametre veya kaynak kimliği alanını değiştirip yeniden çalıştırın. Sonuçlar ayrı çalışma grubunda görünmeli.
8. Sonuçları yeni GeoPackage'a kaydedin. QGIS'i yeniden açıp bu katmanların ve metrekare alanlarının korunduğunu kontrol edin.

Nüfus bölgeleri ve hizmet noktaları CBS'de örtüşme/erişim özetlerini ayrıca test etmek içindir; bu sürüm otomatik nüfus veya POI sayımı üretmez. Nüfus alan oranıyla dağıtılırsa bunun homojen dağılım varsayımı olduğunu raporlayın. Gerçek geometrik çıktı doğrulaması çalışan QGIS'te yapılmalı; `expected_results.json` poligon alanlarının doğrulandığı anlamına gelmez.
