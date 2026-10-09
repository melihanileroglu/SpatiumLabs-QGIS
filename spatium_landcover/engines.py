"""Replaceable mask engines. Models do not receive geospatial coordinates."""
import numpy as np

class GroundedSAM:
    def __init__(self, config):
        import os
        os.environ.setdefault('HF_HUB_ETAG_TIMEOUT','60')
        os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT','180')
        os.environ.setdefault('HF_HUB_DISABLE_XET','1')
        import torch
        from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection, SamModel, SamProcessor
        self.torch = torch
        # CPU avoids unsupported MPS operations; CUDA is used if available.
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        detector = config.get('detector','IDEA-Research/grounding-dino-tiny')
        segmenter = config.get('segmenter','facebook/sam-vit-base')
        detector_revision = config['detector_revision']
        segmenter_revision = config['segmenter_revision']
        import re
        if not all(re.fullmatch(r'[0-9a-f]{40}', revision) for revision in (detector_revision, segmenter_revision)):
            raise ValueError('Model revisions must be immutable 40-character commit IDs.')
        self.dp = AutoProcessor.from_pretrained(detector, revision=detector_revision, trust_remote_code=False)
        self.dm = AutoModelForZeroShotObjectDetection.from_pretrained(detector, revision=detector_revision, trust_remote_code=False).to(self.device).eval()
        self.sp = SamProcessor.from_pretrained(segmenter, revision=segmenter_revision, trust_remote_code=False)
        self.sm = SamModel.from_pretrained(segmenter, revision=segmenter_revision, trust_remote_code=False).to(self.device).eval()

    def predict(self, rgb, classes, threshold):
        from PIL import Image
        import inspect
        image = Image.fromarray(rgb)
        result = []
        for cls in classes:
            inputs = self.dp(images=image, text=cls['prompt'].rstrip('.')+'.', return_tensors='pt').to(self.device)
            with self.torch.inference_mode(): outputs = self.dm(**inputs)
            method = self.dp.post_process_grounded_object_detection
            key = 'threshold' if 'threshold' in inspect.signature(method).parameters else 'box_threshold'
            detection = method(outputs, inputs.input_ids, target_sizes=[image.size[::-1]],
                               text_threshold=threshold, **{key:threshold})[0]
            boxes = detection['boxes'].detach().cpu().tolist()
            if not boxes: continue
            # Bound crowded tiles; fail instead of silently losing detections.
            if len(boxes)>256: raise ValueError('Parçada 256 üzerinde nesne var; parça boyutunu küçültün.')
            for start in range(0,len(boxes),16):
                batch = self.sp(images=image, input_boxes=[boxes[start:start+16]], return_tensors='pt').to(self.device)
                with self.torch.inference_mode(): segmented = self.sm(**batch, multimask_output=False)
                masks = self.sp.image_processor.post_process_masks(segmented.pred_masks.cpu(),
                    batch['original_sizes'].cpu(), batch['reshaped_input_sizes'].cpu())[0]
                for i, mask in enumerate(masks):
                    result.append((cls['id'], np.asarray(mask[0],dtype=bool),
                                   float(detection['scores'][start+i].item())))
        return result

