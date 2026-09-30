#!/usr/bin/env python3
"""Optional document tool: requires reportlab, never used by deployment."""
from pathlib import Path
import argparse
import os
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xml.sax.saxutils import escape

class Diagram(Flowable):
    def __init__(self):
        super().__init__(); self.width=480; self.height=110
    def draw(self):
        c=self.canv
        for x,y,w,label in [(0,65,145,'Ubuntu / Kubernetes'),(173,65,135,'Envoy Gateway'),(336,65,144,'v1 / v2 / панель'),(0,10,145,'Prometheus'),(173,10,135,'Fluentd / файлы'),(336,10,144,'API / SQLite')]:
            c.setFillColor(colors.HexColor('#f2f4f0')); c.setStrokeColor(colors.HexColor('#cbd1c7'))
            c.roundRect(x,y,w,32,4,fill=1,stroke=1)
            c.setFillColor(colors.HexColor('#283426')); c.setFont('Document',9)
            c.drawCentredString(x+w/2,y+12,label)
        c.setStrokeColor(colors.HexColor('#687963'))
        for x in [145,308]:
            c.line(x,81,x+28,81); c.line(x+23,84,x+28,81); c.line(x+23,78,x+28,81)
        c.line(408,65,408,42)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--font',default=os.getenv('TRAFFICOPS_PDF_FONT')); parser.add_argument('--output',default='output/pdf/TrafficOps-passport-draft.pdf')
    args=parser.parse_args()
    if not args.font or not Path(args.font).is_file(): parser.error('--font must name a Cyrillic TTF font')
    pdfmetrics.registerFont(TTFont('Document',args.font))
    root=Path(__file__).resolve().parents[1]
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyRU',fontName='Document',fontSize=10,leading=15,spaceAfter=9,textColor=colors.HexColor('#30382d')))
    styles.add(ParagraphStyle(name='HeadingRU',fontName='Document',fontSize=15,leading=20,spaceBefore=13,spaceAfter=8))
    styles.add(ParagraphStyle(name='TitleRU',fontName='Document',fontSize=23,leading=29,spaceAfter=14))
    story=[]
    for paragraph in (root/'docs/passport.md').read_text().split('\n\n'):
        paragraph=paragraph.strip()
        if not paragraph: continue
        if paragraph.startswith('# '): story.append(Paragraph(escape(paragraph[2:]),styles['TitleRU']))
        elif paragraph.startswith('## '):
            if paragraph == '## Проверки и статус': story.append(PageBreak())
            story.append(Paragraph(escape(paragraph[3:]),styles['HeadingRU']))
            if paragraph == '## Архитектура': story.append(Diagram())
        else: story.append(Paragraph(escape(paragraph),styles['BodyRU']))
    output=root/args.output; output.parent.mkdir(parents=True,exist_ok=True)
    def footer(canvas,doc):
        canvas.setFont('Document',8); canvas.setFillColor(colors.grey)
        canvas.drawString(48,30,'TrafficOps | Черновик, live-приёмка не завершена')
        canvas.drawRightString(547,30,str(doc.page))
    SimpleDocTemplate(str(output),pagesize=(595,842),leftMargin=48,rightMargin=48,topMargin=42,bottomMargin=48).build(story,onFirstPage=footer,onLaterPages=footer)
    print(output)
if __name__ == '__main__': main()
