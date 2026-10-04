#!/usr/bin/env python3
"""Build the project passport; requires ReportLab, never used by deployment."""
import argparse
import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Flowable, PageBreak, Paragraph, SimpleDocTemplate,
                               Spacer, Table, TableStyle)

INK = colors.HexColor('#243343')
ACCENT = colors.HexColor('#245e77')


class Diagram(Flowable):
    """Actual request, telemetry and controller dependency paths."""
    def __init__(self):
        super().__init__()
        self.width, self.height = 499, 190

    def draw(self):
        c = self.canv
        nodes = {
            'browser': (184, 159, 130, 'Browser'),
            'gateway': (159, 117, 180, 'Envoy / Gateway API'),
            'controller': (0, 69, 155, 'Controller + panel'),
            'v1': (196, 69, 110, 'demo-v1'),
            'v2': (349, 69, 110, 'demo-v2'),
            'prom': (188, 0, 120, 'Prometheus'),
            'logs': (337, 0, 162, 'Fluentd → log files'),
            'state': (0, 0, 155, 'SQLite / Kubernetes API'),
        }
        def arrow(x1, y1, x2, y2):
            import math
            c.setStrokeColor(ACCENT)
            c.line(x1, y1, x2, y2)
            a = math.atan2(y2-y1, x2-x1)
            for delta in (-0.5, 0.5):
                c.line(x2, y2, x2-5*math.cos(a+delta), y2-5*math.sin(a+delta))
        arrow(249, 159, 249, 145)
        for x in (77, 251, 404):
            c.line(249, 117, 249, 105)
            c.line(77, 105, 404, 105)
            arrow(x, 105, x, 97)
        for x in (251, 404):
            arrow(x, 69, 248, 28)
            arrow(x, 69, 418, 28)
        arrow(77, 69, 77, 28)
        arrow(155, 83, 180, 83)
        c.line(180, 83, 180, 40)
        arrow(180, 40, 248, 28)
        c.line(155, 75, 168, 75)
        c.line(168, 75, 168, 34)
        arrow(168, 34, 418, 28)
        for x, y, w, label in nodes.values():
            c.setFillColor(colors.HexColor('#f1f5f7'))
            c.setStrokeColor(colors.HexColor('#c8d4dc'))
            c.roundRect(x, y, w, 28, 4, fill=1, stroke=1)
            c.setFillColor(INK)
            c.setFont('Document', 9)
            c.drawCentredString(x+w/2, y+10, label)
        c.setFont('Document', 8)
        c.drawString(195, 48, 'metrics / logs')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--font', default=os.getenv('TRAFFICOPS_PDF_FONT'))
    parser.add_argument('--output', default='output/pdf/Паспорт.pdf')
    args = parser.parse_args()
    if not args.font or not Path(args.font).is_file():
        parser.error('--font must name a Cyrillic TTF font')
    pdfmetrics.registerFont(TTFont('Document', args.font))
    root = Path(__file__).resolve().parents[1]
    body = ParagraphStyle('Body', fontName='Document', fontSize=10,
                          leading=14, spaceAfter=8, textColor=INK)
    h2 = ParagraphStyle('Heading', parent=body, fontSize=15, leading=19,
                        spaceBefore=10, spaceAfter=8, textColor=ACCENT,
                        keepWithNext=True)
    h3 = ParagraphStyle('Subheading', parent=body, fontSize=11, leading=15,
                        spaceBefore=7, spaceAfter=4, textColor=ACCENT,
                        keepWithNext=True)
    title = ParagraphStyle('Title', parent=h2, fontSize=29, leading=35)
    cell = ParagraphStyle('Cell', parent=body, fontSize=9, leading=12, spaceAfter=0)
    def para(text, style=body):
        return Paragraph(escape(text.replace('`', '')), style)
    story = []
    for block in (root/'docs/passport.md').read_text().split('\n\n'):
        block = block.strip()
        if not block:
            continue
        if block.startswith('| '):
            rows = []
            for line in block.splitlines():
                if line.startswith('| ---'):
                    continue
                rows.append([para(t.strip(), cell) for t in line.strip('|').split('|')])
            table = Table(rows, colWidths=[165, 137, 197], hAlign='LEFT')
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e6eef3')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 7),
                ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                ('TOPPADDING', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
                ('LINEBELOW', (0, 0), (-1, -1), 0.4, colors.HexColor('#c8d4dc')),
            ]))
            story.extend([table, Spacer(1, 5)])
        elif block.startswith('# '):
            story.append(para(block[2:], title))
        elif block.startswith('## '):
            heading = block[3:]
            if heading in ('Обязательная часть', 'Инженерное ревью'):
                story.append(PageBreak())
            story.append(para(heading, h2))
            if heading == 'Схема потоков':
                story.extend([Diagram(), Spacer(1, 8)])
        elif block.startswith('### '):
            story.append(para(block[4:], h3))
        else:
            story.append(para(block))
    output = root/args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    def footer(canvas, doc):
        canvas.setStrokeColor(colors.HexColor('#c8d4dc'))
        canvas.line(48, 43, 547, 43)
        canvas.setFont('Document', 8)
        canvas.setFillColor(INK)
        canvas.drawString(48, 29, 'TrafficOps | MTC ENGINEER HACK')
        canvas.drawRightString(547, 29, str(doc.page))
    SimpleDocTemplate(str(output), pagesize=(595, 842), leftMargin=48,
                      rightMargin=48, topMargin=35, bottomMargin=55,
                      title='TrafficOps', author='TrafficOps').build(
                          story, onFirstPage=footer, onLaterPages=footer)
    print(output)


if __name__ == '__main__':
    main()
