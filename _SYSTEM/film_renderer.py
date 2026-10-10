"""Registered illustrated film shots. No models, captions, or downloaded footage.

This module is appended to the trusted object library at package creation.
Every family uses staged environments, shot changes, and a consistent actor.
"""

FILM_BACKGROUNDS = {}


class FilmPainter(Painter):
    def __init__(self, palette='day', camera=(640,360,1)):
        colors = {'day':('#e7dfce','#c5b9a2'), 'night':('#182b47','#101d33'),
                  'gym':('#c8d5d2','#91a9a7'), 'warm':('#d79b6d','#ad684f')}
        top,bottom = colors[palette]
        if palette not in FILM_BACKGROUNDS:
            base = Image.new('RGB',(2560,1440),top)
            d = ImageDraw.Draw(base)
            a = tuple(int(top[i:i+2],16) for i in (1,3,5))
            b = tuple(int(bottom[i:i+2],16) for i in (1,3,5))
            for row in range(0,1440,8):
                ratio = row/1440
                color = tuple(round(mix(v,w,ratio)) for v,w in zip(a,b))
                d.rectangle((0,row,2560,row+8),fill=color)
            FILM_BACKGROUNDS[palette] = base
        self.image = FILM_BACKGROUNDS[palette].copy()
        self.draw = ImageDraw.Draw(self.image)
        self.cx,self.cy,self.zoom = camera
        self.labels = []

    def point(self,x,y):
        return (round(2*(640+(x-self.cx)*self.zoom)),round(2*(360+(y-self.cy)*self.zoom)))

    def label(self,x,y,text,size=34,color=WHITE):
        # Text is drawn after supersampling at its projected screen position.
        px,py = self.point(x,y)
        actual=max(12,round(size*self.zoom))
        if actual*len(text)*.35 < px/2 < 1280-actual*len(text)*.35 and actual < py/2 < 720-actual:
            self.labels.append((px/2,py/2,text,actual,color))


def film_actor(p,x,y,s=1,pose='stand',phase=0,reach=None,facing=1):
    skin='#e8ad87'; shirt='#3e7193'; pants='#253e50'
    stride=math.sin(phase)*34*s if pose in ('walk','run') else 0
    lean=10*s if pose=='run' else 0
    p.ellipse((x-58*s,y-7*s,x+65*s,y+14*s),'#65757b')
    if pose=='meditate':
        p.line([(x,y-93*s),(x-65*s,y-45*s),(x+55*s,y-20*s)],pants,26*s)
        p.line([(x+10*s,y-93*s),(x+76*s,y-47*s),(x-52*s,y-15*s)],pants,26*s)
    elif pose=='sit':
        for side in (-1,1):
            knee=(x+facing*57*s,y-89*s+side*8*s)
            foot=(x+facing*66*s,y-9*s+side*6*s)
            p.line([(x+side*12*s,y-92*s),knee,foot],pants,23*s)
            p.line([foot,(foot[0]+facing*27*s,foot[1]+3*s)],'#182b36',15*s)
    else:
        for side in (-1,1):
            hip=(x+side*17*s,y-88*s)
            knee=(x+side*21*s+side*stride*.5,y-40*s)
            foot=(x+side*26*s+side*stride,y-10*s)
            p.line([hip,knee,foot],pants,23*s)
            p.line([foot,(foot[0]+facing*25*s,foot[1]+3*s)],'#182b36',16*s)
            p.line([(foot[0]+facing*8*s,foot[1]+9*s),(foot[0]+facing*29*s,foot[1]+9*s)],'#e8dcc9',3*s)
    p.poly([(x-34*s,y-169*s),(x+33*s+lean,y-167*s),(x+40*s,y-87*s),(x-32*s,y-86*s)],shirt)
    p.line([(x-29*s,y-90*s),(x+36*s,y-90*s)],'#2d526e',5*s)
    p.line([(x+4*s,y-151*s),(x+4*s,y-102*s)],'#548cad',2*s)
    p.rect((x-12*s+lean,y-186*s,x+13*s+lean,y-165*s),skin,5*s)
    hx=x+lean; hy=y-207*s
    p.ellipse((hx-31*s,hy-36*s,hx+31*s,hy+35*s),skin)
    p.poly([(hx-31*s,hy+1*s),(hx-34*s,hy-25*s),(hx-12*s,hy-43*s),
            (hx+24*s,hy-37*s),(hx+34*s,hy-13*s),(hx+8*s,hy-20*s),(hx-13*s,hy-8*s)],'#233546')
    p.poly([(hx+facing*24*s,hy),(hx+facing*41*s,hy+10*s),(hx+facing*24*s,hy+15*s)],skin)
    if pose=='meditate':p.line([(hx+facing*7*s,hy+4*s),(hx+facing*20*s,hy+5*s)],'#233546',3*s)
    else:p.circle(hx+facing*17*s,hy+3*s,2.5*s,'#233546')
    p.line([(hx+facing*13*s,hy+22*s),(hx+facing*23*s,hy+21*s)],'#aa6658',2*s)
    for side in (-1,1):
        shoulder=(x+side*28*s+lean*.5,y-151*s)
        target=(x+side*51*s,y-96*s)
        if pose in ('walk','run'):
            target=(x+side*47*s-side*stride*.7,y-109*s+side*stride*.45)
        if pose=='meditate':target=(x+side*67*s,y-42*s)
        if reach and side==facing:target=reach
        elbow=(mix(shoulder[0],target[0],.52)-side*9*s,mix(shoulder[1],target[1],.52)+12*s)
        p.line([shoulder,elbow],shirt,20*s)
        p.line([elbow,target],skin,15*s)
        p.circle(*target,9*s,skin)


