"""Registered local illustration library: physical object actions, no narration captions."""
import math
from PIL import Image, ImageDraw
from motion_sdk import font

NAVY = '#0c1428'
INK = '#23314b'
WHITE = '#f2eee5'
GOLD = '#ffd16a'
CORAL = '#ff8187'
TEAL = '#68ded1'
MUTED = '#8194b3'


def progress(t, a, b):
    x = max(0.0, min(1.0, (t-a)/max(.001,b-a)))
    return x*x*(3-2*x)


def mix(a,b,x):
    return a+(b-a)*x


class Painter:
    def __init__(self, framing='wide'):
        self.image = Image.new('RGB',(2560,1440),NAVY)
        self.draw = ImageDraw.Draw(self.image)
        self.zoom = .96 if framing == 'wide' else 1.04
        self.labels = []
        self.ellipse((210,82,1120,672),'#111e35')
        self.ellipse((195,594,1100,694),'#080f20')
        self.line([(60,625),(1220,625)],'#28384f',2)

    def point(self,x,y):
        return (round(2*(640+(x-640)*self.zoom)),round(2*(360+(y-360)*self.zoom)))

    def box(self,b):
        a=self.point(b[0],b[1]);c=self.point(b[2],b[3])
        return (min(a[0],c[0]),min(a[1],c[1]),max(a[0],c[0]),max(a[1],c[1]))

    def rect(self,b,color,r=0,outline=None,w=1):
        self.draw.rounded_rectangle(self.box(b),radius=round(r*2*self.zoom),fill=color,
                                    outline=outline,width=max(1,round(w*2*self.zoom)))

    def ellipse(self,b,color,outline=None,w=1):
        self.draw.ellipse(self.box(b),fill=color,outline=outline,width=max(1,round(w*2*self.zoom)))

    def circle(self,x,y,r,color,outline=None,w=1):
        self.ellipse((x-r,y-r,x+r,y+r),color,outline,w)

    def line(self,points,color,w=4):
        self.draw.line([self.point(x,y) for x,y in points],fill=color,width=max(1,round(w*2*self.zoom)),joint='curve')

    def poly(self,points,color,outline=None):
        self.draw.polygon([self.point(x,y) for x,y in points],fill=color,outline=outline)

    def label(self,x,y,text,size=34,color=WHITE):
        self.labels.append((x,y,text,size,color))

    def finish(self):
        image=self.image.resize((1280,720),Image.Resampling.LANCZOS)
        draw=ImageDraw.Draw(image)
        for x,y,text,size,color in self.labels:
            draw.text((x,y),text,font=font(size),fill=color,anchor='mm')
        return image


def arrow(p,a,b,color=TEAL,w=8):
    p.line([a,b],color,w)
    angle=math.atan2(b[1]-a[1],b[0]-a[0]);r=22
    p.poly([b,(b[0]-r*math.cos(angle-.5),b[1]-r*math.sin(angle-.5)),
               (b[0]-r*math.cos(angle+.5),b[1]-r*math.sin(angle+.5))],color)


def check(p,x,y,s=1,color=TEAL):
    p.line([(x-18*s,y),(x-3*s,y+14*s),(x+27*s,y-22*s)],color,max(3,7*s))


