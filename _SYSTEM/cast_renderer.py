"""Registered Blender cast staging appended to the shared character builder."""


def story_coin(name,at,color):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.115,depth=.034,location=at)
    obj=bpy.context.object;obj.name=name;obj.rotation_euler.x=math.pi/2
    metal=material(color)
    metal.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value=.82
    metal.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.27
    obj.data.materials.append(metal)
    bevel=obj.modifiers.new('Coin rounded edge','BEVEL');bevel.width=.014;bevel.segments=3
    return obj


def story_set(location,prop):
    PALETTE.update(silver=(.62,.69,.78,1),purple=(.16,.026,.25,1),plaster=(.36,.26,.15,1))
    box('Stage floor',(0,0,-.10),(30,30,.18),'wood',.02)
    box('Story back wall',(0,3,2.0),(12,.16,4.3),'plaster',.03)
    if location=='court':
        for x in (-3.1,3.1):
            capsule('Court column',(x,2.2,0),(x,2.2,3.7),.19,'paper')
            for z in (.14,3.6):box('Column capital',(x,2.2,z),(.64,.55,.17),'gold',.03)
        for x in (-1.6,1.6):
            box('Royal banner',(x,2.85,2.7),(.75,.07,1.9),'purple',.02)
            capsule('Banner gold rail',(x-.43,2.78,3.65),(x+.43,2.78,3.65),.035,'gold')
        box('Throne seat',(0,1.6,.65),(1.4,.7,.20),'red',.06)
        box('Throne back',(0,1.9,1.6),(1.42,.18,1.9),'gold',.06)
        box('Throne cushion',(0,1.76,1.62),(1.1,.1,1.55),'red',.08)
        box('Court exit opening',(-3.3,2.86,1.3),(1.1,.075,2.6),'pants',.02)
        for x in (-3.90,-2.70):box('Court exit frame',(x,2.78,1.4),(.10,.15,2.8),'gold',.02)
        box('Court exit lintel',(-3.3,2.78,2.8),(1.3,.15,.12),'gold',.02)
    elif location=='market':
        for x in (-2.5,2.5):
            box('Market counter',(x,1.55,.72),(1.7,.7,1.4),'wood',.05)
            for j in range(5):
                awning=box('Market awning',(x-.7+j*.35,1.55,2.55),(.34,1.6,.10),'red' if j%2 else 'paper',.01)
                awning.rotation_euler.x=.17
            for j in range(9):ellipsoid('Market produce',(x-.6+(j%3)*.48,1.30+(j//3)*.13,1.50),(.16,.13,.13),'mint')
    elif location=='room':
        for x in (-2.6,2.6):
            box('Room vertical beam',(x,2.9,2.1),(.18,.22,4.1),'wood',.02)
        box('Window dark opening',(-1.9,2.86,2.75),(1.4,.08,1.3),'pants',.02)
        capsule('Window bar',(-1.9,2.76,2.2),(-1.9,2.76,3.3),.028,'gold')
        box('Room bench',(2.1,1.7,.55),(1.4,.5,.22),'wood',.03)
    else:
        for x in (-3,3):
            capsule('Garden trunk',(x,1.7,0),(x,1.7,2.1),.11,'wood')
            ellipsoid('Garden crown',(x,1.7,2.5),(.7,.7,.85),'mint')
    props={}
    if prop=='chest':
        box('Chest plinth',(0,-.62,.44),(1.26,.72,.86),'wood',.04)
        box('Savings chest bottom',(0,-.62,.88),(1.22,.70,.06),'wood',.03)
        for y in (-.95,-.29):box('Savings chest wall',(0,y,1.025),(1.22,.075,.29),'wood',.025)
        for x in (-.575,.575):box('Savings chest side',(x,-.62,1.025),(.075,.70,.29),'wood',.025)
        ellipsoid('Savings chest clasp',(0,-1.0,1.06),(.07,.028,.075),'gold')
        for x in (-.48,.48):box('Chest gold strap',(x,-.99,1.025),(.07,.035,.30),'gold',.01)
        hinge=bpy.data.objects.new('Savings lid hinge',None);bpy.context.scene.collection.objects.link(hinge)
        hinge.location=(0,-.29,1.225)
        lid=box('Savings chest lid',(0,0,0),(1.25,.72,.10),'wood',.03)
        lid.parent=hinge;lid.location=(0,-.35,0)
        for i in range(96):
            layer=i//24;slot=i%24
            coin=story_coin('Saved silver coin',(-.47+(slot%6)*.185,-.84+(slot//6)*.145,.94+layer*.066),'silver')
            # Separate stacks so the savings read as coins, not a merged metal sheet.
            coin.scale.x=coin.scale.y=.56
            coin.rotation_euler=(0,0,i*.4)
        props['lid']=hinge
    elif prop=='coins':
        props['gold']=story_coin('Gold choice coin',(0,0,0),'gold')
        props['silver']=story_coin('Silver choice coin',(0,0,0),'silver')
        for coin in props.values():coin.scale=(1.35,1.35,1)
    elif prop=='scroll':
        box('Accusation scroll',(0,-.75,1.2),(.7,.07,.9),'paper',.02)
        for z in (.76,1.64):capsule('Scroll roll',(-.40,-.75,z),(.40,-.75,z),.06,'wood')
    elif prop=='hourglass':
        for z in (.62,1.48):box('Hourglass plate',(0,-.8,z),(.62,.42,.08),'gold',.02)
        capsule('Hourglass stem',(0,-.8,.65),(0,-.8,1.45),.035,'gold')
        ellipsoid('Hourglass upper glass',(0,-.8,1.25),(.19,.14,.20),'white')
        ellipsoid('Hourglass lower glass',(0,-.8,.85),(.19,.14,.20),'white')
    return props


def story_actor(actor):
    MATERIAL_STATE['prefix']=actor['id']+'_'+actor['profile']['identity_id'][:8]+'_'
    configure_character(actor['profile'])
    before=set(bpy.data.objects.keys())
    rig,rests,eyes=character(actor['profile'])
    parts=[obj for obj in bpy.data.objects if obj.name not in before and obj.type=='MESH']
    shape=actor['profile']['appearance']['shape']
    mouth_z=2.39-shape['height']*.42
    mouth_y=-.015-shape['depth']*math.sqrt(1-.42**2)-.019
    opening=ellipsoid('Expressive mouth',(0,mouth_y,mouth_z),(shape['mouth_width']*.85,.019,.044),'pants');bind(opening,rig,'head')
    teeth=ellipsoid('Mouth teeth',(0,mouth_y-.012,mouth_z+.012),(shape['mouth_width']*.63,.008,.012),'white');bind(teeth,rig,'head')
    grin=[];width=shape['mouth_width']*1.55
    for j in range(8):
        x1=-width+2*width*j/8;x2=-width+2*width*(j+1)/8
        curve=capsule('Curved smile',(x1,mouth_y-.028,mouth_z-.038+.070*(x1/width)**2),
            (x2,mouth_y-.028,mouth_z-.038+.070*(x2/width)**2),.012,'hair')
        bind(curve,rig,'head');grin.append(curve)
    if actor['costume']=='royal':
        crown=ellipsoid('Royal crown band',(0,.025,2.78),(.355,.28,.095),'gold');bind(crown,rig,'head')
        for j in range(5):
            bpy.ops.mesh.primitive_cone_add(vertices=5,radius1=.065,radius2=.008,depth=.18,location=(-.23+j*.115,-.13,2.89))
            peak=bpy.context.object;peak.name='Crown peak';peak.data.materials.append(material('gold'));bind(peak,rig,'head')
        robe=ellipsoid('Royal robe',(0,.02,1.32),(.37,.25,.57),'shirt');bind(robe,rig,'torso')
        pendant=ellipsoid('Royal pendant',(0,-.26,1.73),(.085,.035,.10),'gold');bind(pendant,rig,'torso')
    elif actor['costume'] in {'formal','scholar'}:
        coat=ellipsoid('Minister coat',(0,.02,1.32),(.32,.245,.55),'shirt');bind(coat,rig,'torso')
        for z in (1.36,1.58,1.79):
            button=ellipsoid('Formal gold button',(0,-.255,z),(.027,.022,.027),'gold');bind(button,rig,'torso')
        beard=ellipsoid('Mature beard',(0,-.245,2.135),(.14,.035,.06),'hair');bind(beard,rig,'head')
    rig.scale=(actor['scale'],)*3;rig['cast_id']=actor['id']
    MATERIAL_STATE['prefix']=''
    return dict(rig=rig,rests=rests,eyes=eyes,actor=actor,opening=opening,teeth=teeth,grin=grin,
        pupils=[p for p in parts if p.name.startswith('Pupil')],
        pupil_origins={p.name:p.location.copy() for p in parts if p.name.startswith('Pupil')},
        brows=[p for p in parts if p.name.startswith('Eyebrow')],
        mouths=[p for p in parts if p.name.startswith('Smile')])


def story_phase(q,index):
    return smooth((q-(.12+index*.26))/.26)


def story_pose(actor,action,t,progress,coin_target=None,coin_select=None,coin_hand='R'):
    rig,rests=actor['rig'],actor['rests']
    base='walk' if action=='depart' else 'think' if action=='think' else 'sit' if action=='sit' else 'stand'
    ends=action_pose(base,t,progress,[])
    if action=='rise':
        seated=action_pose('sit',t,progress,[])
        ends={name:(Vector(seated[name][0]).lerp(Vector(a),progress),Vector(seated[name][1]).lerp(Vector(b),progress)) for name,(a,b) in ends.items()}
        for p,side in (('L',-1),('R',1)):
            for upper_name,lower_name,pole in ((p+'_thigh',p+'_shin',(side*.18,-.60,.70)),
                (p+'_upperarm',p+'_forearm',(side*.65,.06,1.65))):
                root=Vector(ends[upper_name][0]);tip=Vector(ends[lower_name][1])
                a=(Vector(rests[upper_name][1])-Vector(rests[upper_name][0])).length
                b=(Vector(rests[lower_name][1])-Vector(rests[lower_name][0])).length
                joint,tip=solve_limb(root,tip,pole,a,b)
                ends[upper_name]=(root,joint);ends[lower_name]=(joint,tip)
                end_name=p+'_foot' if lower_name.endswith('shin') else p+'_hand'
                offset=Vector(ends[end_name][1])-Vector(ends[end_name][0]);ends[end_name]=(tip,tip+offset)
    if action in {'speak','ask','accuse','defend','show_savings','worry','smile','laugh','nod','open_chest'}:
        side=actor.get('gaze_side',1);p='R' if side>=0 else 'L';side=1 if side>=0 else -1
        shoulder=Vector(ends[p+'_upperarm'][0]);wrist=Vector((.50,-.03,1.23))
        if action=='speak':wrist=Vector((.45,-.36,1.60+.08*math.sin(t*3)))
        if action=='ask':wrist=Vector((.43,-.36,1.57))
        if action=='accuse':wrist=Vector((.65,-.35,1.86))
        if action=='defend':wrist=Vector((.43,-.38,2.10))
        if action=='show_savings':wrist=Vector((.26,-.45,1.32))
        if action=='open_chest':wrist=Vector((.13,-.47,1.39))
        if action=='worry':wrist=Vector((.12,-.30,2.28))
        if action=='laugh':wrist=Vector((.45,-.24,1.77+.055*math.sin(t*11)))
        wrist.x*=side
        wrist=Vector((side*.48,-.04,1.20)).lerp(wrist,progress)
        upper=(Vector(rests[p+'_upperarm'][1])-Vector(rests[p+'_upperarm'][0])).length
        fore=(Vector(rests[p+'_forearm'][1])-Vector(rests[p+'_forearm'][0])).length
        elbow,wrist=solve_limb(shoulder,wrist,(side*.67,.10,1.65),upper,fore)
        ends[p+'_upperarm']=(shoulder,elbow);ends[p+'_forearm']=(elbow,wrist)
        ends[p+'_hand']=(wrist,wrist+Vector((0,-.05,-.11)))
    if action=='tremble':
        for p,side in (('L',-1),('R',1)):
            shoulder=Vector(ends[p+'_upperarm'][0])
            target=Vector((side*.23+.032*math.sin(t*22+side),-.30,1.28+.02*math.sin(t*19)))
            wrist=Vector((side*.48,-.04,1.20)).lerp(target,progress)
            upper=(Vector(rests[p+'_upperarm'][1])-Vector(rests[p+'_upperarm'][0])).length
            fore=(Vector(rests[p+'_forearm'][1])-Vector(rests[p+'_forearm'][0])).length
            elbow,wrist=solve_limb(shoulder,wrist,(side*.65,.12,1.55),upper,fore)
            ends[p+'_upperarm']=(shoulder,elbow);ends[p+'_forearm']=(elbow,wrist)
            ends[p+'_hand']=(wrist,wrist+Vector((0,-.05,-.11)))
    if coin_target is not None:
        local=rig.matrix_world.inverted()@coin_target
        p=coin_hand
        shoulder=Vector(ends[p+'_upperarm'][0])
        # Keep a selected coin at chest height, including in child medium shots.
        home=Vector((-.30,-.20,1.65)) if p=='L' else Vector((.30,-.20,1.65))
        if coin_select is not None:
            approach=smooth(min(1.,coin_select/.48));retract=smooth((coin_select-.50)/.50)
            local=home.lerp(local,approach).lerp(home,retract)
        upper=(Vector(rests[p+'_upperarm'][1])-Vector(rests[p+'_upperarm'][0])).length
        fore=(Vector(rests[p+'_forearm'][1])-Vector(rests[p+'_forearm'][0])).length
        elbow,wrist=solve_limb(shoulder,local,(-.65,.12,1.55) if p=='L' else (.65,.12,1.55),upper,fore)
        ends[p+'_upperarm']=(shoulder,elbow);ends[p+'_forearm']=(elbow,wrist)
        ends[p+'_hand']=(wrist,wrist+Vector((0,-.06,-.10)))
    if action in {'nod','laugh','worry','ask'}:
        tilt=.065*math.sin(progress*math.pi*2) if action=='nod' else -.08 if action=='laugh' else .08
        ends['head']=((0,0,1.95),(.015*math.sin(t),tilt*progress,2.72))
    for name,(a,b) in ends.items():posed_bone(rig,name,a,b,rests[name])
    blink=.09 if t%3.8>3.64 else 1
    for eye in actor['eyes']:eye.scale.z=blink;eye.keyframe_insert(data_path='scale')
    for pupil in actor['pupils']:
        pupil.location=actor['pupil_origins'][pupil.name].copy()
        pupil.location.x+=.023*actor.get('gaze_side',0)
        pupil.keyframe_insert(data_path='location')
    for mouth in actor['mouths']:
        mouth.scale.x=1+.35*progress if action in {'smile','laugh'} else 1
        mouth.scale.z=1+1.7*abs(math.sin(t*8))*progress if action in {'speak','ask','defend'} else 1
        mouth.keyframe_insert(data_path='scale')
    openness=(.80+.70*abs(math.sin(t*7))) * smooth(min(1.,progress*3)) if action in {'speak','ask','defend','accuse'} else 1.15*progress if action=='laugh' else 0
    actor['opening'].scale.x=1.45 if action=='laugh' else 1
    actor['opening'].keyframe_insert(data_path='scale')
    actor['opening'].scale.z=openness
    actor['opening'].hide_render=openness<.02;actor['teeth'].hide_render=openness<.2
    actor['opening'].keyframe_insert(data_path='scale');actor['opening'].keyframe_insert(data_path='hide_render')
    actor['teeth'].keyframe_insert(data_path='hide_render')
    smiling=(action=='smile' and progress>.20) or actor.get('held_smile',False)
    for curve in actor['grin']:
        curve.hide_render=not smiling;curve.keyframe_insert(data_path='hide_render')
    for mouth in actor['mouths']:
        mouth.hide_render=openness>=.02 or smiling;mouth.keyframe_insert(data_path='hide_render')
    for j,brow in enumerate(actor['brows']):
        expressive=action in {'worry','ask','accuse'} or actor.get('emotion') in {'tense','concerned'}
        brow.rotation_euler.y=(.20 if j%2 else -.20)*(progress if action in {'worry','ask','accuse'} else .55) if expressive else 0
        brow.keyframe_insert(data_path='rotation_euler')
    return ends


def build(ctx,spec):
    params=spec['params'];direction=params['direction'];cast=params['cast']
    visible=direction['actors'];count=spec['end_frame']-spec['start_frame']
    MATERIAL_STATE['prefix']='';props=story_set(direction['location'],direction['prop'])
    actors={a['id']:story_actor(a) for a in cast if a['id'] in visible}
    for actor in actors.values():actor['emotion']=direction.get('emotion','neutral')
    positions={}
    for index,identity in enumerate(visible):
        x=0 if len(visible)==1 else (index-(len(visible)-1)/2)*(1.35 if len(visible)==3 else 1.40)
        positions[identity]=Vector((x,0,0));actors[identity]['rig'].location=positions[identity]
    seated_actor=next((b['actor'] for b in direction['beats'] if b['action'] in {'sit','rise'}),None)
    royal=next((identity for identity in visible if actors[identity]['actor']['costume']=='royal'),seated_actor)
    if direction['location']=='court' and royal is not None:
        for obj in bpy.context.scene.objects:
            if obj.name.startswith('Throne'):obj.location.x+=positions[royal].x
    scene=bpy.context.scene;scene.world=bpy.data.worlds.new('Story studio');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.015,.023,.045,1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.16
    for name,at,power,color,size in [('Story key',(-3,-4,6),1000,(1,.78,.55),3),('Story fill',(4,-3,3),240,(.50,.69,1),3),('Story rim',(0,3,4),1150,(1,.72,.38),2.4)]:
        bpy.ops.object.light_add(type='AREA',location=at);lamp=bpy.context.object;lamp.name=name
        lamp.data.energy=power;lamp.data.color=color;lamp.data.size=size;lamp.data.use_shadow=True
        lamp.rotation_euler=(Vector((0,0,1.4))-lamp.location).to_track_quat('-Z','Y').to_euler()
    scene.view_settings.view_transform='AgX'
    bpy.ops.object.camera_add(location=(1.3,-8.5,3.4));camera=bpy.context.object;scene.camera=camera
    camera.data.type='ORTHO';camera.data['shot_focus']='upper_body' if direction['camera']=='medium' else 'full_body'
    initial_owner=params.get('initial_coin_owner')
    if initial_owner is not None and initial_owner not in visible:raise ValueError('Initial coin owner must be visible')
    chooser=next((b['actor'] for b in direction['beats'] if b['action']=='choose_silver'),initial_owner or visible[-1])
    giver=next((b['actor'] for b in direction['beats'] if b['action']=='offer_coins'),next((a for a in visible if a!=chooser),visible[0]))
    scene['cast_ids']='|'.join(visible)
    giver_hand='R' if positions[giver].x<=positions[chooser].x else 'L'
    chooser_hand='L' if giver_hand=='R' else 'R'
    choice_index=next((i for i,b in enumerate(direction['beats']) if b['action']=='choose_silver'),None)
    opening_index=next((i for i,b in enumerate(direction['beats']) if b['action']=='open_chest'),None)
    rises={b['actor']:i for i,b in enumerate(direction['beats']) if b['action']=='rise'}
    sits={b['actor'] for b in direction['beats'] if b['action']=='sit'}
    if direction['prop']=='chest' and opening_index is None and any(b['action']=='show_savings' for b in direction['beats']):opening_index=0
    for frame in range(1,count+1):
        scene.frame_set(frame);q=(frame-1)/max(1,count-1);t=(frame-1)/ctx['fps']
        active={identity:('sit',1.) if identity in rises else ('stand',1.) for identity in visible}
        for i,beat in enumerate(direction['beats']):
            if q>=.12+i*.26:active[beat['actor']]=(beat['action'],story_phase(q,i))
        selected=story_phase(q,choice_index) if choice_index is not None else 1 if initial_owner else 0
        coin_target=Vector(((positions[giver].x+positions[chooser].x)/2,-.32,1.45))
        ends={}
        for identity,actor in actors.items():
            action,progress=active[identity]
            earlier=[(i,b['action']) for i,b in enumerate(direction['beats']) if b['actor']==identity and q>=.12+i*.26]
            last_expression=next(((i,a) for i,a in reversed(earlier) if a not in {'stand','wait','nod','tremble'}),None)
            actor['held_smile']=bool(action in {'stand','wait','nod','tremble'} and last_expression and last_expression[1]=='smile' and story_phase(q,last_expression[0])>.20)
            rig=actor['rig'];rig.location=positions[identity].copy()
            seat_progress=story_phase(q,rises[identity]) if identity in rises else 0
            if identity in rises:rig.location.y=1.42*(1-seat_progress)
            elif identity in sits and action=='sit':rig.location.y=1.42*progress
            departures=[(i,b) for i,b in enumerate(direction['beats']) if b['actor']==identity and b['action']=='depart' and q>=.12+i*.26]
            for index,beat in departures:
                distance=story_phase(q,index)
                # A forward lane keeps departure clear of stationary neighbors.
                rig.location.x-=1.10*distance;rig.location.y-=.90*distance
            if action=='laugh':rig.location.z=.014*math.sin(t*12)*progress
            partner=direction.get('listener','none') if identity==direction.get('speaker') else direction.get('speaker','none')
            side=(1 if positions[partner].x>positions[identity].x else -1) if partner in positions and partner!=identity else 0
            actor['gaze_side']=side
            yaw=.55*side
            if identity in rises:yaw*=seat_progress
            if action=='sit':yaw=0
            departure_yaw=-math.atan2(1.10,.90)
            if action=='depart':yaw=departure_yaw*progress
            elif departures:
                yaw=departure_yaw+(yaw-departure_yaw)*smooth(min(1.,progress*3))
            rig.rotation_mode='QUATERNION';rig.rotation_quaternion=(math.cos(yaw/2),0,0,math.sin(yaw/2))
            rig.keyframe_insert(data_path='location');rig.keyframe_insert(data_path='rotation_quaternion')
            bpy.context.view_layer.update()
            # Only an actual selection beat makes the receiver reach for a coin.
            target=coin_target.copy() if direction['prop']=='coins' and (identity==giver or (identity==chooser and (choice_index is not None or initial_owner is not None))) else None
            if target is not None and identity==chooser:target.x+=.20
            select=selected if identity==chooser and (choice_index is not None or initial_owner is not None) else None
            hand=giver_hand if identity==giver else chooser_hand
            ends[identity]=story_pose(actor,action,t,progress,target,select,hand)
        bpy.context.view_layer.update()
        if direction['prop']=='coins':
            hand=actors[giver]['rig'].matrix_world@Vector(ends[giver][giver_hand+'_forearm'][1])
            # Display the coin faces in front of the palm, outside the skin mesh.
            props['gold'].location=hand+Vector((-.20,-.18,-.07))
            if (choice_index is not None or initial_owner is not None) and selected>=.48:
                hand=actors[chooser]['rig'].matrix_world@Vector(ends[chooser][chooser_hand+'_forearm'][1])
                props['silver'].location=hand+Vector((0,-.18,-.07));scene['silver_owner']=chooser
            else:props['silver'].location=hand+Vector((.20,-.18,-.07));scene['silver_owner']=giver
            for name in ('gold','silver'):props[name].keyframe_insert(data_path='location')
        if 'lid' in props:
            # Open beyond vertical so the rear lid does not hide a child's face.
            props['lid'].rotation_euler.x=-2.70*(story_phase(q,opening_index) if opening_index is not None else 0)
            props['lid'].keyframe_insert(data_path='rotation_euler')
        average_scale=sum(a['actor']['scale'] for a in actors.values())/len(actors)
        height=1.70*max(a['actor']['scale'] for a in actors.values()) if direction['camera']=='medium' else 1.47*average_scale
        target=Vector((0,-.12,height))
        cue_id=direction.get('cue_id',spec['source_cues'][0])
        yaw=(.25 if direction['camera']=='two_shot' else -.16 if cue_id%2 else .16)
        position=Vector((yaw*8,-8.5,3.4));position.x+=.14*smooth(q)
        if direction['prop']=='chest':
            # A raised reveal angle makes the contents visible behind the rim.
            position.z=7.0
            target=Vector((0,-.35,1.48))
        camera.location=position;camera.rotation_euler=(target-position).to_track_quat('-Z','Y').to_euler()
        moving=any(b['action']=='depart' for b in direction['beats'])
        scale=6.6 if moving else {'wide':6.5,'medium':4.8,'two_shot':6.0}[direction['camera']]
        if direction['camera']=='medium' and len(visible)==3:scale=max(scale,5.5)
        if direction['prop']=='chest':scale=max(scale,6.0)
        camera.data.ortho_scale=scale*(1-.06*smooth(q))
        camera.keyframe_insert(data_path='location');camera.keyframe_insert(data_path='rotation_euler');camera.data.keyframe_insert(data_path='ortho_scale')
    if params.get('cast_portrait') is True:
        for obj in scene.objects:
            if obj.type=='MESH' and obj.parent not in [a['rig'] for a in actors.values()]:obj.hide_render=True
        actor=actors[visible[0]];height=2.43*actor['actor']['scale']
        for frame in range(1,count+1):
            scene.frame_set(frame);target=Vector((0,-.01,height));position=Vector((.5,-6,height+.22))
            camera.location=position;camera.rotation_euler=(target-position).to_track_quat('-Z','Y').to_euler()
            camera.data.ortho_scale=2.0*actor['actor']['scale']
            camera.keyframe_insert(data_path='location');camera.keyframe_insert(data_path='rotation_euler');camera.data.keyframe_insert(data_path='ortho_scale')
        camera.data['shot_focus']='face'
    scene.frame_set(1)