def film_window(p,night=False):
    p.rect((65,98,440,402),'#324c61',9)
    p.rect((81,114,424,386),'#16263e' if night else '#98b8c7',3)
    for i in range(8):
        xx=90+i*44
        h=42+(i*37)%94
        p.rect((xx,384-h,xx+34,385),'#314964' if night else '#7e9cae')
        if night:
            for j in range(3):p.rect((xx+8,384-h+9+j*20,xx+13,384-h+15+j*20),'#c69d69')
    if night:
        p.circle(344,177,32,'#f5ddb2');p.circle(358,163,29,'#16263e')
        for i in range(10):p.circle(104+(i*79)%285,132+(i*41)%100,1.8,'#e9d8be')
    else:
        p.circle(339,175,35,'#f2d393')
        p.poly([(94,399),(330,399),(625,640),(135,640)],'#d9cba8')
    p.line([(252,112),(252,392)],'#324c61',10)
    p.line([(79,274),(426,274)],'#324c61',8)
    for xx in (47,436):
        p.rect((xx,80,xx+27,425),'#5c6976' if night else '#a58376',5)
    p.rect((49,78,474,95),'#465b69',4)


def film_room(p,night=False,kind='study'):
    p.poly([(-800,585),(2080,585),(2080,1000),(-800,1000)],'#1b2d43' if night else '#af9c86')
    p.line([(-800,585),(2080,585)],'#4d6173' if night else '#826b59',8)
    for yy in (625,700,815):p.line([(-800,yy),(2080,yy)],'#263b51' if night else '#9f8a74',2)
    for xx in range(-500,1800,180):p.line([(xx,585),(640+(xx-640)*1.9,1000)],'#263b51' if night else '#9f8a74',2)
    film_window(p,night)
    p.rect((1015,148,1168,344),'#647e83',8)
    p.rect((1030,162,1153,330),'#d9ccac',4)
    p.poly([(1042,303),(1085,202),(1104,262),(1137,228),(1141,305)],'#5c8984')
    p.rect((1060,445,1195,590),'#496268',5)
    for row in range(3):p.line([(1070,478+row*39),(1185,478+row*39)],'#284651',3)
    p.circle(1190,422,28,'#64866d');p.circle(1155,400,34,'#72997a');p.circle(1120,423,28,'#64866d')
    p.rect((1120,441,1188,486),'#ab715a',6)
    if kind=='bedroom':
        p.poly([(156,465),(635,428),(788,515),(290,569)],'#50687c')
        p.poly([(290,569),(788,515),(788,637),(290,666)],'#263e55')
        p.rect((174,371,211,592),'#6e8493',7)
        p.poly([(207,433),(617,408),(648,452),(250,483)],'#d3c6ae')
        p.poly([(344,475),(650,437),(758,514),(430,549)],'#637f8e')
        p.line([(430,549),(756,514)],'#93a6ad',7)
        p.poly([(811,432),(986,421),(1011,445),(832,458)],'#a9876b')
        p.poly([(832,458),(1011,445),(1011,585),(832,605)],'#755d50')
        p.rect((864,488,967,527),'#8d7160',4);p.line([(902,502),(926,500)],'#c5b299',4)
    elif kind=='study':
        p.rect((623,420,1000,446),'#a0785b',5)
        p.poly([(623,446),(1000,446),(1045,579),(1016,579),(977,455),(647,455),(640,581),(613,581)],'#465b60')
        p.line([(944,422),(944,291),(887,255)],'#344c57',10)
        p.poly([(846,257),(893,225),(934,268)],'#d0a267')
        if night:p.poly([(856,270),(924,270),(1001,420),(742,420)],'#686459')
        p.rect((801,310,879,411),'#415b70',7)
        p.rect((808,317,872,399),'#1e364e',4)
        p.line([(841,411),(841,423)],'#415b70',8)
        p.rect((488,408,522,561),'#786d63',8);p.rect((483,495,611,518),'#786d63',8)
        p.line([(500,517),(488,621)],'#3d525b',10);p.line([(594,517),(607,621)],'#3d525b',10)


