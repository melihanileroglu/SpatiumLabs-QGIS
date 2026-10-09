"""SpatiumLabs vector identity and timed spatial-network introduction."""
from pathlib import Path
from math import sin, cos, pi
from random import Random
from qgis.PyQt.QtCore import Qt, QRectF, QPointF, QTimer, QElapsedTimer
from qgis.PyQt.QtGui import QPainter, QIcon, QColor, QPen, QPolygonF, QFont, QLinearGradient, QRadialGradient
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QWidget
from .intro import progress, phase

LOGO = Path(__file__).parent / 'logo.svg'
def icon(): return QIcon(str(LOGO))

class Logo(QWidget):
    def __init__(self, size=64, parent=None):
        super().__init__(parent); self.setFixedSize(size,size)
        self.renderer=QSvgRenderer(str(LOGO),self)
    def paintEvent(self,event):
        painter=QPainter(self); self.renderer.render(painter,QRectF(self.rect()))

class SpatialIntro(QWidget):
    """Bounded, deterministic particles; animation uses elapsed time, not frame counts."""
    def __init__(self,module,parent=None):
        super().__init__(parent);self.module=module;self.setMinimumSize(640,390)
        rng=Random(42)  # nosec B311 - deterministic decorative points, no security use
        self.points=[(rng.uniform(-235,235),rng.uniform(-95,95),rng.uniform(0,2*pi)) for _ in range(100)]
        self.edges=[]
        for i,a in enumerate(self.points):
            neighbors=sorted(((a[0]-b[0])**2+(a[1]-b[1])**2,j) for j,b in enumerate(self.points) if j!=i)
            self.edges.extend((i,j) for d,j in neighbors[:2] if j>i and d<3600)
        self.clock=QElapsedTimer();self.clock.start()
        self.timer=QTimer(self);self.timer.setInterval(33);self.timer.timeout.connect(self.update);self.timer.start()
    def stop(self): self.timer.stop()
    def paintEvent(self,event):
        t=self.clock.elapsed()/1000;p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        background=QLinearGradient(0,0,self.width(),self.height())
        background.setColorAt(0,QColor('#030d17'));background.setColorAt(1,QColor('#0b2434'));p.fillRect(self.rect(),background)
        # Use a design coordinate system so text and footer never get clipped.
        p.translate(self.width()/2,self.height()/2);scale=min(self.width()/640,self.height()/390);p.scale(scale,scale)
        glow=QRadialGradient(QPointF(0,-40),205);glow.setColorAt(0,QColor(16,109,137,55));glow.setColorAt(1,QColor(16,109,137,0))
        p.setPen(Qt.NoPen);p.setBrush(glow);p.drawEllipse(QPointF(0,-40),240,165)
        settle=phase(t,1.4,2.7);network_alpha=1-phase(t,2.5,3.5)*.96
        positions=[QPointF(x*(1-.18*settle)+sin(seed+t*.35)*(1-settle)*2,y*.52-45) for x,y,seed in self.points]
        # Individual point arrival is staggered; connections grow towards neighbors.
        for i,pos in enumerate(positions):
            p.setOpacity(phase(t,.03+i*.004,.5+i*.004)*network_alpha)
            p.setPen(Qt.NoPen);p.setBrush(QColor('#55cfe7'));p.drawEllipse(pos,1.1+i%3*.22,1.1+i%3*.22)
        p.setPen(QPen(QColor('#2d829b'),.7));p.setBrush(Qt.NoBrush)
        for index,(i,j) in enumerate(self.edges):
            amount=phase(t,.65+(index%10)*.025,1.7+(index%10)*.025)
            p.setOpacity(amount*.7*network_alpha)
            a,b=positions[i],positions[j];p.drawLine(a,QPointF(a.x()+(b.x()-a.x())*amount,a.y()+(b.y()-a.y())*amount))
        lift=phase(t,1.65,2.85);p.setOpacity(lift)
        for index in range(3):
            y=-35-index*22*lift;w=45;h=21
            poly=QPolygonF([QPointF(0,y-h),QPointF(w,y),QPointF(0,y+h),QPointF(-w,y)])
            p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor(67,206,234,20),7));p.drawPolygon(poly)
            fill=QLinearGradient(-w,y-h,w,y+h)
            fill.setColorAt(0,QColor(['#124c67','#147d94','#246980'][index]));fill.setColorAt(1,QColor(['#092234','#28bad0','#0a3049'][index]))
            p.setPen(QPen(QColor(['#6ca9c3','#7ee9f0','#a4ddea'][index]),1.4));p.setBrush(fill);p.drawPolygon(poly)
        reveal=phase(t,2.6,3.3);p.setOpacity(reveal)
        font=QFont('Sans Serif',27,QFont.DemiBold);font.setLetterSpacing(QFont.AbsoluteSpacing,-.7);p.setFont(font)
        metrics=p.fontMetrics();left=metrics.horizontalAdvance('Spatium');right=metrics.horizontalAdvance('Labs');x=-(left+right)/2
        p.setPen(QColor('#edf5fa'));p.drawText(QPointF(x,51),'Spatium');p.setPen(QColor('#42ccdc'));p.drawText(QPointF(x+left,51),'Labs')
        p.setFont(QFont('Sans Serif',10));p.setPen(QColor('#89a9ba'));p.drawText(QRectF(-240,67,480,24),Qt.AlignCenter,'MEKÂNSAL ZEKA · ANALİZ · KEŞİF')
        p.setOpacity(phase(t,3,3.65));p.setFont(QFont('Sans Serif',10,QFont.Medium));p.setPen(QColor('#b1cad7'));p.drawText(QRectF(-200,113,400,24),Qt.AlignCenter,self.module)
        p.setOpacity(1);p.setPen(Qt.NoPen);p.setBrush(QColor('#203f51'));p.drawRoundedRect(QRectF(-105,153,210,2),1,1)
        p.setBrush(QColor('#42ccdc'));p.drawRoundedRect(QRectF(-105,153,210*progress(t),2),1,1)
        p.setPen(QColor('#6d91a5'));p.setFont(QFont('Sans Serif',8));p.drawText(QRectF(-220,165,440,22),Qt.AlignCenter,'Çalışma alanına geçiliyor')
        p.end()

class IntroDialog(QDialog):
    def __init__(self,parent,module):
        super().__init__(parent);self.setWindowTitle('SpatiumLabs | '+module);self.setWindowIcon(icon());self.setFixedSize(720,470)
        self.setStyleSheet('QDialog {background:#071a27;} QPushButton {color:#a8cbd9;background:transparent;border:1px solid #315365;border-radius:5px;padding:6px 14px;} QPushButton:hover {background:#16394a;}')
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,10);layout.setSpacing(0)
        self.animation=SpatialIntro(module,self);layout.addWidget(self.animation)
        row=QHBoxLayout();row.addStretch();skip=QPushButton('Atla →');skip.clicked.connect(self.accept);row.addWidget(skip);row.addSpacing(16);layout.addLayout(row)
        self.finish_timer=QTimer(self);self.finish_timer.setSingleShot(True);self.finish_timer.timeout.connect(self.accept);self.finish_timer.start(4800)
    def done(self,result):
        self.animation.stop();self.finish_timer.stop();super().done(result)

def welcome(parent,module):
    return IntroDialog(parent,module).exec_()==QDialog.Accepted
