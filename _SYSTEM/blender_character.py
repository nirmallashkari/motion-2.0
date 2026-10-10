"""Original reusable articulated character and offline physical scene library.

Generated geometry is host-owned. Inputs choose only registered actions/cameras.
The rigid segmented skin is driven by a real armature, not a flat sprite.
"""
import bpy
import math
from mathutils import Vector, Matrix, Quaternion

PALETTE = {"skin":(.58,.30,.16,1),"shirt":(.045,.25,.38,1),"pants":(.055,.095,.15,1),
    "hair":(.045,.035,.025,1),"shoe":(.055,.065,.073,1),"sole":(.58,.65,.64,1),
    "white":(.88,.91,.89,1),"eye":(.015,.023,.029,1),"wood":(.32,.17,.085,1),
    "mint":(.24,.43,.36,1),"wall":(.52,.59,.52,1),"floor":(.29,.32,.28,1),
    "gold":(.70,.42,.12,1),"paper":(.82,.76,.60,1),"red":(.49,.12,.10,1)}
MATERIAL_STATE = {'prefix':''}


def material(name):
    scoped_name=MATERIAL_STATE['prefix']+name
    known = bpy.data.materials.get(scoped_name)
    if known:return known
    mat=bpy.data.materials.new(scoped_name);mat.use_nodes=True
    node=mat.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value=PALETTE[name]
    node.inputs["Roughness"].default_value=.64
    return mat


def ellipsoid(name,at,size,color):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,radius=1,location=at)
    obj=bpy.context.object;obj.name=name;obj.scale=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.data.materials.append(material(color))
    for face in obj.data.polygons:face.use_smooth=True
    return obj


def box(name,at,size,color,bevel=.06):
    bpy.ops.mesh.primitive_cube_add(size=1,location=at)
    obj=bpy.context.object;obj.name=name;obj.scale=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.data.materials.append(material(color))
    mod=obj.modifiers.new("Rounded edges","BEVEL");mod.width=bevel;mod.segments=3
    obj.modifiers.new("Weighted surface normals","WEIGHTED_NORMAL")
    return obj


def capsule(name,a,b,r,color):
    a,b=Vector(a),Vector(b)
    obj=ellipsoid(name,(a+b)/2,(r,r,(b-a).length/2+r*.42),color)
    obj.rotation_euler=(b-a).to_track_quat("Z","Y").to_euler()
    return obj


def bind(obj,rig,bone):
    # Object geometry is in armature-space coordinates after mesh creation.
    obj.parent=rig
    group=obj.vertex_groups.new(name=bone)
    group.add(list(range(len(obj.data.vertices))),1.0,"REPLACE")
    modifier=obj.modifiers.new("Character skeleton","ARMATURE");modifier.object=rig


def skeleton():
    data=bpy.data.armatures.new("Reusable human skeleton")
    rig=bpy.data.objects.new("Character_Rig",data);bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    rests={"torso":((0,0,1.13),(0,0,1.95)),"head":((0,0,1.95),(0,0,2.72))}
    for side in (-1,1):
        prefix="L" if side==-1 else "R"
        rests[prefix+"_thigh"]=((side*.18,0,1.15),(side*.18,0,.65))
        rests[prefix+"_shin"]=((side*.18,0,.65),(side*.18,0,.16))
        rests[prefix+"_upperarm"]=((side*.36,0,1.94),(side*.47,0,1.57))
        rests[prefix+"_forearm"]=((side*.47,0,1.57),(side*.48,-.04,1.20))
        rests[prefix+"_hand"]=((side*.48,-.04,1.20),(side*.48,-.04,1.045))
        rests[prefix+"_foot"]=((side*.18,0,.16),(side*.18,-.24,.16))
    for name,(head,tail) in rests.items():
        bone=data.edit_bones.new(name);bone.head=head;bone.tail=tail
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.select_set(False)
    return rig,rests


def character(profile=None):
    rig,rests=skeleton()
    appearance=profile['appearance'] if profile else None
    shape=appearance['shape'] if appearance else dict(width=.33,height=.405,depth=.29,eye_spacing=.117,
        eye_size=.072,nose_width=.065,nose_length=.085,brow_radius=.018,mouth_width=.085)
    width,height,depth=shape['width'],shape['height'],shape['depth']
    style=appearance['hairstyle'] if appearance else 'swept_wave'
    if profile:rig['character_identity_id']=profile['identity_id']
    pieces=[]
    pieces.append((ellipsoid("Tailored shirt",(0,0,1.61),(.35,.235,.46),"shirt"),"torso"))
    pieces.append((ellipsoid("Hip trousers",(0,0,1.12),(.29,.21,.19),"pants"),"torso"))
    pieces.append((ellipsoid("Neck",(0,0,2.02),(.13,.13,.17),"skin"),"head"))
    pieces.append((ellipsoid("Face",(0,-.015,2.39),(width,depth,height),"skin"),"head"))
    top=2.39+height*.62
    pieces.append((ellipsoid("Hair cap",(0,.025,top),(width*1.035,depth*.983,.19),"hair"),"head"))
    if style=='soft_curls':
        for j in range(9):
            angle=j*2.4
            pieces.append((ellipsoid('Hair curl',(math.sin(angle)*width*.67,math.cos(angle)*depth*.57,top+.10+(j%3)*.028),(.108,.105,.092),'hair'),'head'))
    elif style=='textured_crop':
        for j in range(5):
            pieces.append((ellipsoid('Textured hair',(-width*.68+j*width*.34,-.12,top+.075),(.095,.13,.065),'hair'),'head'))
    else:
        for index in range(3):
            sweep=-.045*index if style=='side_part' else index*.014
            pieces.append((ellipsoid("Swept hair",(-width*.545+index*width*.439,-.14,top+.01+sweep),(.175,.17,.087),"hair"),"head"))
        if style=='long_bob':
            for side in (-1,1):
                pieces.append((ellipsoid('Long hair side',(side*width*.98,.065,2.40),(.092,depth*.88,.34),'hair'),'head'))
    nose_y=-.015-depth+.006
    pieces.append((ellipsoid("Nose",(0,nose_y,2.36),(shape['nose_width'],shape['nose_length'],.072),"skin"),"head"))
    mouth_z=2.39-height*.42
    mouth_y=-.015-depth*math.sqrt(1-.42**2)-.005
    pieces.append((capsule("Smile",(-shape['mouth_width'],mouth_y,mouth_z),(shape['mouth_width'],mouth_y,mouth_z),.013,"hair"),"head"))
    eyes=[]
    for side in (-1,1):
        prefix="L" if side==-1 else "R"
        pieces.append((ellipsoid("Ear",(side*width*1.006,0,2.39),(.057,.081,.10),"skin"),"head"))
        ex=shape['eye_spacing'];ey=-.015-depth*math.sqrt(1-(ex/width)**2)+.006;ez=2.39+height*.10
        white=ellipsoid("Eye white",(side*ex,ey,ez),(shape['eye_size'],.030,.052),"white")
        pupil=ellipsoid("Pupil",(side*ex,ey-.025,ez-.001),(.029,.019,.038),"eye")
        pieces.extend([(white,"head"),(pupil,"head")]);eyes.extend([white,pupil])
        by=ey+.001;bz=ez+.086
        pieces.append((capsule("Eyebrow",(side*(ex-.05),by,bz),(side*(ex+.053),by+.008,bz+.004),shape['brow_radius'],"hair"),"head"))
        if appearance and appearance['glasses']:
            for j in range(8):
                a=j*math.pi/4;b=(j+1)*math.pi/4
                pieces.append((capsule('Glasses rim',(side*ex+.087*math.cos(a),ey-.043,ez+.065*math.sin(a)),
                    (side*ex+.087*math.cos(b),ey-.043,ez+.065*math.sin(b)),.009,'hair'),'head'))
            pieces.append((capsule('Glasses arm',(side*(ex+.08),ey-.04,ez),(side*width,.06,ez),.008,'hair'),'head'))
        for section,color,radius in (("thigh","pants",.14),("shin","pants",.113),
                                    ("upperarm","shirt",.107),("forearm","skin",.080)):
            a,b=rests[prefix+"_"+section]
            pieces.append((capsule(prefix+" "+section,a,b,radius,color),prefix+"_"+section))
        pieces.append((ellipsoid("Elbow",rests[prefix+"_forearm"][0],(.084,.084,.084),"skin"),prefix+"_forearm"))
        pieces.append((ellipsoid("Hand",(side*.48,-.057,1.15),(.083,.065,.116),"skin"),prefix+"_hand"))
        for finger in range(3):
            pieces.append((capsule("Finger",(side*.48+(finger-1)*.031,-.079,1.113),
                (side*.48+(finger-1)*.031,-.082,1.045),.020,"skin"),prefix+"_hand"))
        pieces.append((ellipsoid("Thumb",(side*.421,-.10,1.16),(.042,.042,.067),"skin"),prefix+"_hand"))
        pieces.append((ellipsoid("Sneaker",(side*.18,-.085,.135),(.13,.245,.117),"shoe"),prefix+"_foot"))
        pieces.append((ellipsoid("Sole",(side*.18,-.09,.064),(.136,.246,.046),"sole"),prefix+"_foot"))
    if appearance and appearance['glasses']:
        pieces.append((capsule('Glasses bridge',(-.04,ey-.043,ez),(.04,ey-.043,ez),.009,'hair'),'head'))
    for obj,bone in pieces:bind(obj,rig,bone)
    return rig,rests,eyes