def film_sleep(p,q):
    p.ellipse((262,422,335,469),'#e8ad87')
    p.poly([(262,444),(268,423),(298,412),(326,424),(328,435),(298,431),(276,446)],'#233546')
    p.line([(307,441),(320,444)],'#233546',3)
    p.poly([(336,443),(574,432),(669,490),(419,525)],'#7297a8')
    p.line([(423,513),(589,474)],'#a0b7bd',5)
    p.ellipse((340,452,422,469+3*math.sin(q*9)),'#e8ad87')


def film_gym(p,t):
    p.poly([(-500,566),(1800,566),(1800,900),(-500,900)],'#5a7379')
    p.line([(-500,566),(1800,566)],'#344c55',8)
    for xx in (50,470,890):
        p.rect((xx,96,xx+350,510),'#4f6b75',7)
        p.rect((xx+12,108,xx+338,496),'#a0b9bd',3)
        p.line([(xx+20,470),(xx+317,123)],'#c0d0d0',4)
    p.rect((55,468,334,487),'#2b414b',8)
    p.line([(85,488),(65,580)],'#344c55',14);p.line([(303,488),(325,580)],'#344c55',14)
    for j in range(3):dumbbell(p,103+j*85,416,.37)
    p.rect((1012,371,1041,594),'#344c55',10);p.rect((1188,371,1217,594),'#344c55',10)
    p.line([(1024,394),(1203,394)],'#344c55',14)
    p.rect((997,548,1236,574),'#263e46',12)


def film_cup(p,x,y,s=1,t=0):
    p.ellipse((x-66*s,y+58*s,x+84*s,y+84*s),'#8f7c69')
    p.ellipse((x+24*s,y-18*s,x+82*s,y+41*s),None,'#eee1c6',10*s)
    p.rect((x-49*s,y-30*s,x+49*s,y+63*s),'#ede0c6',18*s)
    p.ellipse((x-49*s,y-39*s,x+49*s,y-15*s),'#fcf2dc')
    p.ellipse((x-40*s,y-34*s,x+40*s,y-19*s),'#965e3c')
    for j in range(3):
        yy=y-60*s-((t*24+j*23)%65)*s
        p.line([(x+(j-1)*20*s,yy+21*s),(x+(j-1)*20*s+math.sin(t*2+j)*9*s,yy)],'#c5bfaf',3*s)


