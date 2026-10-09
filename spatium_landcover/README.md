# Spatium Labs Vision

RGB segmentation and editable candidate polygons for QGIS 3.28–3.x.
Public preview 0.5.0; GPL-2.0-or-later. Turkish interface.

## Installation (Windows, Linux, macOS)

1. Install the ZIP with **Plugins → Manage and Install Plugins → Install from ZIP**.
2. Open **Spatium Labs → Vision**. Install Python **3.10–3.12** separately
   from https://www.python.org/downloads/ if a compatible interpreter is unavailable.
3. In **Model environment**, choose that Python executable and create the isolated
   environment with the setup button. On Windows select `python.exe`; on macOS/Linux
   select the executable file, not a folder. QGIS Python is never modified.
4. Check the environment. Dependencies require internet, disk space and time;
   the first inference downloads pretrained weights from Hugging Face.
5. Load a local georeferenced RGB raster or choose **Visible map image**.
   Select your analysis area/classes and a **new** GeoPackage filename, then run.

Visible-map mode analyzes the current loaded raster imagery at its visible
resolution. Rotation must be 0°. It does not increase optical resolution or
crawl Google tiles. Visible vectors are temporarily hidden and then restored.
Model inference is local; input images are not sent to a remote inference API.
A licensed XYZ profile is optional, subject to source permission and request limits.
The plugin does not include Google imagery, model weights or a hosted service.

Results are one editable polygon layer with class colours, scores, review status
and metric areas. Simplification reduces pixel staircases. Candidate classes:
buildings, road surface, trees, grass/shrub, water, agriculture candidate, built
open surface and bare ground. A road polygon is **not** a routing network line.
Review and edit results before use. Scores are not verified accuracy percentages.
RGB classes do not establish crop identity, legal land use or cadastral boundaries.

The model environment uses numpy, rasterio, shapely, pyproj, fiona, Pillow, torch,
torchvision, transformers and onnxruntime. CPU inference is supported; compatible
CUDA can be used. Processing speed depends on hardware and scene size.
Training export creates reviewed spatially split image/label samples; it does not
train a model automatically. External ONNX profiles support later custom models.

Model/source terms are separate from the plugin GPL. See **THIRD_PARTY.md**.
Support: https://github.com/melihanileroglu/SpatiumLabs-QGIS/issues

## Türkçe kullanım ve yöntem


## Görünen haritayı analiz et

Varsayılan kaynak **Görünen harita görüntüsü**dür. QGIS'te uydu görüntüsünü açın, istediğiniz ölçekte yaklaşın, gerekirse analiz alanı çizin ve Poligonları çıkar'a basın. Mevcut yüklenmiş harita görüntüsü PNG olarak alınır, görünüm sınırı ve CRS ile koordinatlandırılır ve seçili gerçek modelde parçalı işlenir. Görünür vektörler yakalama sırasında gizlenir; katmanların önceki görünürlüğü geri yüklenir. Sentetik test poligonları ana analizde kullanılmaz. Google dahil görünen XYZ katmanları bu ekran yakalama yolunda kullanılabilir; kaynak kullanım koşulları geçerlidir. Toplu Google karo indirme veya otomatik zoom taraması yapılmaz. Ekran çözünürlüğü optik kaynak çözünürlüğü değildir; harita dönüşü 0° olmalıdır.

0.2.0'da varsayılan bina motoru **[HOTOSM DINOv3s Buildings](https://huggingface.co/hotosm/dinov3s-buildings)** oldu. VHR hava/uydu bina verisiyle eğitilmiştir; 256 piksel pencereler, 128 piksel adım ve ağırlıklı dikiş uygulanır. Girdi normalizasyonu HOT eğitim istatistikleriyle yapılır. İlk çıktı kanalına sigmoid uygulanır; sınır kanalının tahmini bitişik çatılarda ayrım için kullanılır. Varsayılan eşik 0.4371. Bu motor sadece bina sınıfı verir; tarla/su tahmini yapmaz. Genel amaçlı Grounding DINO + SAM ayrı profilde korunur fakat yoğun kent uydu görüntülerinde büyük yanlış maskeler üretebildiği için varsayılan değildir. HOTOSM model ağırlıkları CC-BY-4.0 kapsamındadır; DINOv3 omurgasının ayrı koşulları da geçerlidir. Model kaynağı ve atıf bu profil ve çıktı iş kaydında tutulur.

Yerel RGB dosyası ve lisanslı XYZ edinim modları ayrıca kullanılabilir. Aşağıdaki özgün çözünürlük bilgileri yerel dosya modu içindir.

