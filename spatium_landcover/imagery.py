"""Licensed XYZ provider adapter, explicitly advertised native zoom only."""
import math
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request,urlopen
from io import BytesIO

HALF_WORLD=20037508.342789244

def validate_provider(provider):
    url=provider.get('url','')
    parsed=urlparse(url)
    if parsed.scheme!='https' or not all(token in url for token in ('{z}','{x}','{y}')):
        raise ValueError('HTTPS XYZ adresi {z}, {x}, {y} alanlarını içermeli.')
    host=(parsed.hostname or '').lower()
    if host.endswith(('google.com','googleapis.com','google.cn','gstatic.com')):
        raise ValueError('Bu adaptör Google Earth/Maps karo toplamayı desteklemez. İndirme izni olan ayrı bir görüntü sağlayıcısı kullanın.')
    if provider.get('bulk_analysis_allowed') is not True or not provider.get('license_note','').strip():
        raise ValueError('Sağlayıcı profili toplu indirme/analiz izni ve lisans açıklamasını içermeli.')
    zoom=provider.get('native_zoom')
    if not isinstance(zoom,int) or not 0<=zoom<=22: raise ValueError('Sağlayıcının native_zoom değeri 0–22 arasında olmalı.')
    return provider

def xyz_range(bounds,zoom):
    west,south,east,north=bounds
    if not(-180<=west<east<=180 and -85<=south<north<=85): raise ValueError('XYZ için geçerli coğrafi alan gerekli; tarih çizgisi geçilemez.')
    n=2**zoom
    def x(lon): return (lon+180)/360*n
    def y(lat): return (1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n
    return (max(0,math.floor(x(west))),max(0,math.floor(y(north))),
            min(n-1,math.ceil(x(east))-1),min(n-1,math.ceil(y(south))-1))

def acquire(job,emit):
    import numpy as np
    import rasterio
    from rasterio.windows import Window
    from rasterio.transform import from_origin
    from PIL import Image
    from pyproj import Transformer
    from shapely.geometry import shape,box
    from shapely.ops import transform
    import time
    provider=validate_provider(job['provider']);zoom=provider['native_zoom']
    aoi=shape(job['aoi'])
    if not aoi.is_valid or aoi.is_empty: raise ValueError('Geçerli analiz alanı gerekli.')
    geographic=transform(Transformer.from_crs(job['aoi_crs'],4326,always_xy=True).transform,aoi)
    left,top,right,bottom=xyz_range(geographic.bounds,zoom)
    count=(right-left+1)*(bottom-top+1)
    limit=min(1024,int(provider.get('max_tiles',256)))
    if count>limit: raise ValueError(f'Alan {count} görüntü parçası gerektiriyor; sınır {limit}. Alanı küçültün.')
    output=Path(job['output'])
    if output.exists(): raise ValueError('Görüntü çıktısı mevcut; yeni bir ad seçin.')
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.tmp.tif')
    if temporary.exists(): raise ValueError('Geçici görüntü mevcut; yeni çıktı adı seçin.')
    scale=2*HALF_WORLD/(2**zoom*256)
    affine=from_origin(-HALF_WORLD+left*256*scale,HALF_WORLD-top*256*scale,scale,scale)
    metric_aoi=transform(Transformer.from_crs(job['aoi_crs'],3857,always_xy=True).transform,aoi)
    try:
        with rasterio.open(temporary,'w',driver='GTiff',width=(right-left+1)*256,height=(bottom-top+1)*256,
            count=4,dtype='uint8',crs='EPSG:3857',transform=affine,compress='deflate',photometric='RGB') as dst:
            from rasterio.enums import ColorInterp
            dst.colorinterp=(ColorInterp.red,ColorInterp.green,ColorInterp.blue,ColorInterp.alpha)
            done=0
            for y in range(top,bottom+1):
                for x in range(left,right+1):
                    tile_bounds=box(-HALF_WORLD+x*256*scale,HALF_WORLD-(y+1)*256*scale,
                                    -HALF_WORLD+(x+1)*256*scale,HALF_WORLD-y*256*scale)
                    if tile_bounds.intersects(metric_aoi):
                        url=provider['url'].format(z=zoom,x=x,y=y)
                        request=Request(url,headers={'User-Agent':'SpatiumLabs-Earth/0.1'})
                        # Sequential requests, bounded payload, no hidden retries.
                        with urlopen(request,timeout=30) as response: payload=response.read(8_000_001)
                        if len(payload)>8_000_000: raise ValueError('Görüntü parçası boyut sınırını aştı.')
                        image=Image.open(BytesIO(payload))
                        if image.size!=(256,256): raise ValueError('Sağlayıcı 256 × 256 XYZ görüntü vermeli.')
                        arr=np.asarray(image.convert('RGBA')).transpose(2,0,1)
                        dst.write(arr,window=Window((x-left)*256,(y-top)*256,256,256))
                        time.sleep(.1)
                    done+=1;emit(100*done/count,f'Görüntü {done}/{count} · özgün zoom {zoom}')
            dst.update_tags(SPATIUM_PROVIDER=provider.get('name','XYZ'),LICENSE=provider['license_note'],
                            NATIVE_ZOOM=str(zoom),NOTE='Provider-advertised native zoom; not independently verified optical resolution')
        temporary.rename(output)
    except BaseException:
        temporary.unlink(missing_ok=True);raise
    return output
