"""Separate offline V3.1 candidate, preserving the approved V3 botanical design."""
from __future__ import annotations

from pathlib import Path
from math import hypot
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from core.paths import BASE_DIR
from core.workbook_v21 import validate
from design.build_v3_prototype import cover as v3_cover, reading as v3_reading

ASSETS = Path(__file__).resolve().parent / 'assets'

PAGE_SIZES = {'letter':letter, 'a4':A4}


def _fonts():
    # Bundled system fonts have an unresolved commercial-use review status until documented.
    import os
    candidates=(os.getenv('V2_FONT_PATH',''),'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    base=next((path for path in candidates if os.path.isfile(path)),None)
    if base and 'V2Sans' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('V2Sans',base))
    return 'V2Sans' if 'V2Sans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'


def build_pdf(book, path, *, page_size='letter', print_mode='color'):
    book=validate(book)
    if page_size != 'letter' or print_mode not in {'color','ink'}:
        raise ValueError('V3 supports US Letter color/ink only.')
    width,height=PAGE_SIZES[page_size]
    margin=48
    accent=HexColor('#183F35') if print_mode=='color' else HexColor('#1D302A')
    pale=HexColor('#DDE9DF') if print_mode=='color' else white
    font=_fonts()
    out=Path(path);out.parent.mkdir(parents=True,exist_ok=True)
    pdf=canvas.Canvas(str(out),pagesize=(width,height))
    pdf.setTitle(book['title']+' | Our Classroom Collection | V3.1 Draft')
    pdf.setAuthor('Our Classroom Collection')
    pdf.setSubject('Unapproved educational workbook draft')
    page=0

    def heading(title, subtitle=''):
        nonlocal page
        page+=1
        if print_mode=='color':
            pdf.setFillColor(HexColor('#FFFDF8'));pdf.rect(0,0,width,height,fill=1,stroke=0)
        pdf.setFillColor(accent);pdf.setFont('Helvetica-Bold',8.5)
        pdf.drawString(margin,height-36,'OUR CLASSROOM COLLECTION')
        pdf.setFont('Helvetica',8.5)
        pdf.drawRightString(width-margin,height-36,'SCIENCE  /  READING  /  INVESTIGATION')
        pdf.setStrokeColor(accent);pdf.line(margin,height-43,width-margin,height-43)
        pdf.setFillColor(HexColor('#172E2B') if print_mode=='color' else HexColor('#111111'))
        pdf.setFont('Times-Bold',25);pdf.drawString(margin,height-83,title)
        if subtitle:
            pdf.setFont(font,10);pdf.drawString(margin,height-96,subtitle)
        pdf.setFont('Helvetica',8);pdf.setFillColor(accent)
        pdf.drawString(margin,35,'Our Classroom Collection  •  V3.1 Draft  •  Human review required')
        pdf.drawRightString(width-margin,35,str(page))
        pdf.setStrokeColor(accent);pdf.line(margin,54,width-margin,54)
        return height-121

    def paragraph(text,y,size=11.5,leading=16):
        style=ParagraphStyle('body',fontName=font,fontSize=size,leading=leading,textColor=HexColor('#111111'),spaceAfter=0)
        item=Paragraph(escape(text),style)
        _,h=item.wrap(width-2*margin,700)
        if y-h<70: raise ValueError(f'V3 page {page} content overflows; do not shrink student text.')
        item.drawOn(pdf,margin,y-h)
        return y-h-15

    def label(text,y):
        style=ParagraphStyle('label',fontName=font,fontSize=11,leading=15,textColor=accent)
        item=Paragraph(escape(text),style)
        _,h=item.wrap(width-2*margin,700)
        if y-h<70:raise ValueError(f'V3 page {page} label overflows.')
        item.drawOn(pdf,margin,y-h)
        return y-h-9

    def lines(y,count=3,step=29):
        for _ in range(count):
            if y<65:raise ValueError(f'V3.1 page {page} writing area overflows.')
            pdf.setStrokeColor(HexColor('#9B9B9B'));pdf.line(margin,y,width-margin,y);y-=step
        return y-8

    def directed_arrow(x1,y1,x2,y2,*,dashed=False):
        length=hypot(x2-x1,y2-y1)
        if length<1:raise ValueError('Arrow has no direction.')
        ux,uy=(x2-x1)/length,(y2-y1)/length
        pdf.setStrokeColor(accent);pdf.setLineWidth(1.4)
        if dashed:pdf.setDash(4,3)
        pdf.line(x1,y1,x2,y2)
        pdf.setDash()
        for side in (-1,1):
            pdf.line(x2,y2,x2-7*ux+side*3.5*uy,y2-7*uy-side*3.5*ux)

    def arrow(x1,y1,x2,y2):
        pdf.setStrokeColor(accent);pdf.setLineWidth(1.4);pdf.line(x1,y1,x2,y2)
        pdf.line(x2,y2,x2-6,y2+4);pdf.line(x2,y2,x2-6,y2-4)

    def plant_icon(cx,cy,stage,scale=1):
        """Plausible bean growth silhouettes; no hidden measured quantities."""
        pdf.setStrokeColor(accent);pdf.setLineWidth(1.8)
        pdf.setFillColor(pale)
        if stage==0:  # seed
            pdf.ellipse(cx-13*scale,cy-9*scale,cx+13*scale,cy+9*scale,fill=1,stroke=1)
        else:
            pdf.ellipse(cx-12*scale,cy+3*scale,cx+12*scale,cy+19*scale,fill=1,stroke=1)
            pdf.line(cx,cy+4*scale,cx-3*scale,cy-19*scale)
            pdf.line(cx-3*scale,cy-19*scale,cx-10*scale,cy-28*scale)
            if stage>=2:
                pdf.line(cx,cy+13*scale,cx+1*scale,cy+43*scale)
                pdf.ellipse(cx-17*scale,cy+27*scale,cx,cy+42*scale,fill=1,stroke=1)
                pdf.ellipse(cx+1*scale,cy+28*scale,cx+18*scale,cy+43*scale,fill=1,stroke=1)
            if stage>=3:
                pdf.line(cx,cy+42*scale,cx,cy+63*scale)
                pdf.circle(cx,cy+67*scale,5*scale,fill=0,stroke=1)

    def diagram(reading_id,y):
        if y-218<70:raise ValueError(f'V3 page {page} illustration overflows.')
        title={'leaves':'LOOK CLOSELY  /  HOW A GREEN PLANT MAKES SUGAR',
               'transport':'LOOK CLOSELY  /  THE PATH OF WATER'}[reading_id]
        pdf.setFillColor(accent);pdf.setFont('Helvetica-Bold',9);pdf.drawString(margin,y,title)
        pdf.setStrokeColor(accent);pdf.setLineWidth(.7);pdf.line(margin,y-8,width-margin,y-8)
        bottom=y-211
        plant=ASSETS/('v3-bean-plant-ink.png' if print_mode=='ink' else 'v3-bean-plant.png')
        pdf.drawImage(str(plant),margin+146,bottom+5,218,190,preserveAspectRatio=True,anchor='c',mask='auto')
        pdf.setFont('Helvetica-Bold',8.8);pdf.setFillColor(accent)
        if reading_id=='leaves':
            pdf.drawString(margin+6,bottom+183,'LIGHT ENERGY')
            pdf.drawString(margin+6,bottom+135,'CARBON DIOXIDE')
            pdf.drawString(margin+6,bottom+52,'WATER')
            pdf.drawString(margin+370,bottom+178,'OXYGEN')
            pdf.drawString(margin+370,bottom+112,'SUGARS')
            pdf.setFont('Helvetica',7.9)
            for x,yy,t in [(margin+6,bottom+171,'from sun / dashed energy arrow'),
                           (margin+6,bottom+123,'material input / from air'),
                           (margin+6,bottom+40,'material input / through roots'),
                           (margin+370,bottom+166,'released to air'),
                           (margin+370,bottom+100,'made in leaves; used by plant')]:
                pdf.drawString(x,yy,t)
            directed_arrow(174,bottom+172,258,bottom+157,dashed=True)
            directed_arrow(174,bottom+124,259,bottom+147)
            directed_arrow(174,bottom+37,278,bottom+32)
            directed_arrow(347,bottom+158,411,bottom+170)
            pdf.setStrokeColor(accent);pdf.setLineWidth(.6)
            pdf.line(411,bottom+104,359,bottom+140)
        else:
            pdf.drawString(margin+6,bottom+94,'ROOTS')
            pdf.drawString(margin+6,bottom+50,'SOIL WATER')
            pdf.drawString(margin+370,bottom+176,'LEAVES')
            pdf.drawString(margin+370,bottom+112,'STEM')
            pdf.setFont('Helvetica',7.9)
            pdf.drawString(margin+6,bottom+38,'water enters through roots')
            pdf.drawString(margin+370,bottom+100,'xylem inside carries water')
            pdf.drawString(margin+370,bottom+80,'water travels upward')
            pdf.setStrokeColor(accent);pdf.setLineWidth(.7)
            pdf.line(173,bottom+88,276,bottom+61)
            pdf.line(414,bottom+166,356,bottom+155)
            pdf.line(414,bottom+104,311,bottom+103)
            directed_arrow(174,bottom+35,277,bottom+29)
            for low,high in ((59,83),(91,119),(126,150)):
                directed_arrow(307,bottom+low,307,bottom+high)
        return bottom-12

    def end():pdf.showPage()

    # 1: Approved V3 cover design. The original prototype remains unchanged by default.
    v3_cover(pdf, ink=(print_mode=='ink'), prototype=False, edition='V3.1', white_ink=True)
    page=1

    # 2: Teacher quick start.
    y=heading('Teacher Quick Start','Grades 3–4 • Bean growth inquiry')
    for title,body in [
        ('Learning objectives',book['objective']+' Students will order bean growth stages and support a claim with two real observations.'),
        ('Materials',', '.join(book['materials'])+'.'),
        ('Preparation','Allow about 10 minutes to set up 2–3 dry beans with a moist paper towel or suitable soil in a clear cup or bag. An adult handles setup.'),
        ('Flexible lesson sequence','First read and discuss pages 3–8. Next complete the life-cycle task and setup on pages 9–10. Over several days, use logs on pages 11–12. Finish with evidence and synthesis on pages 13–14.'),
        ('Observation and assessment','Mark setup as Day 0. Check for about five minutes on several dates. Record root, shoot, leaves and height only when measurable. Use pages 15–18 to assess accuracy and evidence; germination timing varies.'),
        ('Safety and troubleshooting','Do not taste seeds or growing material; wash hands afterward. Keep the medium moist, not waterlogged. If no seed sprouts, record that result, check moisture and conditions, and discuss possible explanations without inventing observations.')]:
        y=label(title,y);y=paragraph(body,y,10.5,14)
    end()

    for index,reading in enumerate(book['readings'],1):
        if index==1:
            v3_reading(pdf, ink=(print_mode=='ink'), prototype=False, edition='V3.1')
            page+=1
        else:
            y=heading(f'Reading {index}: {reading["title"]}',reading['objective'])
            y=paragraph('Name: ______________________________   Date: ______________',y,10.5,15)
            y=label('READ WITH A PURPOSE',y)
            for passage in reading['paragraphs']: y=paragraph(passage,y)
            y=label('WORD HELP',y)
            for word,definition in reading['vocabulary'].items():y=paragraph(f'{word}: {definition}.',y,10.5,15)
            y=diagram(reading['id'],y)
            end()
        y=heading(f'Reading {index}: Questions','Name: __________________________  Date: ______________')
        y=paragraph('Use the reading. Circle one answer for each multiple-choice question, then complete the written tasks.',y,10.5,15)
        for number,q in enumerate(reading['questions'],1):
            y=label(f'{number}. {q["prompt"]}',y)
            if q['kind']=='mcq':
                for letter,value in q['options'].items(): y=paragraph(f'({letter}) {value}',y,10.5,14)
                y-=3
            elif q['kind'] in {'sequence','classify'}:
                for item in q['items']:
                    y=paragraph(f'_____  {item}',y,10.5,14)
                y-=3
            else:y=lines(y,3)
        end()

    # 9: original botanical stages in intentionally shuffled order; the key owns the order.
    y=heading('Bean Plant Life Cycle','Name: __________________________  Date: ______________')
    y=paragraph('A bean is a flowering plant. Put numbers 1–5 beside the stages in their growth order. Draw arrows between the boxes.',y)
    stages=[('Mature flowering plant',4),('Seedling',3),('Pod with seeds',5),
            ('Seed',1),('Germinating seed',2)]
    for stage,asset_number in stages:
        row_top=y+1; row_bottom=y-82
        if row_bottom<78:raise ValueError('Life-cycle artwork overflows.')
        pdf.setStrokeColor(accent);pdf.setLineWidth(.7)
        if print_mode=='color':
            pdf.setFillColor(HexColor('#F7F3E8'))
            pdf.roundRect(margin,row_bottom,width-2*margin,83,5,stroke=1,fill=1)
        else:pdf.roundRect(margin,row_bottom,width-2*margin,83,5,stroke=1,fill=0)
        pdf.setFillColor(accent);pdf.setFont('Helvetica-Bold',11)
        pdf.drawString(margin+18,row_bottom+38,'____   '+stage)
        prefix='v31-stage' if asset_number in (4,5) else 'v3-stage'
        art=ASSETS/f'{prefix}-{asset_number}{"-ink" if print_mode=="ink" else ""}.png'
        pdf.drawImage(str(art),width-margin-116,row_bottom+4,107,75,
                      preserveAspectRatio=True,anchor='c',mask='auto')
        y-=97
    y=paragraph('Which stage begins the next cycle? ______________________________',y)
    end()

    # 10: protocol.
    y=heading('Seed Observation Protocol','Name: __________________________  Date: ______________')
    y=label('Materials',y);y=paragraph(', '.join(book['materials'])+'.',y,10.5,14)
    for n,(title,body) in enumerate([('Predict','What do you think will change first? Write a prediction you can check.'),('Set up','With an adult, place 2–3 beans in a clear cup or bag with moist paper towel or suitable soil. Mark this date Day 0.'),('Keep conditions steady','Use the same location and check moisture regularly. Do not let the material dry out or become waterlogged.'),('Observe and measure','Check on several dates. Record root, shoot and leaves if visible. Measure height from the growing surface in centimeters only when a shoot is visible.'),('If nothing sprouts','Write “no germination observed” for that check. Do not invent a result or change the date.')],1):
        y=label(f'{n}. {title}',y);y=paragraph(body,y)
        if title=='Predict':y=lines(y,2)
    end()

    # 11–12: reusable observations with bounded blank sketch boxes.
    for logpage in range(2):
        y=heading(f'Observation Log {logpage+1}','Name: __________________________  Seed type: __________')
        y=paragraph('Record the date and day number. Mark only what you can see; write “not seen” when appropriate. Measure shoot height in cm, if measurable.',y,10.5,15)
        for row in range(3):
            n=logpage*3+row+1
            y=label(f'Observation {n}',y)
            y=paragraph('Date: __________  Day: ____  Moisture/condition: ____________________',y,10,14)
            y=paragraph('Root: __________  Shoot: __________  Leaves: __________  Height: ____ cm',y,10,14)
            y=paragraph('Notes: __________________________________________________________',y,10,14)
            if y-67<65:raise ValueError('Observation sketch area overflows.')
            pdf.setStrokeColor(HexColor('#999999'));pdf.rect(margin,y-60,width-2*margin,60,stroke=1,fill=0)
            pdf.setFont(font,8);pdf.drawString(margin+5,y-12,'Quick sketch of what you actually see (optional)')
            y-=79
        end()

    # 13: data and evidence.
    y=heading('What Changed? Use Your Data','Name: __________________________  Date: ______________')
    y=paragraph('Use only your own dated log entries. An honest no-sprout result is useful evidence. Do not invent a height.',y)
    for title,count in (('Claim: What changed, or what did not change?',3),
                        ('Evidence 1: Date ____  Day ____  What did you observe?',2),
                        ('Evidence 2: Date ____  Day ____  What did you observe?',2),
                        ('Reasoning: How do both observations support your claim?',3)):
        y=label(title,y);y=lines(y,count,step=33)
    y=paragraph('Optional starter: “My observations show ___ because on Day ___ I saw ___.”',y,10,14)
    end()

    # 14: synthesis.
    y=heading('Put the Ideas Together','Name: __________________________  Date: ______________')
    y=label('1. How does a young seedling get food before its leaves make much sugar?',y);y=lines(y,3,step=31)
    y=label('2. What do green leaves use to make sugars?',y);y=lines(y,3,step=31)
    y=label('3. Write the bean stages in order, starting with a seed.',y);y=lines(y,3,step=31)
    y=label('4. Make a claim about your bean. Use two observations as evidence.',y);y=lines(y,5,step=31)
    end()

    # 15–18: key from the same canonical question list used on student pages.
    y=heading('Teacher Key: Readings','Draft guidance • Check against final student pages before approval')
    for index,reading in enumerate(book['readings'],1):
        if index>1:
            end();y=heading(f'Teacher Key: Reading {index}',f'Student PDF page {4+(index-1)*2}')
        y=label(f'READING {index}  /  STUDENT PAGE {4+(index-1)*2}',y)
        for n,q in enumerate(reading['questions'],1):
            y=label(f'{n}. {q["prompt"]}',y)
            if q['kind']=='mcq':
                answer=f'({q["answer"]}) {q["options"][q["answer"]]}'
            elif isinstance(q['answer'],str):answer=q['answer']
            else:answer='; '.join(f'{item}: {value}' for item,value in zip(q['items'],q['answer']))
            y=paragraph('CORRECT ANSWER  '+answer,y,10.3,14)
            evidence=q['evidence']
            if q['id']=='seed-m1':
                water='A seed begins to germinate when it takes in water under suitable conditions.'
                if water not in ' '.join(reading['paragraphs']):
                    raise ValueError('Seed question needs its canonical water evidence.')
                evidence=water+' '+evidence
            y=paragraph('Reading evidence: '+evidence,y,9.5,13)
            if q['kind']!='mcq':y=paragraph('Acceptable response: '+q['rubric'],y,9.5,13)
            y-=5
    end()
    y=heading('Teacher Key: Inquiry','Draft guidance • Never invent student observations')
    for title,body in [
        ('Life cycle, page 9','Seed (1) → germinating seed (2) → seedling (3) → mature flowering plant (4) → pod with seeds (5). The seeds in a pod can begin the next cycle.'),
        ('Observation, pages 10–12','There is no fixed expected germination date or height. Accept dated records of actual observations, including no germination observed. Check that any height has cm units and follows the student measurement rule.'),
        ('Data and evidence, page 13','Give full credit for a clear claim, two dated observations, and a sentence explaining how both support it. Partial credit for an accurate but incomplete link. Accept an honest no-sprout result; invented data are unsupported.'),
        ('Synthesis, page 14','1. Stored food inside the seed. 2. Water and carbon dioxide, using energy from light. 3. Seed → germination → seedling → mature flowering plant → pods/seeds. 4. Accept a claim tied to two actual log entries.'),
        ('Scoring written responses','Check the science separately from evidence. Full credit: accurate idea with cited reading or actual log details. Developing: accurate idea with missing support. Revise: incorrect science or invented observations.'),
        ('Misconceptions to watch','Sunlight supplies energy, not food itself. Soil is not the source of sugars. A bean is a flowering seed plant; not every non-flowering plant makes spores. Xylem carries water; a straw analogy does not explain the mechanism.')]:
        y=label(title,y);y=paragraph(body,y,10.8,16)
    y=paragraph('PUBLICATION BLOCKED: science, answers, layout and commercial-use rights require human verification.',y,9.8,14)
    end()
    pdf.save()
    from pypdf import PdfReader
    if len(PdfReader(str(out)).pages)!=18:
        out.unlink(missing_ok=True);raise ValueError('V3.1 workbook must have exactly 18 useful draft pages.')
    return out