def film_calendar(p,q,comeback=False):
    p.rect((245,160,1035,590),'#74604d',12)
    p.rect((258,173,1022,572),'#f2e5ce',5)
    p.rect((258,173,1022,238),'#b96758',5)
    for j in range(7):
        x=327+j*100
        for row in range(3):
            y=300+row*100
            p.rect((x-36,y-33,x+36,y+33),'#ddd2ba',4)
            if row==0 or (row==1 and j<2):check(p,x,y,.58,'#547f71')
    p.line([(506,387),(548,418)],'#b65d58',6)
    p.line([(548,387),(506,418)],'#b65d58',6)
    k=progress(q,.32,.8)
    x=mix(980,627,k); y=mix(635,410,k)
    hand(p,x,y,.85)
    if q>.7:check(p,627,400,progress(q,.7,.9),'#547f71')
    # Paper curl creates a visible time advance instead of a text-only card.
    fold=progress(q,.83,1)*92
    if comeback:p.poly([(1022,572),(1022-fold,572),(1022,572-fold)],'#c5b38f')


def film_camera(family,q):
    if family=='night_plan':
        if q>.56:return (mix(730,746,q),257,1.54+.1*q)
        return (mix(610,660,q),mix(355,369,q),mix(1,1.14,q))
    if family=='snooze':return (920+6*math.sin(q*16),398,1.93+.13*q)
    if family in ('two_lines','big_goal'):return (743+18*q,389,1.56+.15*q)
    if family=='desk_setup':return (mix(720,785,q),mix(372,391,q),1.05+.32*q)
    if family=='phone_away':return (mix(550,787,q),363,1.01+.07*q)
    if family=='treadmill':return (mix(652,688,q),373,1.03+.18*q)
    if family=='gym' and q>.52:return (686,399,1.55+.1*q)
    if family in ('small_start','environment') and q>.57:return (701,402,1.46+.1*q)
    if family=='tea_stack' and q<.27:return (734,354,1.7)
    if family=='identity' and q>.57:return (786,336,1.51+.1*q)
    if family in ('brain_resist','resistance','energy','choice_battery') and q>.48:return (878,318,1.72+.16*q)
    if family=='momentum':return (mix(530,807,q),488,1.48)
    if family=='convenience' and q>.53:return (798,416,1.4+.15*q)
    if family=='fixed_anchor' and q>.52:return (809,318,1.45+.12*q)
    if family in ('calendar','comeback'):return (640+14*q,367,1+.1*q)
    if family=='identity':return (mix(661,703,q),354,1.06+.12*q)
    return (640+24*(q-.5),360+7*math.sin(q*math.pi),1.025+.055*q)


