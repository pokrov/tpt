"""Deterministic US Letter/A4 V2 draft pages, including a true low-ink style."""
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
from core.workbook_v2 import validate, review_issues

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
    pdf.setTitle(book['title']+' | Our Classroom Collection | Draft')
    pdf.setAuthor('Our Classroom Collection')
    pdf.setSubject('Unapproved educational workbook draft')
    page=0

    def heading(title, subtitle=''):
        nonlocal page
        page+=1
        pdf.setFillColor(accent);pdf.setFont(font,10)
        pdf.drawString(margin,height-36,'OUR CLASSROOM COLLECTION  •  DRAFT')
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

    def diagram(reading_id,y):
        """Fixed text diagram; the artwork never supplies an unseen answer."""
        if reading_id=='seed':
            title='Growth sequence';items=['Dry seed','First root','Shoot and leaves']
        elif reading_id=='leaves':
            title='What a green leaf uses and makes';items=['Water + carbon dioxide','Green leaf + light energy','Sugars + oxygen']
        else:
            title='Water pathway';items=['Soil and roots','Stem (xylem)','Leaves']
        if y-128<65:raise ValueError('Reading diagram overflows.')
        pdf.setFont(font,10.5);pdf.setFillColor(accent);pdf.drawString(margin,y,title)
        y-=18
        box_w=(width-2*margin-36)/3
        for i,item in enumerate(items):
            x=margin+i*(box_w+18)
            pdf.setStrokeColor(accent);pdf.setFillColor(pale)
            pdf.roundRect(x,y-69,box_w,69,6,fill=1,stroke=1)
            pdf.setFillColor(HexColor('#111111'));pdf.setFont(font,9)
            words=item.split();split=max(1,len(words)//2)
            for j,line in enumerate((' '.join(words[:split]),' '.join(words[split:]))):
                if line:pdf.drawCentredString(x+box_w/2,y-31-j*15,line)
            if i<2:
                pdf.setStrokeColor(accent);pdf.line(x+box_w+3,y-35,x+box_w+15,y-35)
                pdf.line(x+box_w+15,y-35,x+box_w+10,y-31)
                pdf.line(x+box_w+15,y-35,x+box_w+10,y-39)
        return y-87

    def end():pdf.showPage()

    # 1: Cover. The supplied logo is a bitmap; no model image or unverified science diagram is needed.
    page+=1
    pdf.setFillColor(pale);pdf.rect(0,0,width,height,fill=1,stroke=0)
    logo=BASE_DIR/'assets'/'store-logo.png'
    if logo.is_file() and print_mode=='color':
        pdf.drawImage(str(logo),width/2-78,height-205,156,156,preserveAspectRatio=True,mask='auto')
    elif print_mode=='ink':
        pdf.setFillColor(accent);pdf.setFont(font,14)
        pdf.drawCentredString(width/2,height-136,'OUR CLASSROOM COLLECTION')
    pdf.setFillColor(accent);pdf.setFont(font,27)
    pdf.drawCentredString(width/2,height-270,'How Plants Grow')
    pdf.setFont(font,15);pdf.drawCentredString(width/2,height-300,'Reading & Seed Observation Workbook')
    pdf.setFont(font,12);pdf.drawCentredString(width/2,height-330,'Grades 3–4  •  Printable PDF')
    pdf.setFont(font,11)
    for i,text in enumerate(['Three science readings and mixed questions','Bean life cycle and observation logs','Evidence writing and teacher answer key']):
        pdf.drawCentredString(width/2,height-398-i*28,text)
    pdf.setFont(font,10);pdf.drawCentredString(width/2,45,'DRAFT • Science and commercial rights require human review')
    end()

    # 2: Teacher quick start.
    y=heading('Teacher Quick Start','Grades 3–4 • Bean growth inquiry')
    y=label('Learning goal',y);y=paragraph(book['objective'],y)
    y=label('Materials',y);y=paragraph(', '.join(book['materials'])+'.',y)
    y=label('Setup and safety',y)
    y=paragraph('Allow about 10 minutes to place 2–3 dry beans in a clear cup or bag with a moist paper towel or suitable soil. An adult handles setup. Do not taste seeds or growing material; wash hands after handling. Keep the medium moist, not waterlogged.',y)
    y=label('Observation routine',y)
    y=paragraph('Mark setup as Day 0. Spend about five minutes on each check over several days. Record the date, day, water/condition, root, shoot, leaves, and height when measurable. Germination time varies. If no sprout appears, record that result honestly.',y)
    y=label('Use and assessment',y)
    y=paragraph('Read pages 3, 5 and 7 before their paired question pages. Use the life-cycle page, protocol, two log pages, data-and-evidence page and synthesis page as a connected inquiry. Pages 15–16 provide fixed answers and open-response guidance.',y)
    y=label('Control the comparison',y)
    y=paragraph('If students compare beans, keep the type of bean and growing conditions as similar as practical. Do not promise that all seeds will grow. This draft needs science and rights review before commercial use.',y)
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
        y=paragraph('Use details from the reading. Circle one answer for each multiple-choice question. Write an evidence-based response.',y,10.5,15)
        for number,q in enumerate(reading['questions'],1):
            y=label(f'{number}. {q["prompt"]}',y)
            if q['kind']=='mcq':
                for letter,value in q['options'].items(): y=paragraph(f'({letter}) {value}',y,10.5,14)
                y-=8
            else:y=lines(y,4)
        end()

    # 9: fixed, original text diagram. No AI-generated picture determines labels or answers.
    y=heading('Bean Plant Life Cycle','Name: __________________________  Date: ______________')
    y=paragraph('A bean is a flowering plant. Put numbers 1–5 beside the stages in their growth order. Draw arrows between the boxes.',y)
    stages=['Mature flowering plant','Seedling','Pod with seeds','Seed','Germinating seed']
    for stage in stages:
        pdf.setStrokeColor(accent);pdf.roundRect(margin,y-43,width-2*margin,42,5,stroke=1,fill=0)
        pdf.setFillColor(HexColor('#111111'));pdf.setFont(font,11);pdf.drawString(margin+15,y-26,'____   '+stage)
        y-=62
    y=paragraph('Which stage begins the next cycle? ______________________________',y)
    end()

    # 10: protocol.
    y=heading('Seed Observation Protocol','Name: __________________________  Date: ______________')
    for title,body in [('Predict','What do you think will change first? Write a prediction you can check.'),('Set up','With an adult, place 2–3 beans in a clear cup or bag with moist paper towel or suitable soil. Mark this date Day 0.'),('Keep conditions steady','Use the same location and check moisture regularly. Do not let the material dry out or become waterlogged.'),('Observe and measure','Check on several dates. Record root, shoot and leaves if visible. Measure height from the growing surface in centimeters only when a shoot is visible.'),('If nothing sprouts','Write “no germination observed” for that check. Do not invent a result or change the date.')]:
        y=label(title,y);y=paragraph(body,y)
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
    y=paragraph('Copy two real observations from your log. If no seed sprouted, say so. Use centimeters only for a height you measured.',y)
    for n in (1,2):
        y=label(f'Observation {n}: date ______  day ____  height ____ cm or “not measured”',y)
        y=lines(y,2)
    y=label('Claim: What changed, or what did not change?',y);y=lines(y,3)
    y=label('Evidence: Which two observations support your claim?',y);y=lines(y,3)
    end()

    # 14: synthesis.
    y=heading('Put the Ideas Together','Name: __________________________  Date: ______________')
    y=label('1. How does a young seedling get food before its leaves make much sugar?',y);y=lines(y,3)
    y=label('2. What do green leaves use to make sugars?',y);y=lines(y,3)
    y=label('3. Write the bean stages in order, starting with a seed.',y);y=lines(y,3)
    y=label('4. Make a claim about your bean. Use two observations as evidence.',y);y=lines(y,5)
    end()

    # 15–16: key and teacher acceptability guidance.
    y=heading('Teacher Key: Readings','Draft guidance • Check against final student pages before approval')
    for index,reading in enumerate(book['readings'],1):
        y=label(f'Reading {index} — student PDF page {4+(index-1)*2}',y)
        for n,q in enumerate(reading['questions'],1):
            answer=q['answer'] if q['kind']=='mcq' else q['answer']
            y=paragraph(f'{n}. {answer} Evidence: {q["evidence"]}',y,10.5,15)
            if q['kind']=='short':y=paragraph('Accept: '+q['rubric'],y,10.5,15)
    end()
    y=heading('Teacher Key: Inquiry','Draft guidance • Never invent student observations')
    for title,body in [
        ('Life cycle, page 9','Seed (1) → germinating seed (2) → seedling (3) → mature flowering plant (4) → pod with seeds (5). The seeds in a pod can begin the next cycle.'),
        ('Observation, pages 10–12','There is no fixed expected germination date or height. Accept dated records of actual observations, including no germination observed. Check that any height has cm units and follows the student measurement rule.'),
        ('Data and evidence, page 13','Accept a claim supported by two recorded observations. An honest no-sprout result is valid. Do not score an invented result as evidence.'),
        ('Synthesis, page 14','1. Stored food inside the seed. 2. Water and carbon dioxide, using energy from light. 3. Seed → germination → seedling → mature flowering plant → pods/seeds. 4. Accept a claim tied to two actual log entries.'),
        ('Misconceptions to watch','Sunlight supplies energy, not food itself. Soil is not the source of sugars. A bean is a flowering seed plant; not every non-flowering plant makes spores. Xylem carries water; a straw analogy does not explain the mechanism.')]:
        y=label(title,y);y=paragraph(body,y,10.5,15)
    if review_issues(book):
        y=paragraph('PUBLICATION BLOCKED: science and/or commercial-use rights require human verification.',y,9.5,13)
    end()
    pdf.save()
    from pypdf import PdfReader
    if len(PdfReader(str(out)).pages)!=16:
        out.unlink(missing_ok=True);raise ValueError('V2 workbook must have exactly 16 useful draft pages.')
    return out
