"""Build two standalone V3 design pages; never touches the workbook library."""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from core.workbook_v21 import draft

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'prototypes'
CREAM = HexColor('#F7F3E8')
PAPER = HexColor('#FFFDF8')
FOREST = HexColor('#183F35')
SAGE = HexColor('#DDE9DF')
MOSS = HexColor('#46745A')
GOLD = HexColor('#B8924A')
INK = HexColor('#1D302A')


def para(pdf, text, x, y, width, size=11.5, leading=17, color=INK, font='Helvetica'):
    style = ParagraphStyle('p', fontName=font, fontSize=size, leading=leading, textColor=color)
    item = Paragraph(escape(text), style)
    _, height = item.wrap(width, 600)
    item.drawOn(pdf, x, y-height)
    return y-height


def line(pdf, x1, y1, x2, y2, color=MOSS, width=.8):
    pdf.setStrokeColor(color); pdf.setLineWidth(width); pdf.line(x1,y1,x2,y2)


def cover(pdf, *, ink=False, prototype=True, edition='V3', white_ink=False):
    w,h=letter
    tone=HexColor('#303030') if ink else FOREST
    pdf.setFillColor(HexColor('#FFFFFF') if ink and white_ink else PAPER if ink else CREAM)
    pdf.rect(0,0,w,h,fill=1,stroke=0)
    if not ink:
        pdf.setFillColor(FOREST);pdf.rect(0,h-20,w,20,fill=1,stroke=0)
    pdf.setFillColor(tone);pdf.setFont('Helvetica-Bold',9)
    pdf.drawString(52,h-56,'OUR CLASSROOM COLLECTION')
    pdf.setFont('Helvetica',9);pdf.drawRightString(w-52,h-56,'SCIENCE  /  READING  /  INVESTIGATION')
    line(pdf,52,h-67,w-52,h-67,tone if ink else GOLD,1.2)
    pdf.setFillColor(tone);pdf.setFont('Times-Bold',44)
    pdf.drawCentredString(w/2,h-130,'How Plants Grow')
    pdf.setFont('Helvetica',15);pdf.drawCentredString(w/2,h-164,'Reading & Seed Observation Workbook')
    pdf.setFillColor(tone if ink else MOSS);pdf.setFont('Helvetica-Bold',11)
    pdf.drawCentredString(w/2,h-195,'FROM A BEAN SEED TO A YOUNG PLANT')
    art=ROOT/'assets'/('bean-growth-cover-art-ink.png' if ink else 'bean-growth-cover-art.png')
    pdf.drawImage(str(art),42,246,528,320,preserveAspectRatio=True,anchor='c',mask='auto')
    line(pdf,52,223,w-52,223,tone if ink else GOLD,1.2)
    pdf.setFillColor(tone);pdf.setFont('Helvetica-Bold',10)
    pdf.drawCentredString(w/2,193,'READ CLOSELY   •   OBSERVE HONESTLY   •   EXPLAIN WITH EVIDENCE')
    pdf.setFont('Helvetica',10);pdf.drawCentredString(w/2,168,'Three science readings  •  Seed investigation  •  Teacher answer key')
    pdf.setFillColor(tone);pdf.roundRect(52,72,156,46,7,fill=0 if ink else 1,stroke=1 if ink else 0)
    pdf.setFillColor(tone if ink else PAPER);pdf.setFont('Helvetica-Bold',15);pdf.drawCentredString(130,88,'GRADES 3–4')
    pdf.setFillColor(tone);pdf.setFont('Helvetica',10);pdf.drawRightString(w-52,91,'US LETTER  •  PRINTABLE PDF')
    pdf.setFont('Helvetica',8);pdf.drawCentredString(w/2,37,('DESIGN PROTOTYPE' if prototype else edition+' DRAFT')+'  •  Science and commercial rights require human review')
    pdf.showPage()


