"""Shared scene grammar for source-mentioned subjects across multiple topics.

All scene variation is validated data. This renderer has no per-script branches.
"""


def story_sprite(p,name,x,y,size,t,angle=0):
    frame=sprite(p.ctx,name,t)
    extent=max(1,round(size*2*p.zoom))
    frame=frame.resize((extent,extent),Image.Resampling.LANCZOS)
    if angle:frame=frame.rotate(angle,Image.Resampling.BICUBIC,expand=True)
    cx,cy=p.point(x,y)
    p.image.paste(frame,(cx-frame.width//2,cy-frame.height//2),frame)


def story_environment(p,domain,t,q):
    if domain in ('transport','market'):
        p.poly([(-800,460),(2080,460),(2080,1000),(-800,1000)],'#a49a80')
        for i in range(-2,10):
            x=i*188-(t*39)%188
            height=110+(i*41)%138
            p.rect((x,460-height,x+136,466),'#738b8a',6)
            for row in range(3):
                for col in range(3):p.rect((x+16+col*35,465-height+row*40,x+32+col*35,486-height+row*40),'#b2c3b7',3)
        p.poly([(-800,532),(2080,532),(2080,615),(-800,615)],'#45626a')
        for y in (544,598):p.line([(-800,y),(2080,y)],'#c0c9bd',7)
        for j in range(22):
            x=j*96-(t*150)%96-300
            p.line([(x,536),(x+28,610)],'#31494f',9)
        if domain=='market':
            for i in range(4):
                x=95+i*310
                fold=progress(q,.25,.75)
                p.line([(x,423),(x,621)],'#76604b',10)
                p.line([(x+220,423),(x+220,621)],'#76604b',10)
                half=mix(147,38,fold)
                p.poly([(x+110,302),(x+110-half,421),(x+110+half,421)],['#b97057','#6b9881'][i%2])
                p.rect((x-5,601,x+235,626),'#80634f',5)
    elif domain=='science':
        # Abstract orbital tracks are illustrative unless two subjects are named.
        for i in range(47):
            x=(i*173+29+t*7)%1430-75;y=55+(i*73)%572
            p.circle(x,y,1.5+(i%3)*.6,'#afc0c6')
        for radius in (220,330,445):p.ellipse((640-radius,360-radius*.43,640+radius,360+radius*.43),None,'#334b68',2)
    elif domain=='nature' or domain=='neutral':
        p.circle(1055,142,59,'#e7c78a')
        p.poly([(-700,539),(165,236),(481,494),(801,280),(1370,545),(1970,305),(2200,840),(-700,840)],'#8aa697')
        p.poly([(-700,640),(354,454),(690,582),(1184,446),(2080,639),(2080,1000),(-700,1000)],'#577e72')
        p.poly([(517,447),(591,456),(904,800),(615,800)],'#c5b396')
        for j in range(14):
            x=j*113-90-(t*9)%113
            p.line([(x,650),(x+8,628),(x+17,650)],'#93aa86',3)
    elif domain=='finance':
        p.poly([(-800,470),(2080,470),(2080,1100),(-800,1100)],'#967959')
        for yy in (529,604,703):p.line([(-800,yy),(2080,yy)],'#b18f6b',3)
        p.rect((135,100,391,301),'#c6b48f',15)
        p.line([(170,264),(170,142)],'#6c8a80',6);p.line([(170,264),(352,264)],'#6c8a80',6)
        p.rect((869,124,1143,301),'#6f837a',12)
        for j in range(4):p.rect((889+j*58,154,925+j*58,271),'#b9be9c',5)
    elif domain=='health':
        p.poly([(-800,557),(2080,557),(2080,1000),(-800,1000)],'#b0c1b5')
        for x in range(40,1400,110):p.line([(x,84),(x,556)],'#aac1bb',2)
        for y in range(115,556,110):p.line([(0,y),(1280,y)],'#aac1bb',2)
        p.rect((67,344,318,389),'#708d8f',12)
        p.line([(83,390),(83,595)],'#527178',11);p.line([(301,390),(301,595)],'#527178',11)
        p.rect((1035,192,1162,423),'#66868b',8)
    else:
        film_room(p,False,'study')


def render_story(t,ctx,spec):
    duration=max(.001,ctx.scene_end-ctx.scene_start)
    q=max(0,min(1,t/duration))
    domain=spec.get('domain','work')
    action=spec.get('action','cutaway')
    variant=spec.get('shot_variant',0)
    palette='night' if domain=='science' else 'warm' if domain=='finance' else 'gym' if domain=='health' else 'day'
    # A common camera grammar varies framing without writing fresh scene code.
    zoom=1.0+.13*q
    cx=640+54*(q-.5);cy=360
    if variant==1 and q>.52:zoom=1.25+.1*q;cy=392
    if variant==2:cx=660-96*q;zoom=1.13+.08*q
    camera=shot_camera_2d(spec['shot_profile'],q) if spec.get('shot_profile') else (cx,cy,zoom)
    p=FilmPainter(palette,camera)
    p.ctx=ctx;p.time=t
    story_environment(p,domain,t,q)
    if spec['kind']=='abstract':
        x=mix(342,852,progress(q,0,1))
        # Abstract transitions contain no people, silhouettes or human sprites.
        p.ellipse((x-48,598,x+48,621),'#45645f')
        p.circle(x,560+math.sin(t*2)*18,29,'#e6cd98')
        p.circle(x-8,551+math.sin(t*2)*18,9,'#fff0c8')
        for j in range(9):
            a=t*.7+j*.4
            px=361+j*65;py=230+math.sin(a)*42
            p.circle(px,py,4+j%3,'#e6cd98')
            if j:p.line([(px-65,230+math.sin(a-.4)*42),(px,py)],'#d8c49d',3)
        return p.finish()
    main=spec['main_asset'];other=spec.get('secondary_asset')
    if action=='travel':
        x=mix(319,964,progress(q,0,1));y=414+math.sin(t*2)*8
        p.ellipse((x-143,533,x+153,556),'#526563')
        story_sprite(p,main,x,y,304,t)
        if other:story_sprite(p,other,1122,439,156,t)
    elif action=='transfer':
        for x in (292,988):p.rect((x-124,310,x+124,590),'#748d86',20,outline='#b0c8ba',w=4)
        x=mix(292,988,progress(q,0,1));y=417-71*math.sin(q*math.pi)
        story_sprite(p,main,x,y,255,t)
        if other:story_sprite(p,other,991,201,119,t)
    elif action=='pair':
        movement=progress(q,0,1)
        a=mix(289,508,movement);b=mix(991,772,movement)
        story_sprite(p,main,a,397,267,t)
        story_sprite(p,other or main,b,397,267,t)
        p.line([(a+98,551),(b-98,551)],'#b18b52',7)
        for j in range(3):p.circle(a+108+(b-a-216)*(j+q%1)/3,551,7,'#e2bd75')
    elif action=='compare':
        story_sprite(p,main,mix(454,337,q),393,mix(229,329,q),t)
        story_sprite(p,other or main,mix(826,965,q),393,mix(329,229,q),t)
        p.line([(641,181),(641,573)],'#85978c',4)
        arrow(p,(345,597),(345,548),'#486e66',5)
        arrow(p,(957,548),(957,597),'#a86853',5)
    elif action=='build':
        for j in range(4):
            entry=progress(q,j*.16,j*.16+.37)
            if j==0 or entry>0:
                x=389+j*161;y=mix(520 if j==0 else 779,474-j*41,entry)
                p.ellipse((x-66,568-j*22,x+66,588-j*22),'#736e57')
                story_sprite(p,main,x,y,151,t)
        if other:story_sprite(p,other,637,168,117,t)
    elif action=='orbit':
        angle=q*math.pi*1.7
        # Only a named secondary object is depicted as a literal orbiting subject.
        story_sprite(p,main,640,368,273,t)
        if other:story_sprite(p,other,640+333*math.cos(angle),368+176*math.sin(angle),117,t)
        else:
            for j in range(3):p.circle(640+333*math.cos(angle+j*2.094),368+176*math.sin(angle+j*2.094),13,'#dfc17d')
    else:
        x=mix(448,768,q);y=385-27*math.sin(q*math.pi)
        story_sprite(p,main,x,y,mix(259,354,q),t,-7+14*q)
        if other:story_sprite(p,other,1016,454,171,t)
    return p.finish()