def render_film(t,ctx):
    family=ctx.scene_id.split('__')[0]
    duration=max(.001,ctx.scene_end-ctx.scene_start)
    q=max(0,min(1,t/duration))
    palette='night' if family in ('night_plan','desk_setup') else 'gym' if family in ('gym','treadmill','bundle') else 'warm' if family in ('brain_resist','resistance','energy','choice_battery','first_push','momentum','reward') else 'day'
    p=FilmPainter(palette,film_camera(family,q))
    p.ctx=ctx;p.time=t
    if family in ('night_plan','snooze'):
        film_room(p,family=='night_plan','bedroom');film_sleep(p,q)
        clock(p,922,388,34,hour=5,ring=t if family=='snooze' and q<.58 else 0)
        if family=='night_plan':
            # Motivated cut from the room to the imagined morning preparation.
            if q>.44:
                p.rect((548,114,929,290),'#e8d9bd',24)
                p.circle(547,329,12,'#e8d9bd');p.circle(572,306,18,'#e8d9bd')
                dumbbell(p,650,208,.54);book(p,823,210,.46,progress(q,.55,.9))
                p.label(738,145,'TOMORROW',19,'#405368')
            p.label(920,388,'05:00',13,'#b85e58')
        else:
            reach=progress(q,.05,.56)
            hand(p,mix(1090,921,reach),mix(581,450,reach),.58)
            if q>.58:p.rect((915,378,930,383),'#b65e58',3)
    elif family in ('small_start','big_goal','two_lines','desk_setup','environment','share_start'):
        film_room(p,family=='desk_setup','study')
        if family=='big_goal':
            for i in range(5):p.rect((654,416-i*21,807,432-i*21),['#3e7193','#b96c59','#82956a'][i%3],4)
            clock(p,916,336,58,hour=1)
            if q>.45:
                k=progress(q,.45,.8)
                p.line([(872,290),(872+86*k,290+86*k)],'#b65e58',8)
                p.line([(958,290),(958-86*k,290+86*k)],'#b65e58',8)
        elif family=='two_lines':
            book(p,749,407,.79,1)
            k=progress(q,.08,.84)
            for i in range(2):
                yy=376+i*21
                p.line([(658,yy),(658+68*progress(k,i*.42,i*.42+.35),yy+4)],'#d0ab50',8)
            hand(p,mix(681,740,k),mix(416,437,k),.45)
        elif family=='environment':
            phone(p,mix(745,1240,progress(q,.03,.48)),365,.43)
            book(p,mix(1110,729,progress(q,.4,.85)),384,.46,progress(q,.7,1))
            film_actor(p,553,611,1.18,'sit',reach=(697,416))
        elif family=='small_start':
            for i in range(5):
                xx=mix(750,1300,progress(q,.04,.49))
                p.rect((xx-71,411-i*22,xx+71,429-i*22),['#3e7193','#b96c59','#82956a'][i%3],4)
            book(p,747,396,.48,progress(q,.4,.8))
            film_actor(p,552,611,1.22,'sit',reach=(mix(605,693,progress(q,.4,.8)),417))
        else:
            book(p,mix(948,734,progress(q,.02,.52)),390,.5,progress(q,.5,.9))
            film_actor(p,554,612,1.25,'sit',reach=(700,421))
            if family=='share_start':
                x=mix(658,1310,progress(q,.22,1));y=370-175*math.sin(q*1.7)
                p.poly([(x-50,y+17),(x+55,y-21),(x-12,y+39),(x-13,y+10)],'#f4e4c5')
    elif family in ('gym','treadmill','bundle'):
        film_gym(p,t)
        if family=='gym':
            lift=(1-math.cos(t*3.2))*.5
            hx=695;hy=461-lift*130
            film_actor(p,633,614,1.68,reach=(hx,hy))
            dumbbell(p,hx,hy,.62)
            clock(p,1111,226,52,hour=6)
        else:
            p.poly([(418,587),(843,587),(901,637),(359,637)],'#243e48')
            p.rect((379,581,850,608),'#253f48',16)
            for i in range(11):
                x=395+((i*41-t*120)%431)
                p.line([(x,590),(x+18,590)],'#9dbbb8',4)
            p.line([(809,587),(823,398),(772,385)],'#365863',16)
            p.rect((721,340,818,391),'#263f4d',8)
            p.rect((736,352,798,378),'#80b4ba',3)
            film_actor(p,629,590,1.52,'run',t*8)
            hx=639;hy=590-207*1.52
            p.line([(hx-36,hy+4),(hx-37,hy-38),(hx+27,hy-48),(hx+50,hy-7)],'#dcb46d',10)
            p.rect((hx-45,hy-7,hx-27,hy+28),'#263d4a',5);p.rect((hx+37,hy-9,hx+53,hy+24),'#263d4a',5)
            for j in range(5):
                h=16+abs(math.sin(t*4+j))*41
                p.rect((1024+j*24,421-h,1035+j*24,421),'#407479',4)
    elif family=='phone_away':
        film_room(p,False,'study')
        p.rect((905,110,1175,651),'#695d53',8)
        p.rect((920,128,1161,643),'#304351',4)
        slide=progress(q,.03,.63)
        film_actor(p,mix(563,1003,slide),623,1.48,'walk',t*6,reach=(mix(641,1049,slide),420))
        phone(p,mix(641,1049,slide),406,.31)
        close=progress(q,.64,.92)
        p.rect((922,128,922+237*close,643),'#958069',3)
        if close>.12:p.circle(922+216*close,361,7,'#d5b573')
        book(p,716,401,.36,1)
    elif family in ('tea_stack','fixed_anchor','negotiation','fork'):
        film_room(p,False,'study')
        if family=='tea_stack':
            film_cup(p,726,367,.68,t)
            k=progress(q,.2,.7)
            p.ellipse((414,598,861,659),'#718c82')
            if q<.27:film_actor(p,554,617,1.4,'sit',reach=(706,389))
            else:film_actor(p,mix(531,640,k),620,1.45,'meditate',t)
        elif family=='fixed_anchor':
            film_actor(p,554,614,1.27,'sit',reach=(695,418));book(p,739,391,.46,1)
            clock(p,908,196,57,hour=6)
            k=progress(q,.18,.8)
            p.line([(907,263),(907,299),(753,299),(753,341)],'#4f8275',5)
            check(p,907,296,.7*k,'#4f8275')
        else:
            clock(p,723,380,46,hour=6)
            film_actor(p,539+math.sin(t*2)*15,615,1.5,reach=(590,373+math.sin(t*3)*12))
            phone(p,815,392,.34)
            book(p,686,391,.37,progress(q,.55,.95))
            p.line([(589,366),(661,355)],'#a47555',4)
    elif family in ('calendar','comeback'):
        p.rect((-100,72,1400,670),'#c7bda4',12)
        for xx in range(30,1400,110):p.line([(xx,72),(xx,670)],'#b5a98f',2)
        film_calendar(p,q,family=='comeback')
    elif family=='identity':
        film_room(p,False,'study')
        p.rect((744,83,1039,561),'#6c6557',20)
        p.rect((759,98,1024,546),'#a2b9b8',13)
        p.poly([(768,111),(896,111),(775,533)],'#b8ccca')
        k=progress(q,.12,.85)
        film_actor(p,892,529,1.4,reach=(mix(834,803,k),mix(397,354,k)),facing=-1)
        film_actor(p,629,623,1.68,reach=(mix(713,790,k),mix(481,348,k)))
        for j in range(3):
            if q>j*.23+.18:check(p,1111,281+j*83,.74*progress(q,j*.23+.18,j*.23+.38),'#548478')
    elif family=='convenience':
        film_room(p,False,'bedroom')
        p.rect((402,449,794,574),'#bb8771',26);p.rect((379,467,417,606),'#a66d59',17);p.rect((778,466,815,606),'#a66d59',17)
        film_actor(p,572,591,1.42,'sit',reach=(659,407))
        phone(p,663,381,.44)
        # The phone interaction reveals an actual tray and a television in room.
        k=progress(q,.19,.62)
        p.rect((927,245,1190,415),'#273f4e',12)
        p.rect((939,257,1178,401),'#516e80',5)
        if k>.05:
            p.poly([(1037,304),(1037,363),(1084,333)],'#e2bd77')
            p.rect((765,563,919,578),'#705749',7)
            p.circle(847,547,43*k,'#ddb55b')
            p.line([(817,552),(881,552)],'#5a8870',6)
    elif family in ('brain_resist','resistance','energy','choice_battery'):
        # An inset mind metaphor is attached to an actor, rather than an icon stage.
        p.poly([(-200,581),(1480,581),(1480,900),(-200,900)],'#795b50')
        for i in range(6):p.line([(100+i*196,581),(20+i*220,760)],'#986e57',2)
        target=527+progress(q,.1,.9)*55
        if q<=.48:film_actor(p,363-12*math.sin(t*2),637,1.98,reach=(target,483))
        p.rect((669,146,1140,475),'#e4c7a4',32)
        p.circle(616,379,17,'#e4c7a4');p.circle(650,348,24,'#e4c7a4')
        brain(p,842,294,.79,.1)
        if family=='choice_battery':
            battery(p,965,418,1-progress(q,.04,.97),.54)
            for i in range(3):
                angle=t*.6+i*2.094
                x=847+math.cos(angle)*162;y=286+math.sin(angle)*93
                if i==0:book(p,x,y,.22,.7)
                elif i==1:phone(p,x,y,.2)
                else:dumbbell(p,x,y,.24)
        elif family=='energy':
            battery(p,971,410,1-progress(q,.1,.9)*.7,.58)
            if q<=.48:
                p.rect((826,554,1088,606),'#5a736c',19)
                p.rect((797,530,830,633),'#5a736c',15);p.rect((1083,530,1115,633),'#5a736c',15)
                arrow(p,(586,566),(750,566),'#e1bb74',7)
        else:
            if q<=.48:
                dumbbell(p,target,483,.51)
                p.line([(567,482),(625,460+math.sin(t*3)*21),(695,477)],'#b26153',8)
            if family=='resistance':
                p.line([(705,208),(1049,208)],'#bf8570',5)
                p.line([(705,208),(705+312*progress(q,0,1),208)],'#914d45',8)
    elif family in ('first_push','momentum','reward'):
        p.poly([(-500,585),(1900,585),(1900,1000),(-500,1000)],'#846554')
        for i in range(8):p.line([(30+i*180,585),(-140+i*220,900)],'#a17b61',2)
        if family=='first_push':
            travel=progress(q,.15,.98)*296
            x=730+travel
            p.circle(x,486,95,'#3a6475');p.circle(x,486,63,'#bfc9bc')
            for i in range(6):
                a=t*1.7+i*math.pi/3
                p.line([(x,486),(x+math.cos(a)*72,486+math.sin(a)*72)],'#3a6475',7)
            film_actor(p,533+travel,619,1.62,'walk',t*4,reach=(x-92,459))
        elif family=='momentum':
            for i in range(9):
                angle=progress(q,.05+i*.073,.24+i*.073)*1.27
                x=211+i*107;y=588
                p.poly([(x,y),(x+23,y),(x+23+math.sin(angle)*148,y-math.cos(angle)*148),
                        (x+math.sin(angle)*148,y-math.cos(angle)*148)],['#3a6475','#e1c393','#bd735d'][i%3])
                for j in (-1,1):
                    distance=75+j*23
                    p.circle(x+11*math.cos(angle)+math.sin(angle)*distance,y-11*math.sin(angle)-math.cos(angle)*distance,4,'#ede1c7')
            hand(p,mix(146,208,progress(q,0,.2)),414,.65)
        else:
            p.poly([(710,585),(710,494),(824,494),(824,399),(938,399),(938,301),(1052,301),(1052,585)],'#af8867')
            walk=progress(q,.02,.63)
            x=mix(380,546,walk)
            lift=progress(q,.63,.98)
            hand_target=(x+105,mix(435,333,lift))
            film_actor(p,x,620,1.69,'walk' if q<.63 else 'stand',t*6,reach=hand_target)
            star(p,1044,237,41,'#e6c27c')
            reward_x=638 if q<.63 else hand_target[0]
            reward_y=435 if q<.63 else hand_target[1]
            star(p,reward_x,reward_y,35+3*math.sin(t*3),'#e6c27c')
    else:
        # Registered fallback preserves an environment, never a narration slide.
        film_room(p,False,'study');film_actor(p,557,617,1.5,'sit',reach=(710,423));book(p,746,387,.5,progress(q,.1,.8))
    image=p.finish()
    # Brief motivated exposure transition; no long static title card.
    if q<.045:
        image=Image.blend(Image.new('RGB',image.size,'#152737'),image,.75+.25*progress(q,0,.045))
    return image
