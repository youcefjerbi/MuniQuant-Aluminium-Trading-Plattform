"""Render MuniQuant's original, silent, seamless 12-second aluminium sculpture film.
Optional authoring dependencies: numpy, Pillow, imageio-ffmpeg (not app dependencies).
"""
from pathlib import Path
import math
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import imageio_ffmpeg

OUT = Path(__file__).resolve().parents[1] / 'app/static/media'
OUT.mkdir(exist_ok=True)
W, H, FPS, SECONDS = 1280, 720, 24, 12
y, x = np.mgrid[0:H, 0:W]
radial = np.exp(-(((x-850)/540)**2 + ((y-330)/420)**2))
base = np.zeros((H,W,3), dtype=np.uint8)
for channel, (dark, glow) in enumerate([(4,13),(10,25),(7,16)]):
    base[:,:,channel] = dark + glow*radial
rng=np.random.default_rng(12)
noise=rng.normal(0,.65,(H,W,1))
base=np.clip(base.astype(float)+noise,0,255).astype('uint8')
background=Image.fromarray(base)
light=np.array([-.6,-.8,1.1]); light/=np.linalg.norm(light)

def rotate(points, ax, ay, az):
    cx,sx,cy,sy,cz,sz=math.cos(ax),math.sin(ax),math.cos(ay),math.sin(ay),math.cos(az),math.sin(az)
    rx=np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]])
    ry=np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]])
    rz=np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]])
    return points @ (rz @ ry @ rx).T

faces=((0,1,2,3),(4,7,6,5),(0,4,5,1),(3,2,6,7),(0,3,7,4),(1,5,6,2))
verts=np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],dtype=float)

def frame(t):
    phase=2*math.pi*t/SECONDS
    im=background.copy()
    glow=Image.new('RGB',(W,H)); g=ImageDraw.Draw(glow)
    g.ellipse((590,530,1190,650),fill=(18,54,30))
    im=Image.blend(im,glow.filter(ImageFilter.GaussianBlur(48)),.18)
    draw=ImageDraw.Draw(im)
    # Fine industrial floor grid.
    for i in range(12):
        yy=470+i*i*2.8
        draw.line([(0,yy),(W,yy)],fill=(17,34,23),width=1)
    for i in range(-7,9):
        draw.line([(810+i*25,455),(810+i*220,720)],fill=(15,31,21),width=1)
    polygons=[]
    # Machined aluminium fins form a slowly turning, open toroidal assembly.
    for i in range(78):
        angle=2*math.pi*i/78
        # Sculptural twisting rectangular fins, each with visible bevel-like edges.
        points=verts*np.array([9,53,27])
        points=rotate(points,0,angle*.5+phase,angle)
        points+=np.array([205*math.cos(angle),205*math.sin(angle),0])
        points=rotate(points,.38,phase, -.28)
        for face in faces:
            p=points[list(face)]
            normal=np.cross(p[1]-p[0],p[2]-p[0]); normal/=np.linalg.norm(normal)
            intensity=abs(float(normal @ light))
            metallic=48+intensity*158
            # Warm reflected light toward the lower right.
            warm=max(0,normal[0])*.22
            color=tuple(int(min(255,metallic*c)) for c in (.86+warm*.1,1.04,.91))
            projected=[(870+v[0]*1.12,342+v[1]*1.12) for v in p]
            polygons.append((float(p[:,2].mean()),projected,color,i))
    for depth,poly,color,i in sorted(polygons,key=lambda item:item[0]):
        draw.polygon(poly,fill=color)
        edge=tuple(min(255,c+18) for c in color)
        draw.line(poly+[poly[0]],fill=edge,width=1)
    # Orbiting telemetry points are decorative, not operational data.
    for i in range(22):
        a=2*math.pi*i/22+phase
        xx=870+315*math.cos(a); yy=342+265*math.sin(a)
        r=2 if i%4 else 3
        draw.ellipse((xx-r,yy-r,xx+r,yy+r),fill=(231,78,94) if i%4==0 else (78,139,98))
    draw.line((538,342,563,342),fill=(105,174,124),width=1)
    draw.line((550,330,550,354),fill=(105,174,124),width=1)
    return im

ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
proc=subprocess.Popen([ffmpeg,'-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'aluminium-motion.mp4')],stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
for n in range(FPS*SECONDS):
    im=frame(n/FPS)
    if n==0: im.save(OUT/'aluminium-poster.jpg',quality=90)
    proc.stdin.write(im.tobytes())
proc.stdin.close()
if proc.wait(): raise RuntimeError('Video encoding failed')
print(OUT/'aluminium-motion.mp4')