QGIS eklentisi; Network'ten bağımsızdır. Haritada dikdörtgen çizin veya seçili poligonları kullanın. Koordinatlı **yerel 8 bit RGB** görüntü özgün çözünürlüğünde 256/512/768 piksel çekirdeklere bölünür; her parçaya 64 piksel bağlam payı eklenir. Çekirdek sahipliği her pikseli yalnızca bir parçadan alır. Maskeler birleştirilip tek `objects` poligon katmanı olarak GeoPackage'a kaydedilir. NoData ve AOI dışı pikseller dışlanır; alan hesabı yerel UTM CRS'inde yapılır.

**Görüntü edinimi:** Google Earth ekranını otomatik yaklaştırıp indirme veya Google/XYZ karo toplama uygulanmaz. Kullanım izni olan GeoTIFF/ortofoto veya koordinatlandırılmış görüntü gereklidir. Google Earth ekran görüntüsünü kullanma yetkiniz varsa önce QGIS Georeferencer ile konumlandırın. Kaynak, tarih ve kullanım izni kayıtla birlikte tutulur. Kaynak GSD'den daha fazla ayrıntı üretilmez. Eğik görüntü önce ortorektifiye edilmelidir; ekran koordinatlandırması çatıların arazi düzlemindeki yer kaymasını gidermez.

İzinli **XYZ sağlayıcı** JSON profiliyle seçili alan otomatik RGB GeoTIFF olarak alınabilir: `name`, `url=https://.../{z}/{x}/{y}.png`, `native_zoom`, `bulk_analysis_allowed=true`, `license_note`, isteğe bağlı `max_tiles` (varsayılan 256, mutlak sınır 1024). Sağlayıcı 256 × 256 HTTPS XYZ karo döndürmelidir; TMS/y ters yönü desteklenmez. Native zoom sağlayıcının beyanıdır; optik çözünürlük bağımsız doğrulanmış sayılmaz. Alfa kanalı korunur. İndirme sırayla ve saniyede en fazla 10 istekle yapılır; hata durumunda eksik görüntü çıktı olarak sunulmaz. Hazır Google sağlayıcısı veya lisanslı bir servis hesabı pakete dahil değildir. Adres/API anahtarlarını Git'e eklemeyin.

**Hazır motor:** Hugging Face Transformers üzerinden `IDEA-Research/grounding-dino-tiny` ve `facebook/sam-vit-base`. Bunlar genel amaçlı nesne bulma/segmentasyon modelleridir; İstanbul bina ve tarla doğruluğu ölçülmüş değildir. Sınıflar bina çatısı, tarla ve su yüzeyi **adaylarıdır**. Model skoru doğruluk yüzdesi değildir. Tek tarihli RGB görüntüden tarım kullanımı, ürün türü veya kadastro parseli belirlenmiş sayılmaz. Bitişik aynı sınıf maskeleri birleşir. Farklı sınıflar çakışırsa profil sırası önceliklidir.

**Ortam:** QGIS Python'una paket kurulmaz. Model ortamı sekmesinden Python 3.10–3.12 seçilip ayrı sanal ortam kurulabilir. İlk analiz model ağırlıklarını indirir; sonraki çalışmalar önbelleği kullanır. Yerel görüntüler dışarı gönderilmez. GPU varsa CUDA, aksi halde CPU kullanılır. Büyük alanlarda CPU yavaş olabilir. İş sınırı 100 milyon piksel, 4096 parça ve 400 km².

**Esneklik:** JSON model profiliyle hedef isimleri, İngilizce prompt'lar, renkler, hazır model kimlikleri değiştirilebilir. `engine=onnx` bir özel anlamsal segmentasyon modelini çalıştırır: float32 NCHW RGB girdi, tek NCHW sınıf-logit çıktısı. `weights`, `input_size`, `channels`, `mean`, `std` tanımlayın. `channels=[0,1,2,3]` örneğinde kanal sırası arka plan/bina/tarla/sudur. Profil içindeki sınıf kimlikleri çıktı ile eşleşmelidir. Arka plan 0, yok sayılan eğitim pikseli 255. ONNX profilinde yerel weights yolu profil dosyasına göre çözülür. Python kodu içeren model eklentileri çalıştırılmaz.