def person(p,x,y,s=1,pose='stand',phase=0,reach=None,color=CORAL):
    # y is the floor. Character is a consistent illustrated subject throughout.
    head_y=y-188*s
    p.ellipse((x-68*s,y-12*s,x+68*s,y+15*s),'#090e1d')
    if pose=='sit':
        p.line([(x-16*s,y-90*s),(x-52*s,y-54*s),(x-60*s,y-12*s)],INK,23*s)
        p.line([(x+18*s,y-90*s),(x+72*s,y-62*s),(x+80*s,y-12*s)],INK,23*s)
    elif pose=='meditate':
        p.line([(x-17*s,y-67*s),(x-82*s,y-25*s),(x+69*s,y-25*s)],INK,26*s)
        p.line([(x+17*s,y-67*s),(x+82*s,y-25*s),(x-69*s,y-25*s)],INK,26*s)
    else:
        swing=math.sin(phase)*28*s if pose in ('walk','run') else 0
        p.line([(x-18*s,y-90*s),(x-25*s+swing,y-40*s),(x-32*s+swing,y-9*s)],INK,25*s)
        p.line([(x+18*s,y-90*s),(x+25*s-swing,y-40*s),(x+32*s-swing,y-9*s)],INK,25*s)
    p.rect((x-42*s,y-163*s,x+42*s,y-78*s),color,21*s)
    p.rect((x-27*s,y-180*s,x+27*s,y-156*s),'#f0b996',10*s)
    p.circle(x,head_y,43*s,'#ffceac')
    p.poly([(x-42*s,head_y-8*s),(x-37*s,head_y-42*s),(x+9*s,head_y-48*s),
            (x+38*s,head_y-27*s),(x+39*s,head_y-5*s),(x+16*s,head_y-21*s),(x-8*s,head_y-12*s)],INK)
    if pose=='meditate':
        p.line([(x-21*s,head_y+8*s),(x-9*s,head_y+10*s)],INK,3*s)
        p.line([(x+10*s,head_y+10*s),(x+22*s,head_y+8*s)],INK,3*s)
    else:
        p.circle(x-14*s,head_y+9*s,3*s,INK);p.circle(x+16*s,head_y+9*s,3*s,INK)
    p.line([(x-5*s,head_y+28*s),(x+11*s,head_y+28*s)],'#b36658',3*s)
    left=(x-62*s,y-93*s)
    right=(x+62*s,y-93*s)
    if pose=='run':
        left=(x-65*s,y-128*s-math.sin(phase)*20*s)
        right=(x+65*s,y-128*s+math.sin(phase)*20*s)
    if pose=='meditate':
        left=(x-71*s,y-34*s);right=(x+71*s,y-34*s)
    if reach:
        right=reach
    p.line([(x-35*s,y-146*s),left],color,22*s)
    p.line([(x+35*s,y-146*s),right],color,22*s)
    p.circle(*left,12*s,'#ffceac');p.circle(*right,12*s,'#ffceac')


def hand(p,x,y,s=1):
    p.rect((x-20*s,y-12*s,x+24*s,y+72*s),'#ffceac',17*s)
    p.rect((x-10*s,y-58*s,x+6*s,y+12*s),'#ffceac',8*s)
    p.rect((x+9*s,y-33*s,x+24*s,y+15*s),'#f6ba98',7*s)
    p.rect((x+25*s,y-21*s,x+39*s,y+20*s),'#edb08d',7*s)
    p.rect((x-34*s,y+18*s,x-7*s,y+50*s),'#ffceac',10*s)
    p.rect((x-24*s,y+54*s,x+30*s,y+89*s),CORAL,8*s)


def phone(p,x,y,s=1,angle=0):
    p.ellipse((x-57*s,y+112*s,x+73*s,y+136*s),'#070d19')
    p.rect((x-59*s,y-118*s,x+59*s,y+118*s),INK,19*s,TEAL,3*s)
    p.rect((x-49*s,y-104*s,x+49*s,y+103*s),'#29415b',13*s)
    p.rect((x-20*s,y-103*s,x+20*s,y-94*s),'#111a2e',5*s)
    for row in range(3):
        for col in range(2):
            p.rect((x-32*s+col*36*s,y-65*s+row*41*s,x-7*s+col*36*s,y-41*s+row*41*s),
                   [TEAL,GOLD,CORAL][(row+col)%3],6*s)
    p.rect((x-18*s,y+90*s,x+18*s,y+94*s),WHITE,2*s)