class OnnxSemantic:
    """Custom supervised NCHW RGB model -> NCHW class logits, no arbitrary code."""
    def __init__(self, config):
        import onnxruntime as ort
        ort.disable_telemetry_events()
        self.config = config
        self.session = ort.InferenceSession(config['weights'], providers=['CPUExecutionProvider'])
        self.input = self.session.get_inputs()[0]
        if len(self.input.shape)!=4: raise ValueError('ONNX girdisi NCHW olmalı.')
        if self.input.type!='tensor(float)' or self.input.shape[1]!=3:
            raise ValueError('ONNX girdisi float32 ve üç kanallı NCHW RGB olmalı.')

    def predict(self, rgb, classes, threshold):
        from PIL import Image
        size = int(self.config.get('input_size',512))
        arr = np.asarray(Image.fromarray(rgb).resize((size,size),Image.Resampling.BILINEAR), dtype=np.float32)/255
        mean=np.array(self.config.get('mean',[0,0,0]),dtype=np.float32)
        std=np.array(self.config.get('std',[1,1,1]),dtype=np.float32)
        if np.any(std<=0): raise ValueError('ONNX std değerleri pozitif olmalı.')
        logits=self.session.run(None,{self.input.name:((arr-mean)/std).transpose(2,0,1)[None]})[0]
        if logits.ndim!=4 or logits.shape[0]!=1: raise ValueError('ONNX çıktısı 1 × sınıf × yükseklik × genişlik olmalı.')
        if not np.isfinite(logits).all(): raise ValueError('ONNX çıktısında NaN/sonsuz değer var.')
        channels=self.config['channels']
        if logits.shape[1]!=len(channels): raise ValueError('ONNX kanal ve sınıf sayıları farklı.')
        exp=np.exp(logits[0]-logits[0].max(axis=0,keepdims=True));prob=exp/exp.sum(axis=0,keepdims=True)
        labels=prob.argmax(axis=0); scores=prob.max(axis=0)
        selected={c['id'] for c in classes}; result=[]
        for channel,identifier in enumerate(channels):
            if identifier not in selected: continue
            small=(labels==channel)&(scores>=threshold)
            mask=np.asarray(Image.fromarray(small).resize((rgb.shape[1],rgb.shape[0]),Image.Resampling.NEAREST),dtype=bool)
            if mask.any(): result.append((identifier,mask,float(scores[small].mean())))
        return result

class ReferenceEngine:
    """Synthetic fixture only. Not a trained detector and never offered for real imagery."""
    def predict(self, rgb, classes, threshold):
        result=[]
        colors={1:(190,80,60),2:(80,160,60),3:(40,110,190)}
        for cls in classes:
            mask=(rgb==colors[cls['id']]).all(axis=2)
            if mask.any(): result.append((cls['id'],mask,1.0))
        return result

class BuildingONNX:
    """HOTOSM aerial building model. Native 256-pixel windows; no whole-view resize."""
    def __init__(self,config):
        import os
        os.environ.setdefault('HF_HUB_DISABLE_XET','1')
        os.environ.setdefault('HF_HUB_ETAG_TIMEOUT','60')
        os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT','180')
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        self.weights=hf_hub_download(config.get('repository','hotosm/dinov3s-buildings'),
            'model.onnx',revision=config.get('revision','main'))
        self.session=ort.InferenceSession(self.weights,providers=['CPUExecutionProvider'])
        self.input=self.session.get_inputs()[0].name
        self.mean=np.array([.4296737853453577,.4001659668453235,.34333372802741474],dtype=np.float32).reshape(3,1,1)
        self.std=np.array([.2056069389373208,.16738555558380538,.1598986422586595],dtype=np.float32).reshape(3,1,1)

    def predict(self,rgb,classes,threshold):
        if not any(c['id']==1 for c in classes): return []
        h,w=rgb.shape[:2];prob=np.zeros((h,w),dtype=np.float32);edges=prob.copy();weights=prob.copy()
        def positions(length):
            result=list(range(0,max(1,length-256+1),128))
            if result[-1]+256<length: result.append(length-256)
            return result
        axis=np.exp(-.5*((np.arange(256)-127.5)/32)**2).astype(np.float32)
        kernel=axis[:,None]*axis[None,:]
        for y in positions(h):
            for x in positions(w):
                ch,cw=min(256,h-y),min(256,w-x)
                chip=np.zeros((256,256,3),dtype='uint8');chip[:ch,:cw]=rgb[y:y+ch,x:x+cw]
                inputs=(chip.astype(np.float32).transpose(2,0,1)/255-self.mean)/self.std
                logits=self.session.run(None,{self.input:inputs[None]})[0]
                if logits.shape!=(1,3,256,256) or not np.isfinite(logits).all(): raise ValueError('Bina modeli çıktı sözleşmesi geçersiz.')
                mask_prob=1/(1+np.exp(-np.clip(logits[0,0],-40,40)))
                boundary=1/(1+np.exp(-np.clip(logits[0,1],-40,40)))
                weight=kernel[:ch,:cw]
                prob[y:y+ch,x:x+cw]+=mask_prob[:ch,:cw]*weight
                edges[y:y+ch,x:x+cw]+=boundary[:ch,:cw]*weight
                weights[y:y+ch,x:x+cw]+=weight
        prob/=weights;edges/=weights
        # Explicit predicted boundary gaps keep touching roofs from being merged.
        mask=(prob>=threshold)&(edges<.5)
        return [(1,mask,float(prob[mask].mean()))] if mask.any() else []

