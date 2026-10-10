"""Pinned Blender 5.1 scene SDK. Imported inside Blender, never by the web worker."""
import math
import random
import bpy
from mathutils import Vector

VERSION='0.1.0'
PALETTE={'navy':(.012,.025,.065,1),'blue':(.045,.21,.62,1),'cyan':(.12,.72,.85,1),
         'white':(.78,.85,.91,1),'warm':(.95,.48,.09,1),'dark':(.018,.027,.045,1),
         'green':(.11,.43,.2,1),'red':(.72,.12,.055,1)}

def material(name, color, metallic=0, roughness=.42, emission=0):
    if name in bpy.data.materials:return bpy.data.materials[name]
    mat=bpy.data.materials.new(name);mat.diffuse_color=color;mat.use_nodes=True
    bs=mat.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=color
    bs.inputs['Metallic'].default_value=metallic
    bs.inputs['Roughness'].default_value=roughness
    if emission:
        bs.inputs['Emission Color'].default_value=color;bs.inputs['Emission Strength'].default_value=emission
    return mat

def box(name, location, scale, color='blue', bevel=.04, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location)
    obj=bpy.context.object;obj.name=name;obj.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.data.materials.append(material(color,PALETTE.get(color,PALETTE['blue'])))
    if bevel:
        mod=obj.modifiers.new('Soft edges','BEVEL');mod.width=bevel;mod.segments=2
        obj.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    if parent:obj.parent=parent
    return obj

def sphere(name,location,radius,color,parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,radius=radius,location=location)
    obj=bpy.context.object;obj.name=name
    obj.data.materials.append(material(color,PALETTE[color]));obj.parent=parent
    for polygon in obj.data.polygons:polygon.use_smooth=True
    return obj

def empty(name,location=(0,0,0),parent=None):
    obj=bpy.data.objects.new(name,None);bpy.context.scene.collection.objects.link(obj)
    obj.location=location;obj.parent=parent;return obj

def label(name,text,location,size=.4,color='white',rotation=(math.pi/2,0,0)):
    data=bpy.data.curves.new(name,'FONT');data.body=text;data.align_x='CENTER';data.size=size;data.extrude=.004
    obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj)
    obj.location=location;obj.rotation_euler=rotation;obj.data.materials.append(material(color,PALETTE[color]))
    return obj

def key(obj,path,values,ctx,index=None,linear=False):
    for ms,value in values:
        if index is None:setattr(obj,path,value)
        else:getattr(obj,path)[index]=value
        frame=1+(ms-ctx['shot']['start_ms'])*ctx['fps']/1000
        obj.keyframe_insert(data_path=path,index=-1 if index is None else index,frame=frame)
    action=obj.animation_data.action if obj.animation_data else None
    if action:
        for layer in action.layers:
            for strip in layer.strips:
                bag=strip.channelbag(obj.animation_data.action_slot)
                if bag:
                    for curve in bag.fcurves:
                        for point in curve.keyframe_points:
                            point.interpolation='LINEAR' if linear else 'BEZIER'
                            point.handle_left_type=point.handle_right_type='AUTO_CLAMPED'

def camera(ctx,positions,target,ortho=None,lens=45):
    bpy.ops.object.camera_add(location=positions)
    cam=bpy.context.object;cam.name='Camera'
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.lens=lens
    if ortho:cam.data.type='ORTHO';cam.data.ortho_scale=ortho
    bpy.context.scene.camera=cam
    return cam

def studio(ctx):
    scene=bpy.context.scene
    scene.world=bpy.data.worlds.new('World');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.006,.015,.04,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.35
    for name,position,energy,color,size in [('Key',(3,-4,9),1600,(.78,.87,1),7),('Cyan rim',(-5,4,7),1800,(.2,.7,1),6),('Warm edge',(5,6,4),900,(1,.54,.23),5)]:
        bpy.ops.object.light_add(type='AREA',location=position)
        lamp=bpy.context.object;lamp.name=name;lamp.data.energy=energy;lamp.data.color=color;lamp.data.shape='DISK';lamp.data.size=size
        lamp.rotation_euler=(Vector((0,0,0))-lamp.location).to_track_quat('-Z','Y').to_euler()
    scene.view_settings.view_transform='AgX'
    box('Stage',(0,0,-.16),(22,32,.3),'navy',.1)