def book(p,x,y,s=1,opening=0,color=CORAL):
    spread=max(0,min(1,opening));left=24+118*spread
    p.ellipse((x-155*s,y+93*s,x+155*s,y+119*s),'#080d1a')
    if spread < .06:
        p.rect((x-72*s,y-104*s,x+73*s,y+90*s),color,8*s)
        p.rect((x-59*s,y-94*s,x-47*s,y+83*s),'#d96276',3*s)
        p.rect((x-28*s,y-63*s,x+37*s,y-39*s),GOLD,3*s)
        p.line([(x-25*s,y-8*s),(x+39*s,y-8*s)],WHITE,4*s)
    else:
        p.poly([(x-left*s,y-78*s),(x,y-108*s),(x,y+89*s),(x-left*s,y+105*s)],color)
        p.poly([(x,y-108*s),(x+left*s,y-78*s),(x+left*s,y+105*s),(x,y+89*s)],color)
        p.poly([(x-(left-8)*s,y-70*s),(x-5*s,y-96*s),(x-5*s,y+77*s),(x-(left-8)*s,y+92*s)],WHITE)
        p.poly([(x+5*s,y-96*s),(x+(left-8)*s,y-70*s),(x+(left-8)*s,y+92*s),(x+5*s,y+77*s)],'#ddd8c6')
        p.line([(x,y-100*s),(x,y+86*s)],'#9b8c7d',3*s)
        for row in range(5):
            yy=y-44*s+row*26*s
            for side in (-1,1):
                p.line([(x+side*17*s,yy-8*s),(x+side*(left-23)*s,yy+8*s)],'#aaa89a',3*s)


def clock(p,x,y,r=85,hour=5,minute=0,ring=0,label=None):
    wobble=math.sin(ring*24)*4 if ring else 0
    x+=wobble
    p.circle(x,y,r+10,INK);p.circle(x,y,r,WHITE)
    for i in range(12):
        a=i*math.pi/6
        p.line([(x+math.sin(a)*r*.79,y-math.cos(a)*r*.79),(x+math.sin(a)*r*.91,y-math.cos(a)*r*.91)],MUTED,3)
    for a,length,width in [((hour+minute/60)*math.pi/6,.49,7),(minute*math.pi/30,.7,4)]:
        p.line([(x,y),(x+math.sin(a)*r*length,y-math.cos(a)*r*length)],INK,width)
    p.circle(x,y,7,CORAL)
    if ring:
        for side in (-1,1):
            p.line([(x+side*(r+25),y-32),(x+side*(r+45+8*math.sin(ring*24)),y-56)],GOLD,5)
    if label:p.label(x,y+r+38,label,26,TEAL)


def desk(p,light=False):
    p.rect((200,442,1100,470),'#b59478',10)
    p.rect((238,468,267,625),INK,5);p.rect((1025,468,1054,625),INK,5)
    if light:
        p.line([(975,441),(975,281),(923,242)],TEAL,12)
        p.poly([(880,245),(940,210),(985,264)],GOLD)
        p.poly([(892,266),(966,266),(1040,439),(790,439)],'#303345')


def brain(p,x,y,s=1,pressure=0):
    for dx,dy,rr in [(-45,-14,44),(0,-37,52),(46,-16,43),(-48,32,44),(5,26,57),(53,29,42)]:
        p.circle(x+dx*s,y+dy*s,rr*s,CORAL)
    for side in (-1,1):
        p.line([(x+side*12*s,y-56*s),(x+side*34*s,y-35*s),(x+side*16*s,y-12*s),
                (x+side*47*s,y+15*s),(x+side*25*s,y+45*s)],'#bc516d',5*s)
    p.line([(x,y-62*s),(x,y+61*s)],'#b74e65',4*s)
    p.circle(x-25*s,y+20*s,5*s,INK);p.circle(x+25*s,y+20*s,5*s,INK)
    p.line([(x-13*s,y+46*s),(x+13*s,y+46*s)],INK,5*s)
    p.line([(x-62*s,y+60*s),(x-80*s-pressure*30*s,y+115*s)],CORAL,12*s)
    p.line([(x+62*s,y+60*s),(x+80*s+pressure*30*s,y+115*s)],CORAL,12*s)


def dumbbell(p,x,y,s=1):
    p.rect((x-81*s,y-8*s,x+81*s,y+8*s),WHITE,6*s)
    for side in (-1,1):
        p.rect((x+side*55*s-12*s,y-41*s,x+side*55*s+12*s,y+41*s),TEAL,7*s)
        p.rect((x+side*77*s-9*s,y-31*s,x+side*77*s+9*s,y+31*s),INK,5*s)


def battery(p,x,y,level=1,s=1):
    p.rect((x-96*s,y-51*s,x+96*s,y+51*s),INK,13*s,WHITE,4*s)
    p.rect((x+98*s,y-18*s,x+112*s,y+18*s),WHITE,3*s)
    for i in range(4):
        active=level*4>i+.25
        p.rect((x-78*s+i*42*s,y-33*s,x-45*s+i*42*s,y+33*s),TEAL if active else '#394254',5*s)


