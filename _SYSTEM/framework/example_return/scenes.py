"""A local-time Python introduction and ending."""
from motion_sdk import drawing_layer, composite, text_box, eo_cubic

def intro(t, ctx):
    image = ctx.canvas()
    layer, draw = drawing_layer(image)
    x = 80 + 250 * eo_cubic(t / .5)
    draw.ellipse((x - 50, 140, x + 50, 240), fill=(34, 197, 94, 255))
    text_box(draw, "SMALL STARTS", (50, 290, ctx.width-50, ctx.height-70), px=58)
    return composite(image, layer)

def ending(t, ctx):
    image = ctx.canvas()
    layer, draw = drawing_layer(image)
    text_box(draw, "KEEP GOING", (50, 130, ctx.width-50, ctx.height-130), px=68)
    draw.rectangle((80, ctx.height-85, 80+(ctx.width-160)*min(1, t), ctx.height-65), fill=(250, 204, 21, 255))
    return composite(image, layer)