def configure_character(profile):
    """Only bounded host-designed proportions and material colors reach Blender."""
    if profile is None:return
    if profile.get('revision')!='story-character-1.0':raise ValueError('Unknown story character revision')
    appearance=profile['appearance']
    if appearance['hairstyle'] not in {'side_part','textured_crop','soft_curls','swept_wave','long_bob'}:
        raise ValueError('Unregistered story hairstyle')
    bounds={'width':(.305,.355),'height':(.365,.425),'depth':(.275,.310),'eye_spacing':(.104,.130),
        'eye_size':(.062,.078),'nose_width':(.047,.075),'nose_length':(.068,.096),
        'brow_radius':(.013,.022),'mouth_width':(.067,.093)}
    if set(appearance['shape'])!=set(bounds):raise ValueError('Invalid face parameters')
    for name,(low,high) in bounds.items():
        value=appearance['shape'][name]
        if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
            raise ValueError('Story face geometry exceeds bounded limits')
    if set(appearance['palette'])!={'skin','hair','shirt','pants'}:raise ValueError('Invalid character materials')
    for name,color in appearance['palette'].items():
        if len(color)!=4 or color[3]!=1 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in color):
            raise ValueError('Invalid story character color')
        PALETTE[name]=tuple(color)


def posed_bone(rig,name,a,b,rest):
    a,b=Vector(a),Vector(b);length=(Vector(rest[1])-Vector(rest[0])).length
    # Minimal rotation from the rest axis avoids the 180-degree roll flips
    # produced by a tracking quaternion near a vertical head/torso axis.
    direction=(Vector(rest[1])-Vector(rest[0])).normalized()
    orientation=direction.rotation_difference((b-a).normalized())@rig.data.bones[name].matrix_local.to_quaternion()
    matrix=Matrix.LocRotScale(a,orientation,Vector((1,(b-a).length/length,1)))
    bone=rig.pose.bones[name];bone.matrix=matrix
    bone.keyframe_insert(data_path="location");bone.keyframe_insert(data_path="rotation_quaternion")
    bone.keyframe_insert(data_path="scale")


def book():
    cover=box("Open book cover",(0,-.71,1.25),(.57,.38,.045),"red",.02)
    for side in (-1,1):
        pages=box("Book pages",(side*.142,-.71,1.285),(.278,.35,.040),"paper",.01)
        pages.rotation_euler.y=side*.11
        for line in range(4):box("Printed lines",(side*.142,-.79+line*.045,1.31),(.20,.008,.004),"wood",.001)
    return cover


def environment(name,action):
    box("Ground",(0,0,-.11),(200,200,.18),"floor",.02)
    if name=="outdoor":
        box("Path",(0,0,-.012),(2.8,15,.045),"paper",.03)
        for side in (-1,1):
            for j in range(3):
                capsule("Tree trunk",(side*2.5,j*3-1,0),(side*2.5,j*3-1,2),.11,"wood")
                ellipsoid("Tree crown",(side*2.5,j*3-1,2.25),(.78,.66,.84),"mint")
    else:
        box("Back wall",(0,2.4,1.85),(9,.15,3.9),"wall",.04)
        box("Window frame",(-2,2.28,2.3),(1.38,.13,1.36),"wood",.03)
        box("Window glass",(-2,2.19,2.3),(1.22,.04,1.20),"white",.02)
        for x in (-2.0,):box("Window mullion",(x,2.12,2.3),(.045,.06,1.20),"wood",.01)
        box("Wall artwork",(1.75,2.24,2.4),(.85,.09,1.03),"paper",.04)
        ellipsoid("Artwork shape",(1.75,2.17,2.45),(.24,.015,.34),"mint")
        box("Plant pot",(-1.4,1.4,.24),(.36,.36,.48),"wood",.05)
        for j in range(4):
            leaf=ellipsoid("Plant leaf",(-1.4+math.sin(j)*.16,1.4,.66+j*.10),(.13,.07,.30),"mint")
            leaf.rotation_euler.y=math.sin(j)*.48
    if name=="study":
        box("Desk top",(0,-.78,1.23),(1.85,.78,.10),"wood",.04)
        for x in (-.75,.75):
            for y in (-1.05,-.48):box("Desk leg",(x,y,.59),(.075,.075,1.18),"wood",.015)
        box("Chair seat",(0,.22,.64),(.58,.52,.11),"mint",.05)
        box("Chair back",(0,.48,1.02),(.61,.10,.72),"mint",.04)
        for x in (-.23,.23):
            for y in (.04,.40):box("Chair leg",(x,y,.32),(.06,.06,.64),"wood",.01)
        book()
        box("Lamp base",(.66,-.66,1.32),(.22,.22,.07),"gold",.03)
        capsule("Lamp stem",(.66,-.66,1.34),(.66,-.66,1.79),.025,"gold")
        ellipsoid("Lamp shade",(.66,-.66,1.78),(.15,.15,.08),"gold")
        if action=="carry_phone":
            # Keep the doorway path free of the reader's chair and furniture.
            for obj in bpy.context.scene.objects:
                if obj.name.startswith(("Desk ","Chair ","Open book","Book pages","Printed lines","Lamp ")):
                    obj.location.x-=1.25
                if obj.name.startswith(("Back wall","Window","Wall artwork","Artwork shape")):
                    obj.location.y+=1.4
    elif name=="living":
        if action!="meditate":
            box("Seat cushion",(0,.13,.57),(1.3,.64,.24),"mint",.12)
            box("Sofa back",(0,.56,1.02),(1.4,.22,.91),"mint",.12)
        box("Mat",(0,-.1,.018),(1.9,1.8,.035),"paper",.08)
    elif name=="bedroom":
        box("Bed base",(0,0,.45),(1.28,3.10,.48),"wood",.10)
        box("Mattress",(0,0,.74),(1.30,3.05,.20),"paper",.12)
        box("Pillow",(0,1.02,.91),(.65,.43,.19),"white",.10)
        box("Bed headboard",(0,1.46,.90),(1.40,.13,1.25),"wood",.06)
        box("Bedside table",(-.95,.80,.55),(.48,.48,1.10),"wood",.045)
        ellipsoid("Alarm body",(-.95,.77,1.27),(.16,.075,.16),"gold")
        ellipsoid("Alarm face",(-.95,.695,1.27),(.135,.008,.135),"white")
        capsule("Hour hand",(-.95,.682,1.27),(-.95,.682,1.35),.010,"eye")
        capsule("Minute hand",(-.95,.682,1.27),(-.86,.682,1.27),.009,"eye")
    elif name=="gym":
        box("Exercise mat",(0,0,.013),(1.7,2.7,.035),"mint",.07)
        for j in range(3):
            capsule("Rack dumbbell",(1.65,1.4,.65+j*.29),(2.1,1.4,.65+j*.29),.055,"sole")
            for x in (1.65,2.1):ellipsoid("Rack weight",(x,1.4,.65+j*.29),(.12,.11,.11),"pants")
    return None


