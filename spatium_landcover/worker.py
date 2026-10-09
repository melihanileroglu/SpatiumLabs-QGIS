"""Isolated inference executable. QGIS never imports torch or rasterio."""
import json
import sys
from pathlib import Path

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    __package__='spatium_landcover'

from .planning import tiles, validate_job

def emit(percent, message):
    print(json.dumps({'progress':percent,'message':message},ensure_ascii=False),flush=True)

def metric_crs(aoi, source_crs):
    from pyproj import CRS, Transformer
    from shapely.ops import transform
    ll=transform(Transformer.from_crs(source_crs,4326,always_xy=True).transform,aoi).centroid
    if not -80 <= ll.y <= 84: raise ValueError('Bu sürüm UTM kapsamı dışında çalışmaz.')
    zone=max(1,min(60,int((ll.x+180)//6)+1))
    return CRS.from_epsg((32600 if ll.y>=0 else 32700)+zone)

def polygon_parts(geom):
    if geom.is_empty: return []
    if geom.geom_type=='Polygon': return [geom]
    if geom.geom_type in ('MultiPolygon','GeometryCollection'):
        return [part for g in geom.geoms for part in polygon_parts(g)]
    return []

def open_aoi(job, src):
    from pyproj import Transformer
    from shapely.geometry import shape, box
    from shapely.ops import transform
    aoi=shape(job['aoi'])
    if not aoi.is_valid or aoi.is_empty or aoi.geom_type not in ('Polygon','MultiPolygon'):
        raise ValueError('Geçerli bir analiz alanı poligonu gerekli.')
    aoi=transform(Transformer.from_crs(job['aoi_crs'],src.crs,always_xy=True).transform,aoi)
    aoi=aoi.intersection(box(*src.bounds))
    if aoi.is_empty: raise ValueError('Analiz alanı görüntüyle kesişmiyor.')
    return aoi

def run(job):
    import numpy as np
    import rasterio
    from rasterio.features import shapes, geometry_mask, geometry_window
    from rasterio.windows import Window
    from shapely.geometry import shape, mapping, box
    from shapely.ops import transform, unary_union
    from shapely import make_valid
    from pyproj import Transformer
    import fiona
    from .engines import load_engine
    validate_job(job)
    if job.get('snapshot_bounds'):
        from PIL import Image
        from rasterio.transform import from_bounds
        image=np.asarray(Image.open(job['raster']).convert('RGB'))
        if image.shape[0]<16 or image.shape[1]<16: raise ValueError('Görünen harita görüntüsü çok küçük.')
        snapshot=Path(job['raster']).with_suffix('.tif')
        with rasterio.open(snapshot,'w',driver='GTiff',width=image.shape[1],height=image.shape[0],count=3,
            dtype='uint8',crs=job['snapshot_crs'],transform=from_bounds(*job['snapshot_bounds'],image.shape[1],image.shape[0])) as dst:
            dst.write(image.transpose(2,0,1))
        job=dict(job,raster=str(snapshot))
    output=Path(job['output'])
    if output.suffix.lower()!='.gpkg': raise ValueError('Çıktı GeoPackage olmalı.')
    if output.exists(): raise ValueError('Çıktı dosyası zaten var; yeni bir ad seçin.')
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_name(output.stem+'.tmp.gpkg')
    if temporary.exists(): raise ValueError('Geçici çıktı mevcut; farklı bir ad seçin.')
    with rasterio.open(job['raster']) as src:
        if job['engine']=='reference' and not src.tags().get('SPATIUM_DATA','').startswith('SYNTHETIC ONLY'):
            raise ValueError('Referans motoru yalnızca işaretli sentetik test görüntüsünde kullanılabilir.')
        if not src.crs or src.count<3: raise ValueError('CRS tanımlı en az üç bantlı RGB görüntü gerekli.')
        if any(src.dtypes[i]!='uint8' for i in range(3)):
            raise ValueError('Bu sürüm 8 bit RGB ister. Önce görüntüyü 8 bit RGB GeoTIFF olarak hazırlayın.')
        if src.transform.b or src.transform.d or src.transform.a<=0 or src.transform.e>=0:
            raise ValueError('Görüntüyü önce kuzeye yönlü GeoTIFF olarak kaydedin.')
        aoi=open_aoi(job,src)
        extent=geometry_window(src,[mapping(aoi)])
        width,height=int(extent.width),int(extent.height)
        plan=list(tiles(width,height,job.get('tile_size',512),job.get('halo',64)))
        if len(plan)>4096 or width*height>100_000_000:
            raise ValueError('Analiz sınırı 100 milyon piksel / 4096 parçadır; alanı küçültün.')
        metric=metric_crs(aoi,src.crs)
        project=Transformer.from_crs(src.crs,metric,always_xy=True).transform
        metric_aoi=transform(project,aoi)
        if metric_aoi.area>400_000_000: raise ValueError('Tek iş en fazla 400 km² olabilir.')
        center=aoi.centroid
        from shapely.geometry import Point
        gsd=transform(project,Point(center.x,center.y)).distance(transform(project,Point(center.x+abs(src.transform.a),center.y)))
        emit(2,f'{len(plan)} parça · kaynak çözünürlük yaklaşık {gsd:.2f} m/piksel')
        engine=load_engine(job['engine'],job.get('model',{}))
        pieces={c['id']:[] for c in job['classes']}
        for i,tile in enumerate(plan):
            x,y,w,h=tile.read;cx,cy,cw,ch=tile.core
            window=Window(extent.col_off+x,extent.row_off+y,w,h)
            data=src.read([1,2,3],window=window)
            valid=src.read_masks([1,2,3],window=window).min(axis=0)>0
            affine=src.window_transform(window)
            valid &= geometry_mask([mapping(aoi)],out_shape=(h,w),transform=affine,invert=True)
            if valid.any():
                rgb=data.transpose(1,2,0);rgb[~valid]=0
                # Core ownership prevents duplicate coverage; halo provides model context.
                core=np.zeros((h,w),dtype=bool);core[cy-y:cy-y+ch,cx-x:cx-x+cw]=True
                for identifier,mask,score in engine.predict(rgb,job['classes'],job.get('threshold',0.3)):
                    if identifier not in pieces or mask.shape!=(h,w): raise ValueError('Model maskesi/sınıfı iş sözleşmesiyle uyuşmuyor.')
                    if not np.isfinite(score) or not 0<=score<=1: raise ValueError('Model skoru 0–1 arasında sonlu bir sayı olmalı.')
                    mask=mask.astype(bool)&valid&core
                    for geom,value in shapes(mask.astype('uint8'),mask=mask,transform=affine):
                        if value!=1: continue
                        projected=transform(project,shape(geom))
                        pieces[identifier].append((projected,float(score)))
            emit(5+80*(i+1)/len(plan),f'Parça {i+1}/{len(plan)} işlendi')
        # Priority is user-selected class order. No area belongs to two classes.
        accepted=shape({'type':'GeometryCollection','geometries':[]})
        features=[]
        for cls in job['classes']:
            candidates=pieces[cls['id']]
            from shapely.strtree import STRtree
            index=STRtree([g for g,s in candidates])
            class_parts=[]
            merged=make_valid(unary_union([g for g,s in candidates])).intersection(metric_aoi).difference(accepted)
            for geom in polygon_parts(merged):
                if geom.area<job.get('min_area',4): continue
                for part in polygon_parts(make_valid(geom).intersection(metric_aoi).difference(accepted)):
                    if part.area<job.get('min_area',4): continue
                    scores=[candidates[int(i)][1] for i in index.query(part,predicate='intersects')]
                    features.append({'geometry':mapping(part),'properties':{
                        'object_id':len(features)+1,'class_id':cls['id'],'class_name':cls['name'],
                        'score_max':max(scores,default=0),'area_m2':part.area,
                        'review':'unreviewed','source_gsd':gsd,'engine':job['engine']}})
                    class_parts.append(part)
            accepted=unary_union([accepted,*class_parts])
        from .geometry import generalize,tolerance_for
        features,generalization=generalize(features,metric_aoi,tolerance_for(job,gsd),job.get('min_area',4))
        emit(90,'Poligon sınırları sadeleştiriliyor ve kaydediliyor')
        schema={'geometry':'Polygon','properties':{'object_id':'int','class_id':'int','class_name':'str',
            'score_max':'float','area_m2':'float','review':'str','source_gsd':'float','engine':'str'}}
        try:
            with fiona.open(temporary,'w',driver='GPKG',layer='objects',crs_wkt=metric.to_wkt(),schema=schema) as dst:
                dst.writerecords(features)
            import sqlite3
            from datetime import datetime,timezone
            report={'schema':1,'created_utc':datetime.now(timezone.utc).isoformat(),'job':job,
                'tile_count':len(plan),'source_gsd_m':gsd,'feature_count':len(features),
                'generalization':generalization,'output_crs':metric.to_string(),'score_definition':'Maximum detector/model score, not calibrated accuracy',
                'limitations':['Candidates require review','Touching same-class areas merge','RGB fields do not establish agricultural land use']}
            report['model_revisions']={name:getattr(getattr(engine,name,None),'config',None)._commit_hash
                for name in ('dm','sm') if getattr(getattr(engine,name,None),'config',None) is not None}
            if job['engine']=='landcover_hybrid':
                report['model_revisions'].update(cover=job['model']['cover_revision'],buildings=job['model']['building_model']['revision'])
            with sqlite3.connect(temporary) as db:
                db.execute('CREATE TABLE spatium_run (metadata_json TEXT NOT NULL)')
                db.execute('INSERT INTO spatium_run VALUES (?)',(json.dumps(report,ensure_ascii=False),))
            temporary.rename(output)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    emit(100,f'{len(features)} aday poligon kaydedildi')
    return report

def export_training(job):
    """Only explicitly reviewed polygons are labels; all other pixels are ignored."""
    import numpy as np
    import rasterio
    from rasterio.features import rasterize, geometry_window
    from rasterio.windows import Window
    from shapely.geometry import shape,mapping
    from shapely.ops import transform
    from pyproj import Transformer
    output=Path(job['dataset'])
    if output.exists(): raise ValueError('Eğitim klasörü mevcut; yeni bir ad seçin.')
    annotations=json.loads(Path(job['annotations']).read_text())
    reviewed=[f for f in annotations['features'] if f['properties'].get('review')=='accepted']
    if not reviewed: raise ValueError('Önce eğitim poligonlarının review alanını accepted olarak işaretleyin.')
    with rasterio.open(job['raster']) as src:
        aoi=open_aoi(job,src)
        project=Transformer.from_crs(job['annotation_crs'],src.crs,always_xy=True).transform
        records=[]
        allowed={0}|{c['id'] for c in job['classes']}
        for f in reviewed:
            identifier=int(f['properties']['class_id'])
            if identifier not in allowed: raise ValueError('Eğitim sınıf kimliği bilinmiyor.')
            geom=transform(project,shape(f['geometry']))
            if not geom.is_valid: raise ValueError('Eğitim poligonları geçerli olmalı.')
            if any(geom.intersection(other).area>1e-8 for other,_ in records):
                raise ValueError('Eğitim poligonları çakışıyor; önce çakışmaları giderin.')
            records.append((geom,identifier))
        window=geometry_window(src,[mapping(aoi)])
        plan=list(tiles(int(window.width),int(window.height),256,0))
        if len(plan)>4096: raise ValueError('Eğitim alanı çok büyük.')
        # Split entire columns into spatial blocks, not random adjacent pixels.
        columns=sorted({t.core[0] for t in plan})
        if len(columns)<3: raise ValueError('Bağımsız train/validation/test için en az üç 256 piksel sütunu gerekli.')
        output.mkdir(parents=True)
        manifest=[]
        try:
            for i,tile in enumerate(plan):
                x,y,w,h=tile.core;win=Window(window.col_off+x,window.row_off+y,w,h)
                affine=src.window_transform(win)
                label=rasterize([(mapping(g),c) for g,c in records],out_shape=(h,w),transform=affine,fill=255,dtype='uint8')
                valid=src.read_masks([1,2,3],window=win).min(axis=0)>0
                valid &= geometry_mask_local(aoi,h,w,affine)
                label[~valid]=255
                if not np.any(label!=255): continue
                column=columns.index(x)
                split='test' if column==len(columns)-1 else 'validation' if column==len(columns)-2 else 'train'
                folder=output/split;folder.mkdir(exist_ok=True)
                image=folder/f'{i:04}_rgb.tif';mask=folder/f'{i:04}_labels.tif'
                profile=src.profile.copy();profile.update(driver='GTiff',width=w,height=h,count=3,transform=affine)
                with rasterio.open(image,'w',**profile) as dst: dst.write(src.read([1,2,3],window=win))
                profile.update(count=1,dtype='uint8',nodata=255)
                with rasterio.open(mask,'w',**profile) as dst: dst.write(label,1)
                manifest.append({'image':str(image.relative_to(output)),'mask':str(mask.relative_to(output)),
                                 'split':split,'window':[int(win.col_off),int(win.row_off),w,h]})
                emit(100*(i+1)/len(plan),f'Eğitim parçası {i+1}/{len(plan)}')
            if {r['split'] for r in manifest}!={'train','validation','test'}:
                raise ValueError('Her mekânsal blokta onaylı etiket bulunmalı; alanın farklı kısımlarını etiketleyin.')
            result={'schema':1,'ignore_id':255,'background_id':0,'classes':job['classes'],
                    'source':job['raster'],'rights_note':job['rights_note'],'tiles':manifest,
                    'split':'disjoint spatial columns; external-location validation also recommended'}
            (output/'dataset.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
            return result
        except BaseException:
            import shutil
            shutil.rmtree(output)
            raise

def geometry_mask_local(aoi,h,w,affine):
    from rasterio.features import geometry_mask
    from shapely.geometry import mapping
    return geometry_mask([mapping(aoi)],out_shape=(h,w),transform=affine,invert=True)

if __name__=='__main__':
    try:
        job=json.loads(Path(sys.argv[1]).read_text())
        if job.get('operation')=='acquire':
            from .imagery import acquire
            acquire(job,emit)
        elif job.get('operation')=='export_training': export_training(job)
        else: run(job)
    except Exception as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False),flush=True)
        sys.exit(1)
