"""Portable pixel planning. Every core pixel is assigned exactly once."""
from dataclasses import dataclass
from math import ceil

@dataclass(frozen=True)
class Tile:
    core: tuple
    read: tuple

def tiles(width, height, size=512, halo=64):
    if width < 1 or height < 1 or size < 64 or halo < 0 or 2 * halo >= size:
        raise ValueError('Geçersiz piksel veya parça boyutu.')
    for y in range(0, height, size):
        for x in range(0, width, size):
            w, h = min(size, width-x), min(size, height-y)
            left, top = max(0, x-halo), max(0, y-halo)
            right, bottom = min(width, x+w+halo), min(height, y+h+halo)
            yield Tile((x,y,w,h), (left,top,right-left,bottom-top))

def tile_count(width, height, size=512):
    return ceil(width/size) * ceil(height/size)

def validate_job(job):
    from pathlib import Path
    if job.get('schema') != 1: raise ValueError('Desteklenmeyen iş şeması.')
    if not Path(job.get('raster','')).is_file(): raise ValueError('Görüntü dosyası bulunamadı.')
    if job.get('engine') not in ('grounded_sam', 'building_onnx', 'landcover_hybrid', 'onnx', 'reference'):
        raise ValueError('Desteklenmeyen model motoru.')
    from math import isfinite
    pixels=job.get('smooth_pixels',1.5)
    if not isinstance(pixels,(int,float)) or not isfinite(pixels) or not 0<=pixels<=5: raise ValueError('Sınır sadeleştirme 0–5 piksel arasında olmalı.')
    if 'simplify' in job and (not isinstance(job['simplify'],(int,float)) or not isfinite(job['simplify']) or job['simplify']<0): raise ValueError('Geçersiz sadeleştirme toleransı.')
    classes = job.get('classes', [])
    ids = [c['id'] for c in classes]
    if not classes or len(ids)!=len(set(ids)) or any(not isinstance(i,int) or i<1 or i>254 for i in ids):
        raise ValueError('Sınıf kimlikleri benzersiz ve 1–254 arasında olmalı.')
    if not 0 < job.get('threshold',0.3) < 1: raise ValueError('Eşik 0–1 arasında olmalı.')
    if not 0 <= job.get('min_area',4) <= 1000000: raise ValueError('Geçersiz asgari alan.')
    list(tiles(1,1,job.get('tile_size',512),job.get('halo',64)))
    if not job.get('aoi') or not job.get('aoi_crs'): raise ValueError('Analiz alanı ve CRS gerekli.')
    if not job.get('rights_note','').strip(): raise ValueError('Görüntü kaynağı/kullanım izni bilgisi gerekli.')
    return job