def setup_camera(mode,ctx,action):
    positions={"wide":(4.3,-7.2,4.0),"medium":(3.6,-6.7,3.4),"detail":(2.6,-5.9,3.0)}
    bpy.ops.object.camera_add(location=positions[mode]);cam=bpy.context.object
    target=(0,.9,1.45) if action=="carry_phone" else (0,-.12,.95 if action in {"sleep","meditate"} else 1.70 if mode=="detail" else 1.38)
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()
    cam.data.type="ORTHO";cam.data.ortho_scale={"wide":6.4,"medium":5.6,"detail":4.5}[mode]
    bpy.context.scene.camera=cam
    return cam


REGISTERED = {'walk','read','phone','lift','run','meditate','sleep','carry_phone','write','type',
    'drink','eat','explain','point','wave','celebrate','think','sad','stretch','pushup','squat',
    'jump','listen','stand','sit','carry_box','shop','cook','water_plant','paint','cycle','talk'}
SEATED = {'read','write','type','phone','drink','eat','listen','sit','cycle'}
LOCOMOTION = {'walk','run','carry_phone','carry_box'}


def smooth(value):
    value=max(0,min(1,value))
    return value*value*(3-2*value)


def solve_limb(root,target,pole,length_a,length_b):
    """Analytic two-link IK preserves segment lengths and joint continuity."""
    root,target,pole=Vector(root),Vector(target),Vector(pole)
    delta=target-root;distance=max(.015,min(delta.length,length_a+length_b-.002))
    direction=delta.normalized() if delta.length>.001 else Vector((0,0,-1))
    distance=max(abs(length_a-length_b)+.002,distance)
    target=root+direction*distance
    projection=(distance*distance+length_a*length_a-length_b*length_b)/(2*distance)
    height=math.sqrt(max(0,length_a*length_a-projection*projection))
    bend=pole-root;normal=bend-direction*bend.dot(direction)
    if normal.length<.001:normal=direction.cross(Vector((0,1,0)))
    if normal.length<.001:normal=direction.cross(Vector((1,0,0)))
    return root+direction*projection+normal.normalized()*height,target


def gait(t,side,running=False):
    period=.66 if running else 1.36
    phase=(t/period+(.5 if side==1 else 0))%1
    width=.27 if running else .22
    if phase<.62:
        return -width+2*width*(phase/.62),0
    swing=(phase-.62)/.38
    return width-2*width*smooth(swing),(.19 if running else .11)*math.sin(math.pi*swing)


def extended_environment(room,action):
    environment('living' if room in {'kitchen','studio'} else 'outdoor' if room=='market' else room,action)
    if room=='living' and action not in SEATED|{'meditate'}:
        for obj in bpy.context.scene.objects:
            if obj.name.startswith(('Seat cushion','Sofa back')):obj.location.x-=1.9
    if room in {'studio','kitchen'}:
        for obj in bpy.context.scene.objects:
            if obj.name.startswith(('Seat cushion','Sofa back')):obj.hide_render=True
    if action in {'write','type'}:
        for obj in bpy.context.scene.objects:
            if obj.name.startswith(('Open book','Book pages','Printed lines')):obj.hide_render=True
    if action=='write':
        box('Notebook',(0,-.72,1.305),(.53,.34,.032),'paper',.015)
        for j in range(4):box('Notebook line',(0,-.8+j*.045,1.325),(.42,.008,.003),'mint',.001)
    if action=='type':
        box('Laptop base',(0,-.73,1.315),(.63,.36,.042),'pants',.025)
        monitor=box('Laptop screen',(0,-.94,1.56),(.63,.035,.43),'pants',.025)
        monitor.rotation_euler.x=-.12
        display=box('Laptop display',(0,-.963,1.56),(.55,.012,.35),'mint',.015)
        display.rotation_euler.x=-.12
        for row in range(3):
            for col in range(6):box('Keyboard key',(-.23+col*.09,-.77+row*.065,1.34),(.06,.04,.012),'sole',.005)
    if room=='market':
        box('Produce counter',(0,-1.1,.81),(2.8,.9,1.6),'wood',.04)
        box('Market canopy',(0,-1.1,3.05),(3.0,1.2,.13),'mint',.04)
        for side in (-1,1):capsule('Stall support',(side*1.4,-1.1,0),(side*1.4,-1.1,3.1),.045,'wood')
        for j in range(6):ellipsoid('Produce',(-.8+j*.32,-1.1,1.73),(.12,.12,.12),'red' if j%2 else 'gold')
    if room=='kitchen':
        box('Kitchen counter',(0,-.87,1.12),(2.7,.9,.22),'paper',.035)
        for x in (-1.0,1.0):box('Cabinet',(x,-.87,.52),(.65,.85,1.0),'mint',.04)
        box('Cooktop',(0,-.76,1.255),(1.0,.6,.045),'pants',.025)
        ellipsoid('Cooking pan',(0,-.70,1.34),(.29,.29,.05),'sole')
        capsule('Pan handle',(.21,-.7,1.34),(.62,-.7,1.34),.04,'pants')
    if room=='studio':
        for x in (-.55,.55):capsule('Easel leg',(x,-1.1,.0),(0,-1.1,2.6),.037,'wood')
        box('Canvas',(0,-.88,1.84),(1.05,.07,1.13),'paper',.04)
        for j in range(3):ellipsoid('Paint mark',(-.21+j*.17,-.835,1.7+j*.15),(.11,.015,.18),'mint' if j%2 else 'gold')
    if action in {'explain','point'}:
        box('Presentation board',(1.2,.36,1.95),(1.2,.10,1.0),'paper',.03)
        for j in range(3):box('Diagram bar',(.85+j*.32,.29,1.7+j*.09),(.17,.03,.24+j*.18),'mint',.01)
        capsule('Board stand',(1.2,.4,0),(1.2,.4,1.5),.055,'wood')
    if action=='celebrate':
        box('Trophy plinth',(-1.4,-.15,.55),(.5,.5,1.1),'wood',.04)
        ellipsoid('Trophy cup',(-1.4,-.15,1.4),(.24,.24,.24),'gold')
        capsule('Trophy stem',(-1.4,-.15,1.1),(-1.4,-.15,1.25),.06,'gold')
    if action=='water_plant':
        box('Flower planter',(.6,-.62,.30),(.6,.5,.6),'wood',.04)
        for j in range(3):
            capsule('Plant stem',(.6,-.62,.57),(.6+j*.08,-.62,.95+j*.15),.018,'mint')
            ellipsoid('Flower bloom',(.6+j*.08,-.62,.95+j*.15),(.13,.10,.13),'gold')
    if action=='cycle':
        for y in (-.88,.91):
            bpy.ops.mesh.primitive_torus_add(major_radius=.39,minor_radius=.038,major_segments=32,minor_segments=8,location=(0,y,.44),rotation=(0,math.pi/2,0))
            wheel=bpy.context.object;wheel.name='Bicycle wheel';wheel.data.materials.append(material('pants'))
            for j in range(8):
                a=j*math.pi/4
                spoke=capsule('Wheel spoke',(0,y,.44),(0,y+.37*math.cos(a),.44+.37*math.sin(a)),.008,'sole')
                spoke.parent=wheel;spoke.matrix_parent_inverse=wheel.matrix_world.inverted()
        for a,b in [((0,.9,.44),(0,0,1.02)),((0,0,1.02),(0,-.88,.44)),((0,-.88,.44),(0,0,.54)),((0,0,.54),(0,.9,.44))]:capsule('Bike frame',a,b,.035,'red')
        box('Bicycle saddle',(0,.13,1.07),(.25,.32,.07),'pants',.03)
        capsule('Handlebar post',(0,-.7,.75),(0,-.7,1.48),.035,'sole')
        capsule('Handlebar',(-.36,-.7,1.48),(.36,-.7,1.48),.032,'pants')


