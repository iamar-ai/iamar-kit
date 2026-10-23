# fill every texel outside the UV charts with the nearest chart texel (no dark background to bleed into at chart borders / mips)
import sys,numpy as np,trimesh
from PIL import Image,ImageDraw,ImageFilter
from scipy import ndimage
low=sys.argv[1]; maps=sys.argv[2:]
sc=trimesh.load(low)
im0=Image.open(maps[0]); W,H=im0.size
m=Image.new('L',(W,H),0); d=ImageDraw.Draw(m)
for g in sc.geometry.values():
    uv=g.visual.uv.copy(); uv[:,1]=1-uv[:,1]
    for f in g.faces: d.polygon([(uv[i,0]*W,uv[i,1]*H) for i in f],fill=255)
m=m.filter(ImageFilter.MaxFilter(5))        # keep the baked margin around each chart
cov=np.asarray(m)>0
for p in maps:
    a=np.asarray(Image.open(p).convert('RGB'))
    # texels the bake never wrote (still black) inside the charts are not data either: refill them from the nearest real texel
    # (a black normal texel decodes to (-1,-1,-1) and shows as a dark dot)
    bad=a.max(2)<20
    valid=cov&~bad
    idx=ndimage.distance_transform_edt(~valid,return_distances=False,return_indices=True)
    out=a[idx[0],idx[1]]
    Image.fromarray(out).save(p); print("filled",p,"outside charts",round(100*(~cov).mean(),1),"%, unbaked inside charts",int((cov&bad).sum()),"texels")