def calendar(p,x,y,t,mode='return'):
    p.rect((x-247,y-144,x+247,y+155),WHITE,18)
    p.rect((x-247,y-144,x+247,y-80),CORAL,16)
    for bx in (-155,155):p.rect((x+bx-9,y-162,x+bx+9,y-117),INK,8)
    for i in range(7):
        xx=x-192+i*64
        p.rect((xx-22,y-30,xx+22,y+28),'#ddd9cf',7)
        if i<3:check(p,xx,y, .54,'#499e92')
    phase=progress(t,.15,.72)
    p.line([(x-14,y-15),(x+14,y+13)],CORAL,6)
    p.line([(x+14,y-15),(x-14,y+13)],CORAL,6)
    if phase>0:
        check(p,x+64,y,.65*phase,TEAL)
    p.rect((x-14,y+82,x+205*phase,y+90),TEAL,4)


def dominoes(p,t,duration,start=330,y=530,count=7):
    for i in range(count):
        x=start+i*83
        a=progress(t,i*duration*.09,duration*(.27+i*.09))*1.28
        h=126;w=34
        points=[(x,y),(x+w*math.cos(a),y-w*math.sin(a)),
                (x+w*math.cos(a)+h*math.sin(a),y-w*math.sin(a)-h*math.cos(a)),
                (x+h*math.sin(a),y-h*math.cos(a))]
        p.poly(points,TEAL if i%2 else GOLD,INK)
        px=x+h*.53*math.sin(a)+w*.5*math.cos(a)
        py=y-h*.53*math.cos(a)-w*.5*math.sin(a)
        p.circle(px,py,4,INK)


def star(p,x,y,r,color=GOLD):
    p.poly([(x+math.sin(i*math.pi/5)*(r if i%2==0 else r*.45),
             y-math.cos(i*math.pi/5)*(r if i%2==0 else r*.45)) for i in range(10)],color)