def prop_objects(action,rig):
    props={}
    if action in {'phone','carry_phone'}:
        props['phone']=[box('Phone',(0,0,0),(.15,.033,.26),'pants',.025),box('Phone screen',(0,0,0),(.123,.008,.205),'white',.01)]
    if action=='lift':
        props['weight']=[capsule('Dumbbell handle',(-.20,0,0),(.20,0,0),.043,'sole')]
        for x in (-.20,.20):props['weight'].append(ellipsoid('Dumbbell plate',(x,0,0),(.09,.15,.15),'pants'))
    if action in {'drink','eat','write','paint','cook','water_plant','carry_box','shop'}:
        name={'drink':'Cup','eat':'Spoon','write':'Pen','paint':'Brush','cook':'Stirring spoon','water_plant':'Watering can','carry_box':'Carried box','shop':'Basket'}[action]
        if action in {'write','paint','cook','eat'}:
            props['held']=[capsule(name,(0,0,-.13),(0,0,.13),.017 if action in {'write','paint'} else .030,'gold')]
        elif action=='drink':
            props['held']=[box(name,(0,0,0),(.18,.18,.24),'paper',.07)]
        elif action=='water_plant':
            props['held']=[box(name,(0,0,0),(.32,.22,.28),'mint',.04),capsule('Can spout',(0,0,0),(.25,-.12,-.10),.025,'mint')]
            props['water']=[ellipsoid('Water drop',(0,0,0),(.017,.017,.032),'mint') for j in range(5)]
        elif action=='carry_box':props['held']=[box(name,(0,0,0),(.67,.42,.46),'wood',.035)]
        else:props['held']=[box(name,(0,0,0),(.40,.28,.32),'wood',.035)]
    if action=='eat':props['bowl']=[ellipsoid('Bowl',(0,-.46,1.04),(.20,.18,.09),'paper')]
    if action=='cycle':
        props['pedals']=[box('Bicycle pedal',(0,0,0),(.25,.14,.035),'pants',.012) for side in (-1,1)]
        props['cranks']=[capsule('Pedal crank',(side*.18,-.05,.54),(side*.18,-.05,.72),.015,'sole') for side in (-1,1)]
    if action in {'listen','run'}:
        for side in (-1,1):
            ear=ellipsoid('Headphone ear cup',(side*.36,0,2.40),(.055,.105,.12),'pants');bind(ear,rig,'head')
        band=capsule('Headphone band',(-.30,.04,2.75),(.30,.04,2.75),.027,'pants');bind(band,rig,'head')
    return props


