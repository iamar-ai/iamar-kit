# lift the baked sky occlusion around the face (head + the hair beside it + the neck, BOTH surfaces), then rebuild the albedo.
# The region is a smooth box feathered wide: selecting triangles by centre point left the side-of-face triangles (which curve
# back) unlifted, and the angular lit/unlit patches on both cheeks were the edge of that selection.
import sys,os,numpy as np,trimesh
from PIL import Image,ImageDraw,ImageFilter
low,ao_png,alb_png,lift=sys.argv[1],sys.argv[2],sys.argv[3],float(sys.argv[4])
X0,X1=float(os.environ.get('RX0','-0.07')),float(os.environ.get('RX1','0.19'))
Y0,Y1=float(os.environ.get('RY0','0.45')),float(os.environ.get('RY1','0.80'))
Z0,Z1=float(os.environ.get('RZ0','-0.14')),float(os.environ.get('RZ1','0.22'))
sc=trimesh.load(low)
ao=np.asarray(Image.open(ao_png).convert('RGB'),np.float64)[...,0]/255.0
H,W=ao.shape
m=Image.new('L',(W,H),0); d=ImageDraw.Draw(m); n=0
for g in sc.geometry.values():
    uv=g.visual.uv.copy(); uv[:,1]=1-uv[:,1]
    C=g.triangles_center
    sel=(C[:,0]>X0)&(C[:,0]<X1)&(C[:,1]>Y0)&(C[:,1]<Y1)&(C[:,2]>Z0)&(C[:,2]<Z1)
    n+=int(sel.sum())
    for f in g.faces[sel]: d.polygon([(uv[i,0]*W,uv[i,1]*H) for i in f],fill=255)
print("lifted triangles",n)
m=m.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(float(os.environ.get('FEATHER','40'))))
mk=np.asarray(m,np.float64)/255.0
o=ao*(1-lift*mk)+1.0*(lift*mk)
o=np.clip(o,0,1)**1.3
base=np.array([0.86,0.82,0.74])
col=np.dstack([o*base[0],o*base[1],o*base[2]])
lum=(col*np.array([0.3,0.59,0.11])).sum(2,keepdims=True)
k=np.clip((1-o)*float(os.environ.get('DESAT','0.65')),0,1)[...,None]
col=col*(1-k)+np.repeat(lum,3,2)*k
Image.fromarray((np.clip(col,0,1)*255).astype(np.uint8),'RGB').save(alb_png)
print("albedo rewritten, lift",lift)