def render(t,ctx):
    # Registered functions never invent a claim or execute model-written code.
    family=ctx.scene_id.split('__')[0]
    framing='close' if ctx.scene_id.endswith('__close') else 'wide'
    p=Painter(framing)
    duration=ctx.scene_end-ctx.scene_start
    q=t/max(.001,duration)
    if family=='night_plan':
        p.circle(1000,150,45,GOLD);p.circle(1020,137,39,'#111e35')
        p.rect((215,460,650,590),TEAL,28);p.rect((215,552,244,625),INK,5);p.rect((615,552,642,625),INK,5)
        p.ellipse((215,403,325,475),WHITE)
        p.ellipse((243,417,305,463),'#ffceac')
        p.rect((304,410,637,481),CORAL,22)
        rise=progress(q,.0,.8)
        clock(p,850,318,88,5,0,label='05:00')
        dumbbell(p,1060,410-95*rise,.8)
        book(p,1045,566-26*rise,.48,progress(q,.35,.8))
        p.circle(665,380,13*rise,WHITE);p.circle(708,338,20*rise,WHITE)
        p.label(436,155,'TOMORROW',35,WHITE)
    elif family=='snooze':
        clock(p,710,314,116,5,0,ring=t if q<.65 else 0)
        p.rect((569,472,852,520),CORAL,22)
        p.label(709,496,'SNOOZE',25,NAVY)
        hx=mix(1030,713,progress(q,.06,.64));hy=mix(600,560,progress(q,.20,.64))
        hand(p,hx,hy,1.1)
        if q>.65:p.line([(672,470),(744,470)],GOLD,8)
        p.label(710,145,'05:00',35,WHITE)
    elif family=='brain_resist':
        x=mix(900,720,progress(q,.10,.8))
        person(p,335,565,1.4,reach=(525,390))
        brain(p,x,350,1.35,progress(q,.3,.8))
        dumbbell(p,mix(515,605,progress(q,.2,.8)),492,.8)
        p.label(640,135,'FRICTION',36,WHITE)
        p.line([(505,394),(x-95,409)],GOLD,12)
    elif family=='resistance':
        shift=progress(q,.1,.9)
        person(p,350-36*shift,580,1.5,reach=(580,374))
        brain(p,910+50*shift,344,1.5,shift)
        p.line([(580,375),(760+50*shift,440)],GOLD,17)
        p.line([(616,385),(670,399)],'#e4a255',4)
        for i in range(3):p.line([(652+i*28,339),(668+i*28,318)],CORAL,4)
    elif family=='energy':
        brain(p,381,325,1.5)
        battery(p,785,235,1-.6*progress(q,.0,.42),1.15)
        p.line([(583,560),(781,455),(981,560)],'#415170',22)
        for i in range(4):p.rect((720+i*42,518-i*24,759+i*42,545-i*24),INK,4)
        x=mix(604,1017,progress(q,.26,.92))
        person(p,x,585,.8,'walk',t*6)
        p.rect((1020,467,1165,563),TEAL,20);p.rect((1045,551,1070,621),INK,6)
        p.label(790,134,'SAVE ENERGY',33,WHITE)
    elif family=='convenience':
        phone(p,690,363,1.5)
        hand(p,mix(1000,744,progress(q,.05,.42)),mix(480,389,progress(q,.05,.42)),.8)
        pop=progress(q,.38,.86)
        x=330-50*pop
        p.circle(x,346,65*pop,GOLD)
        p.poly([(x-37*pop,304),(x+45*pop,326),(x-12*pop,397)],CORAL)
        p.circle(x-6,337,9*pop,WHITE)
        p.rect((912,306,1085,424),TEAL,22)
        p.poly([(971,335),(1014,365),(971,395)],NAVY)
        arrow(p,(554,370),(405,360),GOLD,5)
    elif family in ('small_start','big_goal'):
        if family=='small_start':
            for i in range(5):
                removed=progress(q,i*.065,.45+i*.065)
                x=mix(695,1310+i*70,removed)
                p.rect((x-220,487-i*51,x+220,525-i*51),[CORAL,TEAL,GOLD][i%3],8)
                p.line([(x-166,500-i*51),(x+176,500-i*51)],WHITE,3)
            book(p,535,431,.78,progress(q,.52,.95))
            person(p,294,582,.92,reach=(435,447))
            p.label(645,125,'START SMALL',36,WHITE)
        else:
            # The oversized target physically grows before being rejected.
            clock(p,760,337,mix(75,182,progress(q,.02,.91)),1,0,label='60 MIN')
            for i in range(4):p.rect((276,532-i*51,496,567-i*51),[CORAL,GOLD,TEAL][i%3],7)
            cross=progress(q,.2,.84)
            p.line([(629,216),(629+266*cross,216+250*cross)],CORAL,13)
            p.line([(895,216),(895-266*cross,216+250*cross)],CORAL,13)
    elif family=='two_lines':
        op=progress(q,0,.48)
        book(p,640,375,1.75,op)
        a=progress(q,.48,.71);b=progress(q,.71,.96)
        if a:p.line([(419,299),(419+170*a,325)],TEAL,12)
        if b:p.line([(419,345),(419+170*b,371)],TEAL,12)
        hand(p,mix(1010,455+145*b,progress(q,.44,.58)),461,.75)
        p.label(640,145,'2 LINES',37,WHITE)
    elif family=='first_push':
        start=progress(q,.04,.6)
        x=mix(632,777,start)
        p.circle(x,445,100,TEAL);p.circle(x,445,78,'#163c4b')
        person(p,377+154*start,574,1.35,reach=(x-96,434))
        p.line([(279,595),(1050,595)],WHITE,6)
        arrow(p,(890,442),(1060,442),GOLD,8)
        p.label(640,140,'BEGIN',38,WHITE)
    elif family=='momentum':
        dominoes(p,t,duration)
        hand(p,330-65*progress(q,.06,.39),362,.8)
        p.label(640,160,'MOMENTUM',36,WHITE)
    elif family in ('negotiation','fork'):
        p.circle(640,185,50,GOLD)
        p.line([(637,590),(637,458),(375,335)],TEAL,15)
        p.line([(637,458),(910,335)],CORAL,15)
        px=640+55*math.sin(q*math.pi*3)
        person(p,px,592,1.2,reach=(px+35,345))
        clock(p,303,310,58,6,0)
        clock(p,987,310,58,6,0)
        p.label(356,244,'TODAY?',31,TEAL);p.label(929,244,'TOMORROW?',31,CORAL)
    elif family=='choice_battery':
        brain(p,421,351,1.7)
        battery(p,845,281,1-.85*progress(q,.1,.91),1.5)
        for i in range(3):
            xx=690+i*150;yy=515-30*math.sin(q*math.pi+i*.5)
            p.circle(xx,yy,47,INK,TEAL if i==int(q*3)%3 else MUTED,4)
            if i==0:book(p,xx,yy,.24,1)
            elif i==1:dumbbell(p,xx,yy,.35)
            else:clock(p,xx,yy,27,6,0)
        p.label(643,138,'DECISION FATIGUE',32,WHITE)
    elif family=='fixed_anchor':
        u=progress(q,.04,.78)
        clock(p,mix(270,440,u),333,117,6,0,label='FIXED TIME')
        x=mix(1110,872,u)
        p.circle(x,284,75,CORAL);p.poly([(x-55,332),(x+55,332),(x,438)],CORAL)
        p.circle(x,282,29,WHITE)
        p.label(x,482,'FIXED PLACE',29,WHITE)
        if q>.5:arrow(p,(585,345),(740,345),TEAL,8)
    elif family=='gym':
        p.rect((195,193,1082,570),INK,18)
        p.line([(247,522),(1038,522)],MUTED,7)
        clock(p,996,273,53,6,0,label='18:00')
        rise=.5-.5*math.cos(t*2.5)
        person(p,632,577,1.65,reach=(776,422-100*rise))
        dumbbell(p,817,416-100*rise,.85)
        p.rect((244,469,378,494),TEAL,9)
        p.rect((263,493,277,584),INK,4)
    elif family in ('environment','phone_away','desk_setup'):
        desk(p,family=='desk_setup')
        if family=='environment':
            phone(p,mix(530,950,progress(q,.07,.83)),327,.72)
            book(p,mix(982,450,progress(q,.12,.88)),334,.65,progress(q,.44,.85))
            arrow(p,(741,312),(890,312),CORAL,6)
            p.label(640,140,'DESIGN YOUR SPACE',33,WHITE)
        elif family=='phone_away':
            p.rect((862,150,1100,585),INK,9,TEAL,6)
            p.rect((889,175,1075,580),'#1d2c43',5)
            book(p,360,342,.6,1)
            x=mix(621,991,progress(q,.02,.68));z=mix(.88,.51,progress(q,.1,.69))
            phone(p,x,340,z)
            closing=progress(q,.69,.97)
            p.rect((889,175,889+185*closing,580),'#384a63',5)
            p.circle(909+159*closing,373,6,GOLD)
            p.label(985,123,'OTHER ROOM',27,WHITE)
            arrow(p,(560,337),(812,337),CORAL,7)
        else:
            book(p,mix(298,565,progress(q,.02,.54)),350,.75,progress(q,.44,.95))
            p.circle(283,210,37,GOLD);p.circle(303,198,34,'#111e35')
            p.rect((780,401,844,438),TEAL,7)
            p.label(640,142,'READY TO BEGIN',34,WHITE)
            person(p,355,634,.76,reach=(480+70*progress(q,.1,.85),434))
    elif family=='reward':
        person(p,336,583,1.4,reach=(512,378))
        star(p,996,279,65,GOLD)
        p.line([(558,483),(717,483),(911,352)],MUTED,10)
        x=mix(800,549,progress(q,.08,.86));y=mix(450,374,progress(q,.08,.86))
        star(p,x,y,53,TEAL)
        p.label(991,182,'LATER',29,MUTED);p.label(562,247,'NOW',35,WHITE)
    elif family=='bundle':
        a=progress(q,.07,.8)
        x=mix(300,506,a);y=mix(978,774,a)
        p.rect((x-105,276,x+105,486),INK,30,TEAL,6)
        p.rect((y-105,276,y+105,486),INK,30,CORAL,6)
        dumbbell(p,x,378,.8)
        p.line([(y-65,387),(y-65,338),(y-34,310),(y+34,310),(y+65,338),(y+65,387)],GOLD,15)
        p.rect((y-73,375,y-46,430),GOLD,9);p.rect((y+46,375,y+73,430),GOLD,9)
        p.circle(640,381,45*progress(q,.45,.88),GOLD)
        p.line([(625,381),(655,381)],NAVY,6);p.line([(640,366),(640,396)],NAVY,6)
        p.label(640,155,'PAIR THE HABITS',36,WHITE)
    elif family=='treadmill':
        p.rect((308,575,992,620),INK,20,TEAL,3)
        for i in range(8):
            xx=323+(i*84-t*180)%645
            p.line([(xx,581),(xx-20,612)],MUTED,5)
        p.line([(950,598),(1053,360),(1111,360)],TEAL,16)
        p.rect((1009,302,1151,369),INK,12,TEAL,4)
        person(p,650,570,1.55,'run',t*7)
        p.line([(602,291),(600,260),(626,228),(675,230),(699,267),(700,291)],TEAL,11)
        p.rect((587,283,610,321),TEAL,10);p.rect((690,283,713,321),TEAL,10)
        for i in range(3):
            h=18+22*(.5+.5*math.sin(t*5+i))
            p.rect((1041+i*26,344-h,1054+i*26,348),GOLD,5)
        p.label(410,162,'WORK + REWARD',33,WHITE)
    elif family=='tea_stack':
        switch=progress(q,.25,.57)
        x=mix(407,255,switch)
        p.rect((x-62,370,x+62,477),TEAL,18)
        p.ellipse((x+45,390,x+99,455),TEAL)
        p.ellipse((x+58,403,x+85,442),NAVY)
        p.ellipse((x-72,460,x+87,482),WHITE)
        for i in range(3):
            yy=316-23*math.sin(t*1.8+i)
            p.line([(x-33+i*29,353),(x-45+i*29,yy),(x-29+i*29,yy-37)],WHITE,4)
        if q>.26:arrow(p,(421,391),(603,391),GOLD,8)
        breath=1+.025*math.sin(t*2.3)
        person(p,mix(1110,836,switch),591,1.55*breath,'meditate')
        if q>.52:p.label(830,178,'2 MIN',33,WHITE)
    elif family in ('calendar','comeback'):
        # Bring the new calendar day into reach before marking the return.
        calendar_x=mix(330,650,progress(q,0,.37)) if family=='comeback' else 650
        calendar(p,calendar_x,363,q)
        if family=='comeback' and .38<q<.85:
            # Turn the missed-day page to reveal the return on the next day.
            peel=progress(q,.38,.85)
            bottom=504-217*peel
            p.rect((calendar_x-229,287,calendar_x+229,bottom),INK,3)
            p.line([(calendar_x-229,bottom),(calendar_x+229,bottom)],TEAL,8)
            if peel<.65:
                yy=bottom-85*(1-peel)
                p.line([(calendar_x-22,yy-18),(calendar_x+22,yy+18)],CORAL,8)
                p.line([(calendar_x+22,yy-18),(calendar_x-22,yy+18)],CORAL,8)
        hand(p,mix(1030,710,progress(q,.30,.73)),458,.8)
        p.label(640,136,'NEVER MISS TWICE' if family=='calendar' else 'COME BACK',35,WHITE)
    elif family=='identity':
        p.rect((762,162,1050,596),TEAL,32)
        p.rect((781,181,1031,577),'#233b50',25)
        shift=progress(q,.08,.9)
        person(p,447+110*shift,612,1.7,reach=(672+140*shift,379))
        person(p,908,564,1.16,reach=(793,375),color=CORAL)
        for i in range(3):
            check(p,322,264+i*85,progress(q,i*.14,.35+i*.14),TEAL)
        p.label(635,112,'KEEP YOUR PROMISE',34,WHITE)
    elif family=='share_start':
        book(p,638,429,1.24,progress(q,.01,.75))
        person(p,356,615,1.3,reach=(494+46*progress(q,.12,.83),431))
        fly=progress(q,.06,.94)
        x=mix(763,1117,fly);y=mix(375,177,fly)
        p.poly([(x-39,y+8),(x+54,y-37),(x+20,y+38),(x+3,y+9)],TEAL)
        p.line([(x-55,y+28),(x-150,y+60)],'#30465c',5)
        p.label(640,138,'ONE SMALL START',36,WHITE)
    return p.finish()
