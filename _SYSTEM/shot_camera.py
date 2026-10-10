"""Renderer-backed composition profiles shared by nonhuman Python graphics."""


def shot_camera_2d(profile,q):
    yaw=profile['yaw'];move=profile['move']
    cx=640+yaw*260;cy=360
    if move=='push':zoom=1+.10*q;cx+=45*(q-.5)
    elif move=='pull':zoom=1.13-.10*q;cx-=45*(q-.5)
    elif move=='orbit':zoom=1.04;cx+=80*math.sin(q*math.pi*2);cy+=20*math.sin(q*math.pi)
    else:raise ValueError('Unregistered shot camera motion')
    return cx,cy,zoom
