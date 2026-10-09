# SpatiumLabs for QGIS

Two independent QGIS 3 plugins for spatial analysis. **Public preview 0.5.0**.

| Plugin | Purpose | Dependencies |
|---|---|---|
| [Network](spatium_accessibility/README.md) | Walking service-area rings, shortest paths, nearest facilities, OD distance tables and service-area polygon barriers | Native QGIS; internet only for OSM |
| [Vision](spatium_landcover/README.md) | RGB segmentation, editable multiclass polygons, simplification and reviewed training samples | Separate Python 3.10–3.12 model environment |

## Download and install

Download the plugin ZIPs from [Releases](https://github.com/melihanileroglu/SpatiumLabs-QGIS/releases/tag/v0.5.0).
In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**.
Install either or both packages. Open them from **Spatium Labs**.

The official QGIS repository submission is separate and requires review; this
GitHub release does not imply QGIS repository approval. Until approval, use ZIP
installation. If listed as experimental, enable experimental plugins in QGIS.

Network works without pip packages. Vision's **Model environment** tab creates
an isolated environment; it never installs packages into QGIS Python. First
setup/model download requires internet. See each plugin README for limitations.
The interface is currently Turkish. QGIS 4 / Qt6 is not claimed compatible.

## Validation

Validated with QGIS 3.32.3 on macOS: Network native geometry, overlap, routes,
barriers, demo providers, both plugin dialogs/module switching and intro rendering.
Vision raster/GEOS/GeoPackage integration and ONNX mapping tests passed.
Other operating systems and supported QGIS 3 versions need additional testing.
Model-output accuracy is scene-dependent; software tests do not prove geographic
or classification accuracy. All demo data is synthetic.

## Support and license

Report reproducible issues using [GitHub Issues](https://github.com/melihanileroglu/SpatiumLabs-QGIS/issues).
Include OS/QGIS versions and a small synthetic example. Do not upload confidential
imagery, private source data, API keys or licensed data without permission.

Plugin code: GPL-2.0-or-later. See [LICENSE](LICENSE).
Models, OSM and imagery have separate terms described in each plugin's THIRD_PARTY.md.
No model weights, personal datasets or credentials are in this repository.

## Türkçe

Network yaya ağında metre bazlı analizler yapar. Vision görüntüden sınıflandırılmış
aday poligonlar çıkarır. İki eklenti bağımsız kurulabilir. ZIP dosyalarını Releases
sayfasından indirin ve QGIS'teki ZIP'ten kurulum seçeneğini kullanın. Vision için
ayrı model ortamı gereklidir. Sonuçları kullanım öncesinde kontrol edin.