def action_pose(action,t,q,beats):
    """Reusable poses with stable feet, fixed limb lengths and speech accents."""
    pulse=max([math.exp(-((t-b)/.14)**2) for b in beats] or [0])
    hip=.77 if action in SEATED else .38 if action=='meditate' else 1.13
    hip+=.005*math.sin(t*2.2)
    if action=='cycle':hip=.98
    if action=='squat':hip=1.13-.40*(.5-.5*math.cos(t*2.8))
    airborne=.30*max(0,math.sin(t*3.3)) if action in {'jump','celebrate'} else 0
    hip+=airborne
    shift=hip-1.13
    ends={'torso':((0,0,hip),(0,.012*math.sin(t*1.6),1.95+shift)),
          'head':((0,0,1.95+shift),(.018*math.sin(t*1.1),-.035 if action in {'read','write','phone','sad'} else 0,2.72+shift))}
    for side in (-1,1):
        p='L' if side==-1 else 'R'
        root=(side*.18,0,1.15+shift)
        ankle=(side*.18,0,.16+airborne)
        pole=(side*.18,-.45,.65+shift)
        if action in LOCOMOTION:
            distance,lift=gait(t,side,action=='run');ankle=(side*.18,distance,.16+lift)
        if action in SEATED:
            ankle=(side*.18,-.49,.16);pole=(side*.18,-.65,.6)
        if action=='meditate':ankle=(-side*.17,-.35,.12);pole=(side*.65,-.2,.25)
        if action=='cycle':
            angle=t*4+side*math.pi/2;ankle=(side*.18,-.05+.18*math.cos(angle),.54+.18*math.sin(angle))
        if action=='stretch':root=(side*.18,0,1.15);ankle=(side*.32,0,.16)
        knee,ankle=solve_limb(root,ankle,pole,.50,.49)
        ends[p+'_thigh']=(root,knee);ends[p+'_shin']=(knee,ankle)
        ends[p+'_foot']=(ankle,Vector(ankle)+Vector((0,-.24,0)))
        shoulder=(side*.36,0,1.94+shift)
        wrist=(side*.48,-.04,1.20+shift)
        elbow_pole=(side*.65,.06,1.58+shift)
        if action in LOCOMOTION:
            swing=.20*math.sin(t*(9.5 if action=='run' else 4.62)+side*math.pi/2)
            wrist=(side*.48,swing,1.23+shift+( .12 if action=='run' else 0))
        if action in {'read','write','type'}:
            wrist=(side*.23,-.62,1.34+.013*math.sin(t*(10 if action=='type' else 3)+side))
            if action=='write' and side==1:wrist=(.12+.045*math.sin(t*5),-.69+.023*math.cos(t*4),1.37+.008*pulse)
        if action=='phone':wrist=(side*.10,-.43,1.32+.018*math.sin(t*3+side))
        if action=='meditate':wrist=(side*.42,-.28,.48)
        if action=='lift' and side==1:wrist=(.46,-.30,1.38+.35*(.5-.5*math.cos(t*3)))
        if action=='carry_phone' and side==1:wrist=(.48,-.24,1.24)
        if action in {'drink','eat'}:
            progress=.5-.5*math.cos(t*2)
            if side==1:wrist=(.12,-.39,1.18+.54*progress)
            else:wrist=(-.18,-.35,1.14)
        if action in {'talk','explain'}:
            wrist=(side*.53,-.25,1.50+.11*math.sin(t*3+side)+.06*pulse)
        if action=='point' and side==1:wrist=(.88,.12,1.91)
        if action=='wave' and side==1:wrist=(.66+.10*math.sin(t*6),-.02,2.12)
        if action in {'celebrate','stretch'}:wrist=(side*.46,0,2.54+shift)
        if action=='think' and side==1:wrist=(.13,-.25,2.19)
        if action=='sad':wrist=(side*.35,-.05,1.24);ends['head']=((0,0,1.95),(0,-.13,2.70))
        if action=='listen' and side==1:wrist=(.35,-.06,2.38)
        if action=='carry_box':wrist=(side*.35,-.43,1.26)
        if action=='shop' and side==1:wrist=(.51,-.33,1.26+.06*math.sin(t*2))
        if action=='cook':wrist=(side*.18,-.59,1.47) if side==-1 else (.12+.11*math.cos(t*3),-.67+.08*math.sin(t*3),1.57)
        if action=='water_plant' and side==1:wrist=(.55,-.41,1.43)
        if action=='paint' and side==1:wrist=(.10+.15*math.sin(t*2),-.66,1.89+.11*math.sin(t*3))
        if action=='cycle':wrist=(side*.33,-.70,1.50)
        elbow,wrist=solve_limb(shoulder,wrist,elbow_pole,.386,.372)
        ends[p+'_upperarm']=(shoulder,elbow);ends[p+'_forearm']=(elbow,wrist)
        hand_direction=(0,-.11,-.11) if action in {'read','write','type','phone','paint','cook','drink','eat'} else (0,0,-.155)
        ends[p+'_hand']=(wrist,Vector(wrist)+Vector(hand_direction).normalized()*.155)
    if action=='pushup':
        # A horizontal torso stays over two grounded palms and two grounded toes.
        height=.63+.16*(.5+.5*math.cos(t*3))
        ends['torso']=((0,.25,height),(0,-.57,height+.08))
        ends['head']=((0,-.57,height+.08),(0,-1.29,height+.11))
        for side in (-1,1):
            p='L' if side==-1 else 'R';hip=(side*.18,.25,height)
            ankle=(side*.18,1.1,.16);knee,ankle=solve_limb(hip,ankle,(side*.18,.7,.32),.5,.49)
            ends[p+'_thigh']=(hip,knee);ends[p+'_shin']=(knee,ankle)
            ends[p+'_foot']=(ankle,Vector(ankle)+Vector((0,.24,0)))
            shoulder=(side*.36,-.57,height+.08);wrist=(side*.45,-.64,.18)
            elbow,wrist=solve_limb(shoulder,wrist,(side*.75,-.30,.45),.386,.372)
            ends[p+'_upperarm']=(shoulder,elbow);ends[p+'_forearm']=(elbow,wrist)
            ends[p+'_hand']=(wrist,Vector(wrist)+Vector((0,-.155,0)))
    return ends