def reading(pdf, *, ink=False, prototype=True, edition='V3'):
    w,h=letter
    if not ink:
        pdf.setFillColor(PAPER);pdf.rect(0,0,w,h,fill=1,stroke=0)
    accent=INK if ink else FOREST
    pdf.setFillColor(accent);pdf.setFont('Helvetica-Bold',8.5)
    pdf.drawString(48,h-40,'OUR CLASSROOM COLLECTION')
    pdf.setFont('Helvetica',8.5);pdf.drawRightString(w-48,h-40,'READING 01  /  PLANT SCIENCE')
    line(pdf,48,h-49,w-48,h-49,accent,1)
    pdf.setFillColor(accent);pdf.setFont('Times-Bold',27)
    pdf.drawString(48,h-89,'Reading 1: From Seed to Seedling')
    pdf.setFont('Helvetica',10.5);pdf.drawString(48,h-111,'Describe what a bean seed needs to start growing.')
    if not ink:
        pdf.setFillColor(SAGE);pdf.roundRect(48,h-156,w-96,31,5,fill=1,stroke=0)
    pdf.setFillColor(accent);pdf.setFont('Helvetica-Bold',9)
    pdf.drawString(59,h-145,'NAME  _________________________________')
    pdf.drawRightString(w-59,h-145,'DATE  __________________')
    b=draft()['readings'][0]
    y=h-177
    for text in b['paragraphs']:
        y=para(pdf,text,51,y,w-102,11.5,17,INK)
        y-=11
    if y<400:raise ValueError('Passage overlaps the illustration; revise layout.')
    pdf.setFillColor(accent);pdf.setFont('Helvetica-Bold',9)
    pdf.drawString(48,398,'LOOK CLOSELY  /  A BEAN SEED AND A GERMINATING BEAN')
    line(pdf,48,390,w-48,390,accent,.7)
    art=ROOT/'assets'/('bean-anatomy-germination-ink.png' if ink else 'bean-anatomy-germination-art.png')
    pdf.drawImage(str(art),49,173,514,203,preserveAspectRatio=True,anchor='c',mask='auto')
    # Editorial labels sit outside the artwork; scientific pointers need human verification.
    pdf.setFillColor(accent);pdf.setFont('Helvetica-Bold',8)
    labels=[(53,363,'SEED COAT'),(167,363,'STORED FOOD'),(288,363,'EMBRYO'),
            (360,177,'EMERGING ROOT'),(377,377,'DEVELOPING SHOOT')]
    for x,yy,t in labels:pdf.drawString(x,yy,t)
    line(pdf,78,356,139,323,accent,.6)
    line(pdf,207,356,182,317,accent,.6)
    line(pdf,306,356,225,310,accent,.6)
    line(pdf,421,184,397,220,accent,.6)
    line(pdf,431,371,454,338,accent,.6)
    if not ink:
        pdf.setFillColor(SAGE);pdf.roundRect(48,71,w-96,87,7,fill=1,stroke=0)
    line(pdf,48,158,w-48,158,accent,.9)
    pdf.setFillColor(accent);pdf.setFont('Helvetica-Bold',9);pdf.drawString(58,141,'WORD HELP')
    defs=[('Germination','the beginning of growth from a seed'),('Seedling','a young plant'),('Embryo','the young plant inside a seed')]
    for i,(term,definition) in enumerate(defs):
        x=58+i*168
        pdf.setFillColor(accent);pdf.setFont('Helvetica-Bold',9);pdf.drawString(x,120,term)
        para(pdf,definition,x,111,155,8.7,12,INK)
    line(pdf,48,57,w-48,57,accent,.6)
    pdf.setFillColor(accent);pdf.setFont('Helvetica',8)
    pdf.drawString(48,39,'Our Classroom Collection  •  '+('Design prototype' if prototype else edition+' workbook')+'  •  Draft')
    pdf.drawRightString(w-48,39,'3')
    pdf.showPage()


def build():
    OUT.mkdir(parents=True,exist_ok=True)
    from PIL import Image, ImageOps
    source=Image.open(ROOT/'assets'/'bean-anatomy-germination-art.png').convert('RGBA')
    gray=ImageOps.grayscale(source)
    # A deterministic low-ink derivative preserves the original artwork geometry.
    gray=gray.point(lambda value: min(255, 95+int(value*.63)))
    gray_rgba=Image.merge('RGBA',(gray,gray,gray,source.getchannel('A')))
    gray_rgba.save(ROOT/'assets'/'bean-anatomy-germination-ink.png')
    pdf=canvas.Canvas(str(OUT/'v3-two-page-preview.pdf'),pagesize=letter)
    pdf.setTitle('How Plants Grow | V3 cover and reading page design prototype')
    cover(pdf);reading(pdf);pdf.save()
    ink_pdf=canvas.Canvas(str(OUT/'v3-reading-page-ink.pdf'),pagesize=letter)
    reading(ink_pdf,ink=True);ink_pdf.save()


if __name__=='__main__':build()
