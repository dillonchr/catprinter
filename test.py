import sys
from datetime import datetime

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.ImageChops


PrinterWidth=384

def trim(im):
    bg = PIL.Image.new(im.mode, im.size, (255,255,255))
    diff = PIL.ImageChops.difference(im, bg)
    diff = PIL.ImageChops.add(diff, diff, 2.0)
    bbox = diff.getbbox()
    if bbox:
        return im.crop((bbox[0],bbox[1],bbox[2],bbox[3]+10))


def create_text(text, font_name="IBMPlexMono-Regular.ttf", font_size=20):
    lines = []
    for line in text:
        lines.append(line)
    height = len(lines) * 50
    lines = "\n".join(lines)

    img = PIL.Image.new('RGB', (PrinterWidth, height), color = (255, 255, 255))
    font = PIL.ImageFont.truetype(font_name, font_size)
    d = PIL.ImageDraw.Draw(img)
    d.multiline_text((0,0), lines, fill=(0,0,0), font=font, spacing=-10)
    trim(img)
    img.save("test.png")

if "__main__" == __name__:
    create_text(sys.stdin)
    #create_text(f"Oh hi there!\n{datetime.now()}")