def build(ctx,spec):
    params=spec['params'];action=params['action'];room=params['environment']
    if action not in REGISTERED:raise ValueError('Unknown registered character action')
    profile=params.get('character_profile');configure_character(profile)
    extended_environment(room,action)
    rig,rests,eyes=character(profile);props=prop_objects(action,rig)
    scene=bpy.context.scene;count=spec['end_frame']-spec['start_frame'];duration=count/ctx['fps']
    emotion=params.get('emotion','neutral');move=params.get('camera_move','push');camera_mode=params['camera']
    if emotion not in {'neutral','focused','happy','concerned'} or move not in {'push','orbit','locked','tracking'}:
        raise ValueError('Unregistered expression or camera movement')
    rig.rotation_mode='QUATERNION'
    for bone in rig.pose.bones:bone.rotation_mode='QUATERNION'
    if action=='carry_phone':
        for x in (-.83,.83):box('Door frame',(x,1.52,1.65),(.12,.16,3.30),'wood',.02)
        box('Door lintel',(0,1.52,3.3),(1.79,.16,.12),'wood',.02)
        hinge=bpy.data.objects.new('Door hinge',None);scene.collection.objects.link(hinge);hinge.location=(-.75,1.42,0)
        door=box('Door leaf',(0,0,0),(1.51,.075,3.10),'paper',.03);door.parent=hinge;door.location=(.75,0,1.57)
    belt=[]
    if action=='run':
        box('Treadmill platform',(0,0,.035),(1.30,2.6,.08),'pants',.04)
        for x in (-.57,.57):capsule('Treadmill rail',(x,-1.04,.12),(x,-1.04,1.48),.04,'sole')
        box('Treadmill console',(0,-1.07,1.49),(1.16,.20,.19),'pants',.035)
        for j in range(6):belt.append(box('Belt tread',(0,-1.05+j*.4,.086),(1.10,.03,.006),'sole',.001))
    if action=='sleep':
        for obj in scene.objects:
            if obj.name.startswith(('Sneaker','Sole')):obj.hide_render=True
        for side in (-1,1):
            foot=ellipsoid('Bare foot',(side*.18,-.067,.13),(.10,.18,.087),'skin');bind(foot,rig,'L_foot' if side==-1 else 'R_foot')
    scene.world=bpy.data.worlds.new('Soft studio world');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.45,.53,.59,1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.25
    for name,position,power,color,size in [('Warm key',(-3,-4,6),800,(1,.86,.72),4),('Cool fill',(4,-2,4),350,(.73,.86,1),4),('Soft rim',(0,3,5),850,(1,.92,.80),3)]:
        bpy.ops.object.light_add(type='AREA',location=position);lamp=bpy.context.object
        lamp.name=name;lamp.data.energy=power;lamp.data.color=color;lamp.data.size=size;lamp.data.use_shadow=name=='Warm key'
        lamp.data.shadow_maximum_resolution=.02;lamp.data.shadow_filter_radius=2
        lamp.rotation_euler=(Vector((0,0,1.3))-lamp.location).to_track_quat('-Z','Y').to_euler()
    scene.view_settings.view_transform='AgX'
    cam=setup_camera(camera_mode,ctx,action)
    if action=='paint':cam.location=(5.5,1.8,3.8)
    camera_start=cam.location.copy()
    target=Vector((0,.9,1.45)) if action=='carry_phone' else Vector((0,-.12,.80 if action=='pushup' else .95 if action in {'sleep','meditate'} else 1.38))
    cam.data['shot_target']=list(target)
    brows=[obj for obj in scene.objects if obj.name.startswith('Eyebrow')]
    mouth=bpy.data.objects.get('Smile')
    beats=params.get('speech_beats',[])
    for frame in sorted(set(list(range(1,count+1,2))+[count])):
        scene.frame_set(frame);t=(frame-1)/ctx['fps'];q=(frame-1)/max(1,count-1)
        ends=action_pose(action,t,q,beats)
        rig.rotation_quaternion=(1,0,0,0);rig.location=(0,0,.065 if action=='run' else 0)
        if action=='sleep':rig.rotation_quaternion=Vector((0,0,1)).rotation_difference(Vector((0,1,0)));rig.location=(0,-1.4,.87)
        if action=='carry_phone':
            rig.rotation_quaternion=(0,0,0,1);rig.location=(0,q*2.20,0)
            hinge.rotation_euler.z=math.pi*.48*smooth(q/.18);hinge.keyframe_insert(data_path='rotation_euler')
        if action in {'walk','carry_box'}:rig.location.y=(duration*.16-t*.32)
        rig.keyframe_insert(data_path='location');rig.keyframe_insert(data_path='rotation_quaternion')
        for name,(a,b) in ends.items():posed_bone(rig,name,a,b,rests[name])
        bpy.context.view_layer.update()
        wrist=rig.matrix_world@Vector(ends['R_forearm'][1])
        if 'phone' in props:
            anchor=rig.matrix_world@Vector((0,-.47,1.38)) if action=='phone' else wrist+Vector((0,.035,.045))
            for i,obj in enumerate(props['phone']):
                obj.location=anchor+Vector((0,(.022 if action=='carry_phone' else -.022)*i,0));obj.rotation_euler.z=math.pi if action=='carry_phone' else 0
                obj.keyframe_insert(data_path='location')
        if 'weight' in props:
            for i,obj in enumerate(props['weight']):obj.location=wrist+Vector((0 if i==0 else -.20 if i==1 else .20,0,0));obj.keyframe_insert(data_path='location')
        if 'held' in props:
            for i,obj in enumerate(props['held']):
                offset=Vector((0,0,-.04))
                if action in {'write','paint','cook'}:offset=Vector((0,-.05,-.10))
                if action=='carry_box':offset=Vector((-.35,-.06,.06))
                if action=='shop':offset=Vector((0,0,-.18))
                obj.location=wrist+offset+Vector((.10,-.06,0))*i
                obj.rotation_euler.y=.22 if action=='water_plant' else -.18 if action=='drink' else 0
                if action=='paint':obj.rotation_euler.x=math.pi/2
                obj.keyframe_insert(data_path='location');obj.keyframe_insert(data_path='rotation_euler')
        for j,drop in enumerate(props.get('water',[])):
            drop.location=(.77,-.58,1.30-((t*.8+j*.12)%.60));drop.keyframe_insert(data_path='location')
        if action=='cycle':
            for i,side in enumerate((-1,1)):
                pedal=props['pedals'][i];crank=props['cranks'][i];end=Vector(ends[('L' if side==-1 else 'R')+'_shin'][1])
                pedal.location=end+Vector((0,-.08,-.12));pedal.keyframe_insert(data_path='location')
                start=Vector((side*.18,-.05,.54));crank.location=(start+end)/2
                crank.rotation_euler=(end-start).to_track_quat('Z','Y').to_euler()
                crank.keyframe_insert(data_path='location');crank.keyframe_insert(data_path='rotation_euler')
            for wheel in [obj for obj in scene.objects if obj.name.startswith('Bicycle wheel')]:
                wheel.rotation_mode='QUATERNION'
                wheel.rotation_quaternion=Quaternion((1,0,0),t*3)@Quaternion((0,1,0),math.pi/2)
                wheel.keyframe_insert(data_path='rotation_quaternion')
        if action=='paint':
            marks=[obj for obj in scene.objects if obj.name.startswith('Paint mark')]
            for j,mark in enumerate(marks):
                growth=.01+.99*smooth((q-j*.23)/.40);mark.scale=(growth,1,growth);mark.keyframe_insert(data_path='scale')
        blink=.055 if action in {'sleep','meditate'} else .10 if t%3.7>3.54 else .70 if emotion=='focused' else 1
        for eye in eyes:eye.scale.z=blink;eye.keyframe_insert(data_path='scale')
        for j,brow in enumerate(brows):
            brow.rotation_euler.y=(.18 if j==0 else -.18) if emotion=='concerned' else 0
        if mouth:
            mouth.scale.z=1+.5*max(0,math.sin(t*7)) if action in {'talk','explain'} else 1
            mouth.keyframe_insert(data_path='scale')
        for j,tread in enumerate(belt):tread.location.y=-1.05+(j*.4+t*.8)%2.4;tread.keyframe_insert(data_path='location')
        cam.location=camera_start
        if move=='tracking' or action in {'walk','carry_box','carry_phone'}:cam.location.y+=rig.location.y*.65
        if move=='orbit':
            angle=.065*math.sin(q*math.pi);cam.location.x=camera_start.x*math.cos(angle)-camera_start.y*math.sin(angle)
            cam.location.y=camera_start.x*math.sin(angle)+camera_start.y*math.cos(angle)
        look=target+Vector((0,rig.location.y*.65 if action in {'walk','carry_box','carry_phone'} else 0,0))
        cam.rotation_euler=(look-cam.location).to_track_quat('-Z','Y').to_euler()
        cam.data.ortho_scale={'wide':6.4,'medium':5.6,'detail':4.5}[camera_mode]*(1-.045*smooth(q) if move!='locked' else 1)
        cam.keyframe_insert(data_path='location');cam.keyframe_insert(data_path='rotation_euler');cam.data.keyframe_insert(data_path='ortho_scale')
    if params.get('theme'):
        cinematic_story(scene,ctx,spec,rig,rests,eyes)
    if params.get('shot_profile'):
        line_camera(scene,ctx,spec)
    if params.get('character_portrait') is True:
        # Generate a neutral identity reference before story staging.
        cam=scene.camera
        scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.012,.023,.039,1)
        scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.18
        for obj in scene.objects:
            if obj.type=='MESH' and obj.parent!=rig:obj.hide_render=True
            if obj.type=='LIGHT':
                obj.data.use_shadow=True;obj.data.size=2.4
                if obj.name=='Warm key':obj.data.energy=620;obj.data.color=(1,.86,.73)
                if obj.name=='Cool fill':obj.data.energy=140;obj.data.color=(.56,.74,1)
                if obj.name=='Soft rim':obj.data.energy=760;obj.data.color=(.68,.82,1)
        target=Vector((0,-.03,2.38));position=Vector((.65,-5.4,2.60))
        for frame in range(1,count+1):
            scene.frame_set(frame);cam.location=position
            cam.rotation_euler=(target-position).to_track_quat('-Z','Y').to_euler()
            cam.data.ortho_scale=1.9
            cam.keyframe_insert(data_path='location');cam.keyframe_insert(data_path='rotation_euler')
            cam.data.keyframe_insert(data_path='ortho_scale')
        cam.data['shot_focus']='face'
    scene.frame_set(1)