# Stable Earth IDs keep previously reviewed building/cropland/water labels compatible.
COVER_LABELS={1:'Bareland',2:'Rangeland',3:'Developed space',4:'Road',5:'Tree',6:'Water',7:'Agriculture land',8:'Building'}
COVER_IDS={1:8,2:6,3:7,4:5,5:4,6:3,7:2}

class LandcoverHybrid:
    """Satellite SegFormer cover + dedicated HOTOSM building footprints."""
    def __init__(self, config):
        import os
        os.environ.setdefault('HF_HUB_DISABLE_XET','1')
        os.environ.setdefault('HF_HUB_ETAG_TIMEOUT','60')
        os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT','180')
        import torch
        from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor
        self.torch=torch;self.config=config;self.buildings=None
        repo=config['cover_repository'];revision=config['cover_revision']
        self.processor=SegformerImageProcessor.from_pretrained(repo,revision=revision)
        self.model=SegformerForSemanticSegmentation.from_pretrained(repo,revision=revision,trust_remote_code=False).eval()
        labels={int(k):v for k,v in self.model.config.id2label.items()}
        if self.model.config.num_labels!=9 or any(labels.get(k)!=v for k,v in COVER_LABELS.items()):
            raise ValueError('Arazi örtüsü modelinin sınıf eşlemesi desteklenen sözleşmeyle uyuşmuyor.')
        self.device='cuda' if torch.cuda.is_available() else 'cpu';self.model.to(self.device)

    def predict(self,rgb,classes,threshold):
        selected={c['id'] for c in classes};results=[]
        if 1 in selected:
            if self.buildings is None: self.buildings=BuildingONNX(self.config['building_model'])
            results=self.buildings.predict(rgb,classes,threshold)
        if not selected.intersection(COVER_IDS.values()): return results
        torch=self.torch;h,w=rgb.shape[:2]
        # Preserve native pixel detail. Pad short chips; never stretch a whole map.
        probs=np.zeros((9,h,w),dtype=np.float32);weights=np.zeros((h,w),dtype=np.float32)
        def positions(length):
            values=list(range(0,max(1,length-512+1),384))
            if values[-1]+512<length: values.append(length-512)
            return values
        for y in positions(h):
            for x in positions(w):
                ch,cw=min(512,h-y),min(512,w-x)
                chip=np.pad(rgb[y:y+ch,x:x+cw],((0,512-ch),(0,512-cw),(0,0)),mode='edge')
                inputs=self.processor(images=chip,return_tensors='pt',do_resize=False).to(self.device)
                with torch.inference_mode():
                    logits=self.model(**inputs).logits
                    if logits.shape[1]!=9 or not torch.isfinite(logits).all(): raise ValueError('Arazi örtüsü modeli geçersiz çıktı üretti.')
                    prob=torch.nn.functional.interpolate(logits,size=(512,512),mode='bilinear',align_corners=False).softmax(dim=1)[0].cpu().numpy()
                probs[:,y:y+ch,x:x+cw]+=prob[:,:ch,:cw];weights[y:y+ch,x:x+cw]+=1
        probs/=weights[None];labels=probs.argmax(axis=0)
        for channel,identifier in COVER_IDS.items():
            if identifier not in selected: continue
            mask=(labels==channel)&(probs[channel]>=threshold)
            if mask.any(): results.append((identifier,mask,float(probs[channel][mask].mean())))
        return results

def load_engine(name, config):
    return {'grounded_sam':GroundedSAM,'building_onnx':BuildingONNX,'landcover_hybrid':LandcoverHybrid,'onnx':OnnxSemantic,'reference':lambda _:ReferenceEngine()}[name](config)
