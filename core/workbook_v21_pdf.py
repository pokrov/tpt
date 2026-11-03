"""Deterministic V2.1 classroom candidate, drawn locally without provider assets."""
from __future__ import annotations

from pathlib import Path
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
    if page_size not in PAGE_SIZES or print_mode not in {'color','ink'}:
        raise ValueError('Choose letter/a4 and color/ink.')
    width,height=PAGE_SIZES[page_size]
    margin=42
    accent=HexColor('#1B6658') if print_mode=='color' else HexColor('#111111')
    pale=HexColor('#E8F3EE') if print_mode=='color' else white
    font=_fonts()
    out=Path(path);out.parent.mkdir(parents=True,exist_ok=True)
    pdf=canvas.Canvas(str(out),pagesize=(width,height))
    pdf.setTitle(book['title']+' | Our Classroom Collection | V2.1 Draft')
    pdf.setAuthor('Our Classroom Collection')
    pdf.setSubject('Unapproved educational workbook draft')
    page=0

    def heading(title, subtitle=''):
        nonlocal page
        page+=1
        pdf.setFillColor(accent);pdf.setFont(font,10)
        pdf.drawString(margin,height-36,'OUR CLASSROOM COLLECTION  •  V2.1 DRAFT')
        pdf.setStrokeColor(accent);pdf.line(margin,height-43,width-margin,height-43)
        pdf.setFillColor(HexColor('#172E2B') if print_mode=='color' else HexColor('#111111'))
        pdf.setFont(font,18);pdf.drawString(margin,height-78,title)
        if subtitle:
            pdf.setFont(font,10);pdf.drawString(margin,height-96,subtitle)
        pdf.setFont(font,9);pdf.setFillColor(accent)
        pdf.drawString(margin,27,f'Our Classroom Collection  •  {page}  •  Draft: human review required')
        return height-120

    def paragraph(text,y,size=11.5,leading=16):
        style=ParagraphStyle('body',fontName=font,fontSize=size,leading=leading,textColor=HexColor('#111111'),spaceAfter=0)
        item=Paragraph(escape(text),style)
        _,h=item.wrap(width-2*margin,700)
        if y-h<65: raise ValueError(f'V2 page {page} content overflows; do not shrink student text.')
        item.drawOn(pdf,margin,y-h)
        return y-h-15

    def label(text,y):
        style=ParagraphStyle('label',fontName=font,fontSize=11,leading=15,textColor=accent)
        item=Paragraph(escape(text),style)
        _,h=item.wrap(width-2*margin,700)
        if y-h<65:raise ValueError(f'V2 page {page} label overflows.')
        item.drawOn(pdf,margin,y-h)
        return y-h-9

    def lines(y,count=3):
        for _ in range(count):
            if y<65:raise ValueError(f'V2 page {page} writing area overflows.')
            pdf.setStrokeColor(HexColor('#9B9B9B'));pdf.line(margin,y,width-margin,y);y-=29
        return y-8

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
        if y-143<65:raise ValueError('Reading diagram overflows.')
        title={'seed':'A bean begins to grow','leaves':'Photosynthesis: materials and energy','transport':'Water moves through a bean plant'}[reading_id]
        pdf.setFillColor(accent);pdf.setFont(font,11);pdf.drawString(margin,y,title)
        top=y-17; bottom=top-112
        pdf.setStrokeColor(accent);pdf.setFillColor(pale);pdf.roundRect(margin,bottom,width-2*margin,112,8,fill=1,stroke=1)
        if reading_id=='seed':
            centers=[margin+86,margin+240,margin+393]
            for stage,cx in enumerate(centers):plant_icon(cx,top-45,stage,.8)
            arrow(centers[0]+32,top-56,centers[1]-32,top-56);arrow(centers[1]+32,top-56,centers[2]-32,top-56)
            labels=['Seed coat protects embryo + stored food','Root emerges first','Shoot and leaves develop']
        elif reading_id=='leaves':
            centers=[margin+86,margin+240,margin+393]
            plant_icon(centers[1],top-44,2,.55)
            arrow(centers[0]+46,top-56,centers[1]-42,top-56);arrow(centers[1]+42,top-56,centers[2]-46,top-56)
            labels=['Water + carbon dioxide','Green leaf + light energy','Sugars + oxygen']
        else:
            centers=[margin+86,margin+240,margin+393]
            plant_icon(centers[1],top-44,2,.55)
            arrow(centers[0]+40,top-56,centers[1]-40,top-56);arrow(centers[1]+40,top-56,centers[2]-40,top-56)
            labels=['Soil to roots + root hairs','Stem carries water in xylem','Water reaches leaves']
        pdf.setFillColor(HexColor('#111111'));pdf.setFont(font,8.3)
        for cx,label_text in zip(centers,labels):
            words=label_text.split();split=(len(words)+1)//2
            pdf.drawCentredString(cx,bottom+22,' '.join(words[:split]));pdf.drawCentredString(cx,bottom+11,' '.join(words[split:]))
        return bottom-15

    def end():pdf.showPage()

    # 1: Local vector cover artwork. Existing logo remains a small brand mark only.
    page+=1
    pdf.setFillColor(white);pdf.rect(0,0,width,height,fill=1,stroke=0)
    pdf.setFillColor(pale);pdf.roundRect(margin,height-577,width-2*margin,342,18,fill=1,stroke=0)
    logo=BASE_DIR/'assets'/'store-logo.png'
    if logo.is_file() and print_mode=='color':
        pdf.drawImage(str(logo),margin,height-104,57,57,preserveAspectRatio=True,mask='auto')
    elif print_mode=='ink':
        pdf.setFillColor(accent);pdf.setFont(font,10);pdf.drawString(margin,height-72,'OUR CLASSROOM COLLECTION')
    pdf.setFillColor(accent);pdf.setFont(font,10);pdf.drawRightString(width-margin,height-72,'SCIENCE • READING • OBSERVATION')
    pdf.setFont(font,31);pdf.drawCentredString(width/2,height-153,'How Plants Grow')
    pdf.setFont(font,15);pdf.drawCentredString(width/2,height-183,'Reading & Seed Observation Workbook')
    pdf.setFont(font,11);pdf.drawCentredString(width/2,height-215,'A bean grows from seed to seedling')
    for stage,cx in enumerate((margin+95,margin+255,margin+415)):
        plant_icon(cx,height-348,stage,1.3)
    arrow(margin+138,height-348,margin+208,height-348)
    arrow(margin+298,height-348,margin+367,height-348)
    pdf.setFillColor(accent);pdf.setFont(font,10)
    for cx,title in zip((margin+95,margin+255,margin+415),('SEED','ROOT EMERGES','SEEDLING')):
        pdf.drawCentredString(cx,height-419,title)
    pdf.setFont(font,11);pdf.drawCentredString(width/2,height-501,'Three short readings • Mixed questions • Real observation logs')
    pdf.drawCentredString(width/2,height-531,'Evidence writing • Detailed teacher key')
    pdf.setFont(font,13);pdf.drawCentredString(width/2,137,'GRADES 3–4  •  US LETTER  •  PRINT FRIENDLY')
    pdf.setFont(font,10);pdf.drawCentredString(width/2,45,'DRAFT • Science and commercial rights require human review')
    end()

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
        y=heading(f'Reading {index}: {reading["title"]}',reading['objective'])
        y=paragraph('Name: ______________________________   Date: ______________',y,10.5,15)
        y=label('Read with a purpose',y);y=paragraph(reading['objective'],y)
        for passage in reading['paragraphs']: y=paragraph(passage,y)
        y=label('Word Help',y)
        for word,definition in reading['vocabulary'].items():y=paragraph(f'{word}: {definition}.',y,10.5,15)
        y=diagram(reading['id'],y)
        y=paragraph('Continue to the questions on the next page.',y,10,14)
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

    # 9: fixed, original text diagram. No AI-generated picture determines labels or answers.
    y=heading('Bean Plant Life Cycle','Name: __________________________  Date: ______________')
    y=paragraph('A bean is a flowering plant. Put numbers 1–5 beside the stages in their growth order. Draw arrows between the boxes.',y)
    stages=['Mature flowering plant','Seedling','Pod with seeds','Seed','Germinating seed']
    for stage in stages:
        pdf.setStrokeColor(accent);pdf.roundRect(margin,y-43,width-2*margin,42,5,stroke=1,fill=0)
        pdf.setFillColor(HexColor('#111111'));pdf.setFont(font,11);pdf.drawString(margin+15,y-26,'____   '+stage)
        icon_x=width-margin-32
        if stage=='Pod with seeds':
            pdf.setStrokeColor(accent);pdf.ellipse(icon_x-17,y-30,icon_x+17,y-14,fill=0,stroke=1)
            for dx in (-8,0,8):pdf.circle(icon_x+dx,y-22,2,fill=0,stroke=1)
        else:
            plant_icon(icon_x,y-24,{'Seed':0,'Germinating seed':1,'Seedling':2,'Mature flowering plant':3}[stage],.22)
        y-=62
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
            if y-50<65:raise ValueError('Observation sketch area overflows.')
            pdf.setStrokeColor(HexColor('#999999'));pdf.rect(margin,y-43,width-2*margin,43,stroke=1,fill=0)
            pdf.setFont(font,8);pdf.drawString(margin+5,y-12,'Quick sketch of what you actually see (optional)')
            y-=62
        end()

    # 13: data and evidence.
    y=heading('What Changed? Use Your Data','Name: __________________________  Date: ______________')
    y=paragraph('Use only your own dated log entries. An honest no-sprout result is useful evidence. Do not invent a height.',y)
    for title in ('Claim: What changed, or what did not change?',
                  'Evidence 1: Date ____  Day ____  What did you observe?',
                  'Evidence 2: Date ____  Day ____  What did you observe?',
                  'Reasoning: How do both observations support your claim?'):
        y=label(title,y);y=lines(y,2)
    y=paragraph('Optional starter: “My observations show ___ because on Day ___ I saw ___.”',y,10,14)
    end()

    # 14: synthesis.
    y=heading('Put the Ideas Together','Name: __________________________  Date: ______________')
    y=label('1. How does a young seedling get food before its leaves make much sugar?',y);y=lines(y,3)
    y=label('2. What do green leaves use to make sugars?',y);y=lines(y,3)
    y=label('3. Write the bean stages in order, starting with a seed.',y);y=lines(y,3)
    y=label('4. Make a claim about your bean. Use two observations as evidence.',y);y=lines(y,5)
    end()

    # 15–18: key from the same canonical question list used on student pages.
    y=heading('Teacher Key: Readings','Draft guidance • Check against final student pages before approval')
    for index,reading in enumerate(book['readings'],1):
        if index>1:
            end();y=heading(f'Teacher Key: Reading {index}',f'Student PDF page {4+(index-1)*2}')
        y=label(f'Reading {index} — student PDF page {4+(index-1)*2}',y)
        for n,q in enumerate(reading['questions'],1):
            answer=q['answer'] if isinstance(q['answer'],str) else '; '.join(f'{item}: {value}' for item,value in zip(q['items'],q['answer']))
            y=paragraph(f'{n}. {answer}',y,9.7,13)
            y=paragraph('Source: '+q['evidence'],y,9.2,12)
            if q['kind'] not in {'mcq'}:y=paragraph('Accept: '+q['rubric'],y,9.2,12)
    end()
    y=heading('Teacher Key: Inquiry','Draft guidance • Never invent student observations')
    for title,body in [
        ('Life cycle, page 9','Seed (1) → germinating seed (2) → seedling (3) → mature flowering plant (4) → pod with seeds (5). The seeds in a pod can begin the next cycle.'),
        ('Observation, pages 10–12','There is no fixed expected germination date or height. Accept dated records of actual observations, including no germination observed. Check that any height has cm units and follows the student measurement rule.'),
        ('Data and evidence, page 13','Give full credit for a clear claim, two dated observations, and a sentence explaining how both support it. Partial credit for an accurate but incomplete link. Accept an honest no-sprout result; invented data are unsupported.'),
        ('Synthesis, page 14','1. Stored food inside the seed. 2. Water and carbon dioxide, using energy from light. 3. Seed → germination → seedling → mature flowering plant → pods/seeds. 4. Accept a claim tied to two actual log entries.'),
        ('Scoring written responses','Check the science separately from evidence. Full credit: accurate idea with cited reading or actual log details. Developing: accurate idea with missing support. Revise: incorrect science or invented observations.'),
        ('Misconceptions to watch','Sunlight supplies energy, not food itself. Soil is not the source of sugars. A bean is a flowering seed plant; not every non-flowering plant makes spores. Xylem carries water; a straw analogy does not explain the mechanism.')]:
        y=label(title,y);y=paragraph(body,y,10.5,15)
    y=paragraph('PUBLICATION BLOCKED: science, answers, layout and commercial-use rights require human verification.',y,9.5,13)
    end()
    pdf.save()
    from pypdf import PdfReader
    if len(PdfReader(str(out)).pages)!=18:
        out.unlink(missing_ok=True);raise ValueError('V2.1 workbook must have exactly 18 useful draft pages.')
    return out
