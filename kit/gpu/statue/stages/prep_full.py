import bpy,bmesh,sys,os,math
src,out=sys.argv[-2:]
E=os.environ.get
CX,CZ,RX,RZ=float(E('FCX','0.03')),float(E('FCZ','0.64')),float(E('FRX','0.065')),float(E('FRZ','0.085'))
RXL,RXR=float(E('FRXL',str(RX))),float(E('FRXR',str(RX))); YF=float(E('FYF','0.0')); CY=float(E('FCY','0.0')); YAW=math.radians(float(E('FYAW','0'))); LOOSE=float(E('LOOSE','0.003'))   # (the face oval may be wider on one side: FRXL / FRXR, viewer's right = +x)
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=src)
o=[x for x in bpy.context.scene.objects if x.type=='MESH'][0]
bpy.context.view_layer.objects.active=o; o.select_set(True)
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM'); bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
bm=bmesh.new(); bm.from_mesh(o.data); n0=len(bm.faces)
MAGE=E('MAGE_CLEAN','0')=='1'
def whip(c): return MAGE and c.z < -0.085 and c.x > max(0.285, 0.25 + (-c.z - 0.085) * 0.4)
dead=[f for f in bm.faces if f.calc_center_median().z < float(E('FZCUT','-1.2')) or whip(f.calc_center_median())]
# rock lump behind the boots (Blender frame: x 0.0..0.11, y -0.17..-0.07, lowest 0.1 of the figure)
ZB=min(v.co.z for v in bm.verts)
SOLE=float(E('SOLE','0.028')); ROCK=float(E('ROCKH','0.10'))
def rock(c):
    low = c.z < ZB + ROCK
    small = 0.0 < c.x < 0.11 and -0.17 < c.y < -0.07 and low
    # the cloak's hem pooled on the ground behind the right foot (the viewer's left): a big smooth hollow bulge, 0.2 x 0.3, that reads
    # as a rock. Blender frame, y = -z of the glb. Kept: the staff column (x -0.255..-0.165, y -0.045..0.03) and the boot (x > -0.075).
    staff = -0.255 < c.x < -0.165 and -0.045 < c.y < 0.03
    dome = -0.30 < c.x < -0.075 and -0.045 < c.y < 0.40 and ZB + 0.012 < c.z < ZB + float(E('DOMEH','0.30')) and not staff
    return MAGE and (small or dome)
# per-statue boxes to remove, absolute Blender coordinates: BOXES='x0,x1,y0,y1,z0,z1;...'
BOX=[tuple(float(v) for v in b.split(',')) for b in E('BOXES','').split(';') if b.strip()]
def inbox(c): return any(b[0]<c.x<b[1] and b[2]<c.y<b[3] and b[4]<c.z<b[5] for b in BOX)
dead=list(dead)+[f for f in bm.faces if f.calc_center_median().z<ZB+SOLE or rock(f.calc_center_median()) or inbox(f.calc_center_median())]
bmesh.ops.delete(bm,geom=dead,context='FACES')
bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
cap=[e for e in bm.edges if e.is_boundary and all(v.co.z<ZB+SOLE+0.06+(float(E('DOMEH','0.30')) if MAGE else float(E('CAPH','0.0'))) for v in e.verts)]
bmesh.ops.holes_fill(bm,edges=cap,sides=0)       # close the soles
# drop small loose bits
bm.faces.ensure_lookup_table(); seen=set(); comps=[]
for f in bm.faces:
    if f.index in seen: continue
    st=[f]; seen.add(f.index); comp=[]
    while st:
        g=st.pop(); comp.append(g)
        for e in g.edges:
            for h in e.link_faces:
                if h.index not in seen: seen.add(h.index); st.append(h)
    comps.append(comp)
big=max(len(c) for c in comps)
bmesh.ops.delete(bm,geom=[f for c in comps if len(c)<LOOSE*big for f in c],context='FACES')
mh=bpy.data.materials.new('head'); mh.use_nodes=True; mh.diffuse_color=(0.4,0.6,1,1)
mb=bpy.data.materials.new('body'); mb.use_nodes=True; mb.diffuse_color=(0.8,0.78,0.7,1)
o.data.materials.clear(); o.data.materials.append(mb); o.data.materials.append(mh)
nh=0
for f in bm.faces:
    c=f.calc_center_median()
    dx,dy=c.x-CX,c.y-CY; lx=dx*math.cos(YAW)-dy*math.sin(YAW); ly=dx*math.sin(YAW)+dy*math.cos(YAW)   # rotate into the face's frame
    if ly<YF and (((lx)/(RXR if lx>0 else RXL))**2+((c.z-CZ)/RZ)**2)<1: f.material_index=1; nh+=1
    else: f.material_index=0
print("PREP removed",n0-len(bm.faces),"faces; head-material faces",nh,"of",len(bm.faces))
bm.to_mesh(o.data); bm.free()
for p in o.data.polygons: p.use_smooth=True
bpy.ops.export_scene.gltf(filepath=out,export_format='GLB',export_materials='EXPORT',export_image_format='NONE')
