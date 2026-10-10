"""Operator preview of all registered scenes at three distinct action poses."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/"framework"))
import contract
from library_pipeline import recognize,create_package,tail_frames
from local_pipeline import local_inputs
from motion_sdk import Context
from PIL import Image,ImageDraw
import habit_renderer

workspace=Path(__file__).resolve().parent.parent
source,cues,voice=local_inputs(workspace)
families=[recognize(c) for c in cues]
root=workspace/"_SYSTEM/reports/LOCAL_FINAL_2026-10-08"
project=create_package(root/"preview_package",source,cues,families,["wide"]*len(cues),18)
for offset in range(0,len(cues),9):
    batch=project["scenes"][offset:offset+9]
    sheet=Image.new("RGB",(1440,len(batch)*298),"#0c1428")
    draw=ImageDraw.Draw(sheet)
    for row,s in enumerate(batch):
        duration=(s["end_frame"]-s["start_frame"])/24
        for col,q in enumerate([.1,.5,.9]):
            t=q*duration
            ctx=Context(1280,720,24,s["start_frame"]/24+t,s["start_frame"]/24,s["end_frame"]/24,s["id"],root)
            frame=habit_renderer.render(t,ctx)
            sheet.paste(frame.resize((480,270)),(col*480,row*298))
        draw.text((8,row*298+274),s["id"],fill="white")
    path=root/f"preview_{offset//9+1}.jpg"
    sheet.save(path,quality=94)
    print(path)