def cinematic_story(scene,ctx,spec,rig,rests,eyes):
    """Reusable narrative staging, motivated props, acting and portrait framing."""
    theme=spec['params']['theme'];count=spec['end_frame']-spec['start_frame']
    dark=theme in {'reflection','fear','night_reflection','criticism','exhaustion','selfworth','struggle'}
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.08 if dark else .18
    for obj in scene.objects:
        if obj.name.startswith(('Window','Wall artwork','Artwork shape','Plant pot','Plant leaf','Sofa back','Seat cushion','Mat')):
            obj.hide_render=True
        if obj.name.startswith('Back wall') and theme not in {'night_reflection','destiny','effort'}:obj.hide_render=True
        if obj.type=='LIGHT':
            obj.data.use_shadow=True
            if obj.name=='Warm key':obj.data.energy=650 if dark else 1100;obj.data.size=2.2;obj.data.color=(1,.78,.54)
            if obj.name=='Cool fill':obj.data.energy=100 if dark else 250;obj.data.color=(.32,.61,1)
            if obj.name=='Soft rim':obj.data.energy=1250;obj.data.size=1.8;obj.data.color=(.34,.65,1) if dark else (1,.63,.24)
    for name,color in [('floor',(.028,.045,.064,1)),('wall',(.045,.068,.095,1)),('wood',(.16,.09,.045,1))]:
        mat=bpy.data.materials.get(name)
        if mat:mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=color
    mirror=None;mirror_rests=None;mirror_eyes=[];arrows=[];gate=[];work_marks=[];ink_marks=[]
    direction=spec['params'].get('action_plan');variant=direction.get('variant',0) if direction else 0
    if theme=='reflection':
        mirror,mirror_rests,mirror_eyes=character(spec['params'].get('character_profile'));mirror.rotation_mode='QUATERNION'
        for bone in mirror.pose.bones:bone.rotation_mode='QUATERNION'
        box('Reflection backing',(0,3.65,1.50),(1.7,.05,3.05),'wall',.02)
        for x in (-.91,.91):box('Mirror upright',(x,1.60,1.5),(.10,.10,3.14),'gold',.03)
        for z in (.02,3.03):box('Mirror frame',(0,1.60,z),(1.92,.10,.10),'gold',.025)
    if theme=='selfworth':
        box('Fractured mirror',(-1.2,.5,1.3),(1.0,.055,2.4),'sole',.02)
        for j in range(5):capsule('Mirror fracture',(-1.55+j*.15,.463,.2),(-.86-j*.06,.463,2.48),.012,'hair')
    if theme=='criticism' and variant==0:
        for side in (-1,1):
            for j in range(3):
                shaft=capsule('Judgment arrow shaft',(side*1.5,-.12,1.35+j*.40),(side*2.2,-.12,1.35+j*.40),.03,'red')
                bpy.ops.mesh.primitive_cone_add(vertices=16,radius1=.10,radius2=0,depth=.24,location=(side*1.4,-.12,1.35+j*.40))
                tip=bpy.context.object;tip.name='Judgment arrow tip';tip.data.materials.append(material('red'))
                tip.rotation_euler=Vector((-side,0,0)).to_track_quat('Z','Y').to_euler()
                arrows.append((shaft,tip,side,j))
    if theme=='criticism' and variant==1:
        for side in (-1,1):
            panel=box('Judgment gate',(side*1.1,.85,1.42),(.95,.12,2.8),'wood',.03)
            gate.append((panel,side))
        box('Gate lintel',(0,.85,2.90),(3.15,.16,.16),'gold',.035)
    if theme=='fear' and variant==1:
        box('Shadow barrier',(-1.3,1.3,1.4),(.45,.22,2.8),'wall',.04)
    if theme=='effort':
        # A physical task board provides a legible result without transcript text.
        box('Task progress backing',(-.82,.40,1.94),(1.25,.08,.90),'pants',.04)
        for j in range(3):
            marker=box('Completed task block',(-1.27+j*.40,.34,1.94),(.31,.035,.58),'mint',.025)
            work_marks.append(marker)
    if theme=='destiny':
        for j in range(3):ink_marks.append(box('Written notebook line',(-.18,-.72+j*.085,1.348),(.38,.017,.005),'hair',.001))
    if theme=='struggle':
        for side in (-1,1):
            for j in range(5):
                box('Path obstacle',(side*(.95+j%2*.25),j*1.1-2,.15+j%3*.08),(.6,.55,.3+j%3*.16),'wood',.035)
        for j in range(7):box('Broken paving',(0,j*.80-2.4,-.015),(1.4,.63,.035),'paper',.012)
    cam=scene.camera;mode=spec['params']['camera']
    focus='full_body';scale=5.7;target=Vector((0,0,1.45));position=Vector((3.4,-7,3.1))
    if theme in {'fear','criticism','exhaustion','selfworth','confidence','resolve'}:
        if mode=='detail':focus='face';scale=2.35;target=Vector((0,-.02,2.35));position=Vector((1.5,-6,2.9))
        elif mode=='medium':focus='upper_body';scale=3.9;target=Vector((0,0,1.95));position=Vector((2.4,-6,3.0))
    if theme=='reflection':position=Vector((2,-7,3.3));target=Vector((0,1.3,1.45));scale=6.7
    if theme=='night_reflection':position=Vector((3.9,-5,3.2));target=Vector((0,.1,.95));scale=5.3
    if theme in {'destiny','effort'}:focus='upper_body';position=Vector((2.3,-5.8,3.0));target=Vector((0,-.2,1.60));scale=4.8
    cam.data['shot_focus']=focus
    cam.data['shot_target']=list(target)
    pupil_origins={obj.name:obj.location.copy() for obj in scene.objects if obj.name.startswith('Pupil')}
    for frame in sorted(set(list(range(1,count+1,2))+[count])):
        scene.frame_set(frame);q=(frame-1)/max(1,count-1);t=(frame-1)/ctx['fps'];progress=smooth((q-.20)/.58) if direction else smooth(q)
        if theme=='reflection':
            rig.rotation_quaternion=Quaternion((0,0,1),math.pi);rig.location=(0,0,0)
            mirror.rotation_quaternion=(1,0,0,0);mirror.location=(0,3.2,0);mirror.scale=(-1,1,1)
            ends=action_pose('think',t,q,[])
            shoulder=(.36,0,1.94);lift=progress if direction else smooth(min(1,q*2.5))
            wrist=Vector((.48,-.04,1.20)).lerp(Vector((.13,-.25,2.19)),lift)
            elbow,wrist=solve_limb(shoulder,wrist,(.67,-.25,1.60),.386,.372)
            ends['R_upperarm']=(shoulder,elbow);ends['R_forearm']=(elbow,wrist);ends['R_hand']=(wrist,Vector(wrist)+Vector((0,0,-.155)))
            for name,(a,b) in ends.items():posed_bone(rig,name,a,b,rests[name])
            for name,(a,b) in ends.items():posed_bone(mirror,name,a,b,mirror_rests[name])
            mirror.keyframe_insert(data_path='location');mirror.keyframe_insert(data_path='rotation_quaternion')
            for eye in mirror_eyes:eye.scale.z=.1 if t%3.7>3.54 else 1;eye.keyframe_insert(data_path='scale')
        if theme in {'resolve','confidence','exhaustion','fear','criticism','selfworth'}:
            action=spec['params']['action'];ends=action_pose(action,t,q,[])
            if theme in {'resolve','confidence'}:
                ends['head']=((0,0,1.95),(0,-.13*(1-progress),2.70+.025*progress))
                for side in (-1,1):
                    prefix='L' if side<0 else 'R';shoulder=(side*.36,0,1.94)
                    if side>0:
                        wrist=(.28,-.30,1.25+progress*.74) if theme=='resolve' else (.08+progress*.52,-.30,1.88-progress*.12)
                    else:wrist=(-.40,-.05,1.23+progress*.06)
                    elbow,wrist=solve_limb(shoulder,wrist,(side*.65,-.3,1.55),.386,.372)
                    ends[prefix+'_upperarm']=(shoulder,elbow);ends[prefix+'_forearm']=(elbow,wrist)
                    ends[prefix+'_hand']=(wrist,Vector(wrist)+Vector((0,0,-.155)))
            else:
                tilt=.045+.11*progress if theme=='exhaustion' else .075+.06*math.sin(q*math.pi)
                ends['head']=((0,0,1.95),(.025*math.sin(t),-tilt,2.70))
                if theme in {'criticism','selfworth','exhaustion'}:
                    reaction=smooth(min(1,progress*2.4))*(1-.35*smooth((progress-.65)/.35))
                    for side in (-1,1):
                        prefix='L' if side<0 else 'R';shoulder=(side*.36,0,1.94)
                        wrist=Vector((side*.35,-.05,1.24)).lerp(Vector((side*.15,-.30,1.78 if theme=='criticism' else 2.11 if side>0 else 1.40)),reaction)
                        elbow,wrist=solve_limb(shoulder,wrist,(side*.65,-.28,1.58),.386,.372)
                        ends[prefix+'_upperarm']=(shoulder,elbow);ends[prefix+'_forearm']=(elbow,wrist);ends[prefix+'_hand']=(wrist,Vector(wrist)+Vector((0,0,-.155)))
            for name,(a,b) in ends.items():posed_bone(rig,name,a,b,rests[name])
        if theme in {'effort','destiny'} and direction:
            active_t=min(1.,max(0.,(q-.20)/.58))*(count/ctx['fps'])*.58
            ends=action_pose(spec['params']['action'],active_t,progress,[])
            for name,(a,b) in ends.items():posed_bone(rig,name,a,b,rests[name])
        for j,marker in enumerate(work_marks):
            growth=.01+.99*smooth((progress-j/3)*3)
            marker.scale.z=growth;marker.keyframe_insert(data_path='scale')
        for j,marker in enumerate(ink_marks):
            marker.scale.x=.01+.99*smooth((progress-j/3)*3);marker.keyframe_insert(data_path='scale')
        for panel,side in gate:
            panel.location.x=side*(1.55-.92*progress);panel.keyframe_insert(data_path='location')
        if direction:
            # Animate the actual facial geometry, with restrained acting.
            concerned=theme in {'fear','exhaustion','criticism','selfworth','night_reflection'}
            for j,brow in enumerate([obj for obj in scene.objects if obj.name.startswith('Eyebrow')]):
                brow.rotation_euler.y=(-1 if j%2 else 1)*(.10+.14*progress if concerned else .07*(1-progress))
                brow.keyframe_insert(data_path='rotation_euler')
            for eye in [obj for obj in scene.objects if obj.name.startswith('Pupil')]:
                eye.location.x=pupil_origins[eye.name].x+(-.012 if concerned else .010)*math.sin(progress*math.pi)
                eye.keyframe_insert(data_path='location')
            mouth=bpy.data.objects.get('Smile')
            if mouth:
                mouth.scale.x=.7 if concerned else .9+.16*progress;mouth.keyframe_insert(data_path='scale')
        if theme=='night_reflection':
            for eye in eyes:eye.scale.z=.55+.35*math.sin(q*math.pi);eye.keyframe_insert(data_path='scale')
        for shaft,tip,side,index in arrows:
            move=side*(-.36*math.sin(progress*math.pi+index*.18))
            shaft.location.x=side*1.85+move;tip.location.x=side*1.4+move
            shaft.keyframe_insert(data_path='location');tip.keyframe_insert(data_path='location')
        rig.keyframe_insert(data_path='location');rig.keyframe_insert(data_path='rotation_quaternion')
        camera=position.copy();angle=.06*(q-.5)
        camera.x=position.x*math.cos(angle)-position.y*math.sin(angle)
        camera.y=position.x*math.sin(angle)+position.y*math.cos(angle)
        look=target.copy()
        if theme=='struggle':camera.y+=rig.location.y*.7;look.y+=rig.location.y*.7
        cam.location=camera;cam.rotation_euler=(look-camera).to_track_quat('-Z','Y').to_euler()
        cam.data.ortho_scale=scale*(1-.11*progress)
        cam.keyframe_insert(data_path='location');cam.keyframe_insert(data_path='rotation_euler');cam.data.keyframe_insert(data_path='ortho_scale')
    scene.frame_set(1)


