# Third-party models and imagery

No model weights or third-party imagery are bundled with this plugin.
Weights are downloaded into a separate user-selected model environment/cache.
Users must comply with each model and imagery source's current terms.

- SegFormer land cover: https://huggingface.co/boehnen/satlens-segformer
  pinned revision `19cdd879e535d76e7fcbbd1e8b54dac9c1da90d6`; model card declares MIT.
- HOTOSM DINOv3s Buildings: https://huggingface.co/hotosm/dinov3s-buildings
  pinned revision `f7254545dfbbf10a40594d5a5fb62136902000ae`; model card declares
  CC-BY-4.0 and identifies separate DINOv3 backbone terms. Attribution is to
  Humanitarian OpenStreetMap Team and the named model authors. Backbone terms:
  https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md
- Optional Grounding DINO: https://huggingface.co/IDEA-Research/grounding-dino-tiny
- Optional SAM: https://huggingface.co/facebook/sam-vit-base
- User-provided ONNX models: source/weight licenses must be supplied by their owner.
- Google imagery, when visible in QGIS, remains subject to Google terms:
  https://maps.google.com/help/terms_maps/ . No Google tiles are included or scraped.

Review model cards, backbone terms and image-source licenses before commercial use.
The plugin license does not grant rights to third-party weights, training data or imagery.
Local processing does not override those terms.