def market(ctx,spec):
    """A persistent market reconstruction, evaluated on the project's global clock."""
    studio(ctx);random.seed(ctx['seed'])
    for x in (-.56,.56):box('Rail',(x,0,.055),(.08,27,.11),'white',.02)
    for y in range(-13,14):box('Sleeper',(0,y,-.012),(1.65,.17,.09),'dark',.01)
    train=empty('train')
    for carriage in range(3):
        group=empty('carriage_'+str(carriage),(0,-carriage*3.9,0),train)
        box('Train body',(0,0,1.28),(1.46,3.5,1.42),'white',.12,group)
        box('Train lower band',(0,0,.85),(1.50,3.53,.35),'blue',.06,group)
        box('Train roof',(0,0,2.03),(1.52,3.6,.20),'blue',.10,group)
        for side in (-1,1):
            for y in (-1.12,0,1.12):box('Window',(side*.741,y,1.5),(.024,.78,.46),'dark',.04,group)
            for y in (-1.05,1.05):
                pivot=empty('wheel',(side*.65,y,.40),group)
                bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=.35,depth=.16,location=(0,0,0),rotation=(0,math.pi/2,0))
                wheel=bpy.context.object;wheel.parent=pivot;wheel.data.materials.append(material('wheel metal',PALETTE['dark'],.65,.25))
                for angle in (0,math.pi/2):
                    spoke=box('Wheel spoke',(0,0,0),(.18,.53,.045),'white',.01,pivot);spoke.rotation_euler.x=angle
                key(pivot,'rotation_euler',[(0,0),(30000,-70)],ctx,index=0,linear=True)
    for x in (-.43,.43):sphere('Headlamp',(x,1.78,1.16),.09,'warm',train)
    key(train,'location',[(0,-4),(1800,-2),(3800,4),(5200,8),(5300,-15),(11500,-13),(15600,-8),(17400,-5),(19200,-2),(23100,8),(25500,17),(30000,26)],ctx,index=1,linear=True)
    for side in (-1,1):
        for j,y in enumerate((-4,0,4)):
            x=side*2.6
            box('Counter',(x,y,.62),(1.2,2.6,1.1),'blue',.05)
            for dy in (-1.2,1.2):box('Canopy post',(side*3.04,y+dy,1.5),(.075,.075,3),'cyan',.02)
            hinge=empty('canopy_'+str(side)+'_'+str(j),(side*3.0,y,2.83))
            for stripe in range(8):
                box('Canopy stripe',(-side*.95,-1.25+stripe*.34,0),(1.96,.33,.065),'white' if stripe%2 else 'cyan',.015,hinge)
            key(hinge,'rotation_euler',[(0,side*1.45),(5200,side*1.45),(5300,0),(17400,0),(19000,side*1.45),(24800,side*1.45),(26600,0),(30000,0)],ctx,index=1)
            for tray in range(3):
                tx=side*1.3;ty=y-1+tray*.8
                box('Produce tray',(tx,ty,.23),(.53,.62,.18),'warm',.02)
                for k in range(5):
                    sphere('Vegetable',(tx+random.uniform(-.17,.17),ty+random.uniform(-.21,.21),.40),.105,'green' if tray%2 else 'red')
            vendor=empty('Vendor',(side*3.58,y,0))
            box('Vendor body',(0,0,1.15),(.42,.38,.68),'warm',.09,vendor)
            sphere('Vendor head',(0,0,1.64),.21,'white',vendor)
            box('Vendor hat',(0,0,1.83),(.61,.55,.08),'cyan',.04,vendor)
    mode=spec['camera']
    portrait=ctx['orientation']=='portrait'
    if mode=='detail':
        cam=camera(ctx,(1.65,1.05,.85),(.6,1.05,.38),ortho=2.3)
        # Keep the chosen wheel near the camera during the explanatory close-up.
        cam.parent=train;cam.location=(1.65,1.05,.85)
    elif mode=='low':cam=camera(ctx,(5,-7,3.4),(0,-1,1.0),ortho=9 if portrait else 12)
    elif mode=='location':
        cam=camera(ctx,(9,-11,14),(0,0,0),ortho=17 if portrait else 21)
        title=label('Location','THAILAND\nMAEKLONG MARKET',(0,0,0),.62,'cyan',(0,0,0))
        title.parent=cam;title.location=(0,4.4,-10)
        title.data.materials.clear();title.data.materials.append(material('Location luminous',PALETTE['cyan'],emission=1.3))
        box('Location backplate',(0,4.3,-10.1),(8,1.65,.035),'dark',.06,cam)
    elif mode=='wide':cam=camera(ctx,(8,-12,13),(0,-1,.8),ortho=17 if portrait else 20)
    elif mode=='hero':cam=camera(ctx,(7,-9,7),(0,0,.9),ortho=12 if portrait else 17)
    else:cam=camera(ctx,(7,-9,7),(0,-1,1),ortho=12 if portrait else 16)
    start=spec['start_ms'];end=spec['end_ms']
    if mode not in ('detail','location'):
        pos=tuple(cam.location)
        key(cam,'location',[(start,pos),(end,(pos[0]*.97,pos[1]*.97,pos[2]*.97))],ctx)
    return {'objects':len(bpy.context.scene.objects),'action':'train travel / canopy hinge / wheel rotation','schematic':True}