**Doğrulama/eğitim:** Poligonları elle düzeltin, `class_id` belirleyin ve doğruladıklarınızın `review` alanını `accepted` yapın. Atlanan nesneleri ve gerçek arka plan örneklerini ekleyin. Çakışan etiketler reddedilir. Eğitim dışa aktarma 256 piksel RGB/etiket GeoTIFF'leri ve `dataset.json` üretir. Train, validation, test ayrı mekânsal sütunlardır; rastgele piksel ayrımı yapılmaz. Veri seti hazırlama model eğitimi değildir. Model eğitimi dışarıda gerçekleştirilip ONNX ile geri alınır. Komşu mekânsal bloklar hâlâ benzer olabilir; farklı konum/tarihte bağımsız doğrulama gerekir.

## Geliştirici kontrolleri

`python -m unittest discover -s tests` ağ ve taşınabilir parçalama testlerini çalıştırır. Raster bağımlılıkları olan ayrı ortamda `python -m unittest tests/earth_integration.py` gerçek TIFF, GEOS ve GPKG kontrollerini çalıştırır. `scripts/create_earth_tests.py` İstanbul koordinatlarında tamamen sentetik görüntü ve etiket üretir. `reference` motoru yalnızca bu sentetik renkleri okur; yapay zekâ değildir ve kullanıcı arayüzünde sunulmaz. Gerçek görüntü/model doğruluğu bu testlerle kanıtlanmaz.

Kaynaklar: [Grounding DINO](https://huggingface.co/IDEA-Research/grounding-dino-tiny), [SAM](https://huggingface.co/facebook/sam-vit-base), [Google Earth koşulları](https://maps.google.com/intl/en_all/help/terms_maps-earth/). Model ve görüntü lisansları eklenti lisansından bağımsızdır.

## Vision · Arazi örtüsü ve nesne çıkarımı

Varsayılan “Arazi örtüsü + binalar” profili aynı görüntüde bina, yol yüzeyi, ağaçlık alan, otsu/çalı örtüsü, su, tarım alanı adayı, yapılaşmış açık yüzey ve çıplak zemini sınıflandırır. Yol çıktısı poligondur; Network analizleri için yol çizgisi/topolojisi değildir. Araçlar ve insanlar gibi küçük nesneler bu sınıflandırma profiline dahil değildir.

Bina sınırları HOTOSM DINOv3 ONNX modeliyle, diğer sınıflar `boehnen/satlens-segformer` modeliyle çıkarılır. SegFormer sınıf kimlikleri modelin config.json tanımlarıyla doğrulanır; uyuşmazlıkta işlem durur. Ağırlık sürümleri sabittir. Model, görüntüyü 512 piksel pencerelerle işler; daha küçük görüntü kenarları doldurulur, görüntü büyütülerek sahte ayrıntı oluşturulmaz. Skor eşiği her iki modele uygulanır.

Tek GeoPackage katmanında `class_id` / `class_name` ile sınıflar tutulur. Binalar örtüşen sınıflara göre önceliklidir; bilinmeyen veya eşik altındaki alanlar boş kalabilir. Renkler hedeflerin yanındaki kutulardan seçilir. Network ile aynı başlık, kart, sekme ve küçük yazı düzeni kullanılır. Sağdaki şekil yalnızca renkli şematik önizlemedir.

Model testleri yazılım çalışmasını doğrular; İstanbul için etiketli bağımsız doğruluk değerlendirmesi yapılmamıştır. Tarım alanı adayı, hukuki arazi kullanımı veya kadastro tespiti değildir. Eğitim veri seti için bina=1, tarım=2, su=3 kimlikleri korunmuştur.

Model kaynakları: https://huggingface.co/boehnen/satlens-segformer ve https://huggingface.co/hotosm/dinov3s-buildings . Model lisansları eklenti lisansından ayrıdır.

## Sınır sadeleştirme (0.3.1)

Kapalı / Hafif / Dengeli / Güçlü seçenekleri sırasıyla 0 / 0.75 / 1.5 / 3 kaynak pikseli tolerans kullanır. Varsayılan Dengeli, rasterdan gelen küçük basamakları ve gereksiz vertexleri azaltır. Bina köşelerini yuvarlatan spline uygulanmaz. Ortak sınırlar eşleşiyorsa coverage sadeleştirme, aksi halde topolojiyi koruyan sadeleştirme uygulanır. Sonuçlar analiz alanına kırpılır ve sınıflar arası örtüşmeler çıkarılır. İş raporunda tolerans, yöntem ve önceki/sonraki vertex sayıları saklanır. Mevcut çıktılar otomatik değiştirilmez; yeni bir çıktı dosyasına analizi yeniden çalıştırın.
