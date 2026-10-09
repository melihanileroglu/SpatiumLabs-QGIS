"""Schematic network illustrations and legends, independent of Qt/QGIS."""
from html import escape
from .graph import parse_distances

ORIGIN='#148d7c'
TARGET='#dc2626'
ROUTE='#2563eb'

def legend(mode, colors, thresholds):
    if mode == 0:
        try: values=parse_distances(thresholds)
        except ValueError: values=[400,800,1200]
        low=0;items=[]
        for i,value in enumerate(values):
            color=colors[0 if len(values)==1 else round(i*2/(len(values)-1))]
            items.append((color,'%g–%g m'%(low,value)));low=value
        return items+[(ORIGIN,'Başlangıç noktası')]
    if mode == 1: return [(ORIGIN,'Başlangıç'),(TARGET,'Hedef'),(ROUTE,'En kısa rota')]
    if mode == 2: return [(ORIGIN,'Başlangıç'),(TARGET,'Tesisler'),(ROUTE,'Seçilen tesisin rotası'),('#94a3b8','Diğer yol bağlantıları')]
    return [(ORIGIN,'Başlangıçlar'),(TARGET,'Hedefler'),(ROUTE,'Ağ mesafesi hücreleri')]

def legend_html(mode,colors,thresholds):
    return '<br>'.join('<span style="color:%s">■</span> %s'%(escape(c,quote=True),escape(t)) for c,t in legend(mode,colors,thresholds))

def svg(mode,colors,thresholds):
    pieces=['<svg xmlns="http://www.w3.org/2000/svg" width="260" height="174" viewBox="0 0 260 174">',
            '<rect width="260" height="174" rx="10" fill="#f3f6fa"/>']
    def path(d,color,width=2,opacity=1):pieces.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round" opacity="%s"/>'%(d,color,width,opacity))
    def point(x,y,color,name):
        pieces.append('<circle cx="%s" cy="%s" r="5" fill="%s" stroke="white" stroke-width="2"/>'%(x,y,color))
        pieces.append('<text x="%s" y="%s" font-family="Arial" font-size="10" fill="#334155">%s</text>'%(x+8,y-6,escape(name)))
    if mode < 3:
        for d in ['M12 30 L82 30 L112 52 L246 52','M12 82 L66 82 L112 110 L245 110',
                  'M26 154 L84 154 L144 138 L248 138','M42 12 L42 154','M84 12 L84 154',
                  'M144 12 L144 154','M204 12 L204 154']:
            path(d,'#d8e0ea',4)
    if mode == 0:
        outlines=['M30 65 L52 28 L106 22 L129 36 L190 28 L224 62 L216 99 L231 132 L192 153 L158 146 L114 157 L79 143 L39 147 L26 105 Z',
                  'M59 66 L81 46 L116 49 L142 40 L181 56 L184 81 L202 106 L178 126 L143 119 L112 133 L76 114 L50 95 Z',
                  'M89 71 L112 61 L135 65 L154 60 L165 78 L157 99 L136 105 L115 117 L98 101 L82 90 Z']
        bands=legend(0,colors,thresholds)[:-1]
        # Two/one-threshold examples show exactly the colors used by the output.
        chosen=[outlines[0]] if len(bands)==1 else ([outlines[0],outlines[2]] if len(bands)==2 else outlines)
        for d,(color,_) in zip(chosen,reversed(bands[-len(chosen):])):
            pieces.append('<path d="%s" fill="%s" fill-opacity="0.72" stroke="white" stroke-width="1.5"/>'%(d,color))
        path('M84 82 L112 110 L144 110 L144 52','#475569',2,.55)
        point(112,110,ORIGIN,'S')
    elif mode == 1:
        path('M42 30 L84 30 L112 52 L204 52 L204 138',ROUTE,5)
        point(42,30,ORIGIN,'A');point(204,138,TARGET,'B')
    elif mode == 2:
        path('M84 82 L84 30 L144 30',ROUTE,5)
        point(84,82,ORIGIN,'A')
        for x,y,name in [(144,30,'F1'),(204,110,'F2'),(42,154,'F3')]:point(x,y,TARGET,name)
    else:
        for i,name in enumerate(['T1','T2','T3']):
            pieces.append('<text x="%s" y="27" font-family="Arial" font-size="11" fill="%s">%s</text>'%(85+i*54,TARGET,name))
        for row in range(3):
            pieces.append('<text x="16" y="%s" font-family="Arial" font-size="11" fill="%s">O%s</text>'%(57+row*43,ORIGIN,row+1))
            for col in range(3):
                distance=[[240,560,810],[420,190,650],[710,380,220]][row][col]
                color=['#dbeafe','#93c5fd','#2563eb'][min(2,distance//300)]
                pieces.append('<rect x="%s" y="%s" width="49" height="36" rx="4" fill="%s"/>'%(65+col*54,35+row*43,color))
                pieces.append('<text x="%s" y="%s" font-family="Arial" font-size="11" fill="%s">%s m</text>'%(69+col*54,57+row*43,'white' if color=='#2563eb' else '#1e3a8a',distance))
    pieces.append('</svg>')
    return ''.join(pieces)