def finance(ctx,spec):
    studio(ctx);series=spec['params']['series'];maximum=max(float(i['value']) for i in series)
    count=len(series);start=spec['start_ms'];end=spec['end_ms']
    for i,datum in enumerate(series):
        x=(i-(count-1)/2)*1.65;h=1+4*float(datum['value'])/max(1,maximum)
        bar=box('bar_'+str(i),(x,0,h/2),(1.1,1,h),'cyan' if i%2 else 'blue',.08)
        key(bar,'scale',[(start,.03),(min(end,start+1300+i*180),1)],ctx,index=2)
        key(bar,'location',[(start,.03*h/2),(min(end,start+1300+i*180),h/2)],ctx,index=2)
        label('Value',str(datum['value']),(x,-.7,h+.35),.4,'warm')
        label('Label',str(datum['label']),(x,-.7,-.02),.25)
    camera(ctx,(8,-15,10),(0,0,2),ortho=12 if ctx['orientation']=='portrait' else 14)
    return {'objects':len(bpy.context.scene.objects),'action':'source-backed bar growth'}

def process(ctx,spec):
    studio(ctx);steps=spec['params'].get('steps',[])
    if not 2<=len(steps)<=6:raise ValueError('Process builder requires 2–6 steps')
    start=spec['start_ms'];end=spec['end_ms']
    for i,text in enumerate(steps):
        y=(i-(len(steps)-1)/2)*2.1
        obj=box('Step_'+str(i),(0,y,.55),(2.8,1.4,1.1),'blue',.16)
        key(obj,'scale',[(start,.02),(min(end,start+600+i*350),1)],ctx,index=2)
        label('Step label',text,(0,y-.73,.9),.29)
        if i:box('Connection',(0,y-1.05,.2),(.1,.8,.1),'cyan',.01)
    camera(ctx,(9,-13,14),(0,0,1),ortho=14 if ctx['orientation']=='portrait' else 18)
    return {'objects':len(bpy.context.scene.objects),'action':'staged process reveal'}

BUILDERS={'market':market,'finance':finance,'process':process}