def line_camera(scene,ctx,spec):
    """Change actual rendered camera position/movement for each repeated subject."""
    profile=spec['params']['shot_profile'];count=spec['end_frame']-spec['start_frame']
    yaw=float(profile['yaw']);move=profile['move']
    if not -.43<=yaw<=.43 or move not in {'push','pull','orbit'}:
        raise ValueError('Unregistered line camera profile')
    camera=scene.camera
    samples=[]
    for frame in sorted(set(list(range(1,count+1,2))+[count])):
        scene.frame_set(frame)
        samples.append((frame,camera.location.copy(),camera.data.ortho_scale))
    for frame,position,scale in samples:
        scene.frame_set(frame);q=(frame-1)/max(1,count-1)
        target=Vector(camera.data.get('shot_target',(0,-.12,.95 if spec['params']['action']=='sleep' else 1.38)))
        if spec['params']['action'] in {'walk','carry_phone','carry_box'}:
            target.y+=bpy.data.objects['Character_Rig'].location.y*.65
        offset=position-target;angle=yaw+(.18*math.sin(q*math.pi*2) if move=='orbit' else 0)
        rotated=Vector((offset.x*math.cos(angle)-offset.y*math.sin(angle),
                        offset.x*math.sin(angle)+offset.y*math.cos(angle),offset.z))
        camera.location=target+rotated
        camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.ortho_scale=scale*((1+.11*q)/(1-.11*q) if move=='pull' else 1)
        camera.keyframe_insert(data_path='location');camera.keyframe_insert(data_path='rotation_euler')
        camera.data.keyframe_insert(data_path='ortho_scale')
    scene.frame_set(1)
