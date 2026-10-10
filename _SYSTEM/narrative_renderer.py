"""Original human-free motion scenes for registered source-related metaphors."""


def render_narrative(t,ctx,spec):
    duration=max(.001,ctx.scene_end-ctx.scene_start);q=max(0,min(1,t/duration))
    if spec.get('action_plan'):q=action_clock(q)
    theme=spec['theme'];v=spec.get('shot_variant',0)
    camera=shot_camera_2d(spec['shot_profile'],q) if spec.get('shot_profile') else (640,360,1+.08*q)
    p=FilmPainter('night',camera);p.ctx=ctx;p.time=t
    gold='#f8b657';light='#ffe6a5';blue='#6cc8ec';red='#ed6b54';dark='#243547'
    # Depth cues and a moving pool of light frame the object instead of a slide.
    for j in range(4):
        p.ellipse((110-j*30,50-j*20,1170+j*30,700+j*20),None,'#1b2b40',2)
    for j in range(22):
        x=(j*173+t*(12+j%4*5))%1280;y=(j*83)%680+20
        p.circle(x,y,1+j%3,'#34465c')
    if theme=='time_loss':
        cx,cy=466,350
        p.circle(cx,cy,204,'#152b40');p.circle(cx,cy,194,None,gold,8)
        for j in range(12):
            a=j*math.pi/6;p.line([(cx+math.sin(a)*170,cy-math.cos(a)*170),(cx+math.sin(a)*183,cy-math.cos(a)*183)],light,5)
        for length,speed,width in ((144,4.5,8),(101,.7,13)):
            a=t*speed;p.line([(cx,cy),(cx+math.sin(a)*length,cy-math.cos(a)*length)],light,width)
        p.circle(cx,cy,14,gold)
        for j in range(5):
            phase=(q*2+j*.17)%1;x=839+math.sin(phase*3+j)*54;y=175+phase*470
            p.poly([(x-93,y-67),(x+93,y-49),(x+76,y+90),(x-99,y+68)],['#324a60','#436377'][j%2])
            for row in range(3):
                for col in range(4):p.rect((x-66+col*34,y-20+row*26,x-51+col*34,y-7+row*26),gold if row==j%3 else '#8293a0',2)
    elif theme=='separation':
        distance=80+230*smooth_theme(q)
        for side in (-1,1):
            x=640+side*distance;p.ellipse((x-155,245,x+155,475),None,blue if side<0 else gold,30)
        if q<.48:
            p.line([(563,335),(718,386)],light,16)
        else:
            for j in range(18):
                a=j*2.4;x=640+math.cos(a)*(q-.48)*620;y=360+math.sin(a)*(q-.48)*450
                p.line([(x,y),(x+math.cos(a)*18,y+math.sin(a)*18)],gold,5)
    elif theme=='turning_point':
        opening=4+300*q
        p.rect((335,105,945,620),'#f5c974',8)
        p.rect((320-opening,95,640-opening,630),'#1d2b3b',7)
        p.rect((640+opening,95,960+opening,630),'#142536',7)
        p.poly([(640-opening,620),(640+opening,620),(960,710),(320,710)],'#705c3e')
        p.line([(335,620),(945,620)],light,5)
        for j in range(45):
            x=640+math.sin(j*2.1)*(38+q*500);y=(j*71-t*78)%720
            p.circle(x,y,1+j%4,light)
    elif theme=='fire':
        p.ellipse((373,578,912,660),'#562b25')
        for layer in range(4):
            size=(1-layer*.21)*(120+240*smooth_theme(q));points=[(640-size*.63,606)]
            for j in range(25):
                angle=math.pi*(1-j/24);x=640+math.cos(angle)*size*.68
                y=598-math.sin(angle)*(size*1.32+math.sin(j*.7+t*5)*40)
                points.append((x,y))
            points.append((640+size*.63,606));p.poly(points,['#9b3828','#df5b2f',gold,light][layer])
        for j in range(68):
            rise=(t*.28+j*.029)%1;x=640+math.sin(j*3.2+rise*6)*(70+rise*145);y=590-rise*530
            p.circle(x,y,(1-rise)*(2+j%4),gold if j%3 else light)
    elif theme=='resilience':
        p.poly([(366,512),(861,512),(848,557),(764,579),(762,632),(460,632),(458,579),(375,557)],'#718493')
        half=110+90*q;height=58-26*q
        p.rect((640-half,512-height,640+half,512),'#df7440',10)
        phase=t*2.7;hammer_y=315+125*(.5-.5*math.cos(phase)) if 0<q<1 else 290
        p.poly([(683,hammer_y-170),(711,hammer_y-167),(697,hammer_y+37),(669,hammer_y+31)],'#b18155')
        p.rect((603,hammer_y-25,775,hammer_y+38),'#a7bbc5',13)
        intensity=max(0,math.cos(phase)) if 0<q<1 else 0
        for j in range(35):
            a=math.pi*(j/34);distance=30+(t*170+j*33)%210
            x=645+math.cos(a)*distance;y=476-math.sin(a)*distance*intensity
            p.line([(x,y),(x+math.cos(a)*14,y-8)],gold,3)
        p.line([(640-half+10,518-height),(640+half-10,518-height)],light,4)
    elif theme=='pressure':
        gap=220-130*smooth_theme(min(1,q*1.5))+24*smooth_theme((q-.8)/.2);cx,cy=640,360
        p.rect((353,cy-gap-100,927,cy-gap),'#596d7d',15)
        p.rect((353,cy+gap,927,cy+gap+100),'#596d7d',15)
        transform=smooth_theme((q-.27)/.5);size=132
        color=blue if transform>.5 else '#3d4650'
        coal=[(cx-117,cy-27),(cx-90,cy-118),(cx+68,cy-96),(cx+124,cy+16),(cx+23,cy+116)]
        diamond=[(cx-size,cy-46),(cx-58,cy-size),(cx+58,cy-size),(cx+size,cy-46),(cx,cy+size)]
        points=[(a[0]+(b[0]-a[0])*transform,a[1]+(b[1]-a[1])*transform) for a,b in zip(coal,diamond)]
        p.poly(points,color)
        if transform>.25:
            for a,b in ((points[0],points[3]),(points[1],points[4]),(points[2],points[4])):p.line([a,b],light if transform>.5 else '#57636c',4)
        for j in range(16):
            if transform>.5:
                a=j*math.pi/8;r=160+transform*75
                p.line([(cx+math.cos(a)*r,cy+math.sin(a)*r),(cx+math.cos(a)*(r+15),cy+math.sin(a)*(r+15))],gold,3)
    elif theme=='inner_power':
        cx,cy=640,372;opening=smooth_theme(q)
        for j in range(24):
            a=j*math.pi/12;r=215+15*math.sin(t*2+j)
            p.poly([(cx+math.cos(a)*160,cy+math.sin(a)*160),(cx+math.cos(a-.1)*r,cy+math.sin(a-.1)*r),(cx+math.cos(a+.1)*r,cy+math.sin(a+.1)*r)],'#ad713d')
        p.poly([(501,233),(571,187),(709,187),(779,233),(749,455),(640,546),(531,455)],gold)
        for side in (-1,1):
            x=cx+side*66;p.ellipse((x-32,cy-38*opening,x+32,cy+8*opening),'#142536')
            p.circle(x,cy-11,6*opening,light)
        p.poly([(602,435),(678,435),(640,465)],'#513228')
        p.line([(640,466),(640,486),(612,504)],'#513228',6);p.line([(640,486),(668,504)],'#513228',6)
    elif theme=='strategy':
        for row in range(5):
            for col in range(8):
                x=250+col*97+row*27;y=203+row*66
                p.poly([(x,y),(x+94,y),(x+121,y+62),(x+27,y+62)],'#294255' if (row+col)%2 else '#a8b4ad')
        x=368+455*smooth_theme(q);y=424-142*smooth_theme((q-.45)/.5)
        p.ellipse((x-58,y+31,x+62,y+59),'#152738')
        p.poly([(x-47,y+33),(x+47,y+33),(x+25,y-47),(x-25,y-47)],gold)
        p.circle(x,y-67,35,light);p.rect((x-19,y-132,x+19,y-96),gold,4)
        p.rect((x-42,y-120,x+42,y-105),gold,4)
        for j in range(6):p.circle(383+j*77,466-j*24,5,blue)
    else:
        raise ValueError('Unregistered Python narrative concept')
    return p.finish()


def smooth_theme(value):
    value=max(0,min(1,value));return value*value*(3-2*value)
