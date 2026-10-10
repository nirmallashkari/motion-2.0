"""Trusted asset animation helpers, concatenated with the registered habit renderer."""

ASSET_CACHE = {}
SCENE_SPECS = {}


def sprite(ctx, name, seconds):
    key = (ctx.scene_id, name)
    if key not in ASSET_CACHE:
        frames = []
        ends = []
        total = 0.0
        with Image.open(ctx.asset(name)) as image:
            first = 1 if image.info.get('default_image') else 0
            for index in range(first, image.n_frames):
                image.seek(index)
                frames.append(image.convert('RGBA').copy())
                total += max(.001, float(image.info.get('duration', 1000)) / 1000)
                ends.append(total)
        ASSET_CACHE[key] = (frames, ends)
    frames, ends = ASSET_CACHE[key]
    position = seconds % ends[-1]
    for index, end in enumerate(ends):
        if position < end:
            return frames[index]
    return frames[-1]


def asset_brain(p, x, y, scale, pressure):
    spec = SCENE_SPECS[p.ctx.scene_id]
    name = spec['brain_asset']
    # The mind inset uses the licensed asset without invented anatomical limbs.
    frame = sprite(p.ctx, name, p.time)
    size = max(1, round(205*scale*2*p.zoom))
    frame = frame.resize((size,size), Image.Resampling.LANCZOS)
    cx,cy = p.point(x,y)
    p.image.paste(frame,(cx-size//2,cy-size//2),frame)


def stamp(image, ctx, name, t, x, y, size, angle=0):
    frame = sprite(ctx,name,t).resize((round(size),round(size)),Image.Resampling.LANCZOS)
    if angle:
        frame = frame.rotate(angle,Image.Resampling.BICUBIC,expand=True)
    image.paste(frame,(round(x-frame.width/2),round(y-frame.height/2)),frame)


def render_asset(t, ctx, spec):
    duration = ctx.scene_end-ctx.scene_start
    q = t/max(.001,duration)
    image = Image.new('RGB',(1280,720),NAVY)
    draw = ImageDraw.Draw(image)
    action = spec['action']
    main = spec['main_asset']
    secondary = spec.get('secondary_asset')
    palette = ['#132840','#132d38','#2b2540'][spec['variation']%3]
    draw.ellipse((160,82,1120,700),fill=palette)
    if action == 'travel':
        # Camera follows the vehicle; the passing route gives clear progression.
        for line in (527,566):
            draw.line((0,line,1280,line),fill=MUTED,width=5)
        for number in range(20):
            x = (number*100-t*180)%1500-100
            draw.line((x,518,x+25,578),fill=INK,width=10)
        x = mix(280,1000,progress(q,0,1))
        draw.ellipse((x-147,520,x+147,545),fill='#080f20')
        stamp(image,ctx,main,t,x,374,312)
        if secondary:
            stamp(image,ctx,secondary,t,1115,400,126)
    elif action == 'transfer':
        # Move a visible object from the first place into the second place.
        for x in (295,985):
            draw.rounded_rectangle((x-140,242,x+140,540),radius=30,outline=TEAL,width=5)
        x = mix(295,985,progress(q,.03,.95))
        stamp(image,ctx,main,t,x,388,235)
        if secondary:
            stamp(image,ctx,secondary,t,985,161,110)
    elif action == 'pair':
        move = progress(q,0,.83)
        x = mix(285,465,move)
        y = mix(995,815,move)
        stamp(image,ctx,main,t,x,383,280)
        stamp(image,ctx,secondary or main,t,y,383,280)
        gap = max(0,90*progress(q,.25,.9))
        draw.line((550,383,550+gap,383),fill=GOLD,width=12)
        draw.line((730-gap,383,730,383),fill=GOLD,width=12)
        draw.ellipse((626,369,654,397),fill=TEAL)
    elif action == 'compare':
        # Two views separate, then the camera emphasizes the selected subject.
        move = progress(q,0,1)
        stamp(image,ctx,main,t,mix(470,355,move),385,mix(240,325,move))
        stamp(image,ctx,secondary or main,t,mix(810,950,move),385,mix(325,195,move))
        draw.line((650,214,650,570),fill=MUTED,width=4)
    elif action == 'build':
        # Each object enters and joins a physical stack, rather than a text list.
        for number in range(4):
            phase = progress(q,number*.18,number*.18+.35)
            if number == 0 or phase > 0:
                x = 393+number*164
                y = mix(520 if number == 0 else 760,482-number*46,phase)
                stamp(image,ctx,main,t,x,y,148)
        if secondary:
            stamp(image,ctx,secondary,t,640,159,110)
    elif action == 'orbit':
        stamp(image,ctx,main,t,640,379,265)
        for number in range(1 if secondary else 3):
            angle = q*math.pi*1.5+number*math.pi*2/3
            x = 640+350*math.cos(angle)
            y = 379+175*math.sin(angle)
            if secondary:
                stamp(image,ctx,secondary,t,x,y,108)
            else:
                draw.ellipse((x-15,y-15,x+15,y+15),fill=GOLD)
    else:
        # Inspect a source-mentioned object using a continuous camera move.
        size = mix(245,420,progress(q,0,1))
        x = mix(445,755,progress(q,0,1))
        stamp(image,ctx,main,t,x,385,size,-8+16*q)
        if secondary:
            stamp(image,ctx,secondary,t,1000,420,156)
    for x,y,label in spec.get('labels',[]):
        draw.text((x,y),label,font=font(32),fill=WHITE,anchor='mm')
    return image


def render(t, ctx):
    spec = SCENE_SPECS[ctx.scene_id]
    if spec['kind'] == 'habit':
        return render_habit(t,ctx)
    return render_asset(t,ctx,spec)
