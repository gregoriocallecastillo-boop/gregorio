from io import BytesIO
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from .services import invoice_paid,invoice_status

def invoice_pdf(inv):
    buffer=BytesIO();styles=getSampleStyleSheet()
    fonts=Path(__file__).resolve().parent/'fonts'
    if 'NexoSans' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('NexoSans',str(fonts/'DejaVuSans.ttf')))
        pdfmetrics.registerFont(TTFont('NexoBold',str(fonts/'DejaVuSans-Bold.ttf')))
    for style in styles.byName.values():style.fontName='NexoBold' if style.name.startswith('Heading') or style.name=='Title' else 'NexoSans'
    styles['Normal'].fontSize=9.5;styles['Normal'].leading=14
    styles['Heading2'].fontSize=12;styles['Heading2'].leading=17
    styles['Heading3'].fontSize=10;styles['Heading3'].leading=15
    styles.add(ParagraphStyle('SmallNexo',fontName='NexoSans',fontSize=9,leading=13,textColor=colors.HexColor('#607284')))
    styles.add(ParagraphStyle('BrandNexo',fontName='NexoBold',fontSize=30,leading=36,textColor=colors.HexColor('#176b5b')))
    styles.add(ParagraphStyle('RightNexo',parent=styles['Normal'],alignment=TA_RIGHT))
    def p(s,style='Normal'):return Paragraph(escape(str(s)).replace('\n','<br/>'),styles[style])
    def money(n):return f'{n:,.2f} {inv.currency}'
    doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=40,leftMargin=40,topMargin=38,bottomMargin=55,title=inv.number,author=inv.issuer['name'])
    title='NOTA DE CRÉDITO' if inv.kind=='credit' else 'FACTURA'
    story=[p('nexo','BrandNexo'),Spacer(1,18)]
    header=Table([[p(inv.issuer['name'],'Heading2'),p(f'{title} {inv.number}','Heading2')],[p(inv.issuer.get('address',''),'SmallNexo'),p(f'Emisión: {inv.created_at:%d/%m/%Y}','SmallNexo')],[p('Identificación: '+inv.issuer.get('tax_id','Sin registrar'),'SmallNexo'),p(f'Vence: {inv.due_date:%d/%m/%Y}','SmallNexo')],[p(inv.issuer.get('email',''),'SmallNexo'),p('Moneda: '+inv.currency,'SmallNexo')]],colWidths=[295,220]);header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0)]));story.extend([header,Spacer(1,22),p('CLIENTE','Heading3'),p(inv.customer['name']),p(inv.customer.get('address',''),'SmallNexo'),p('Identificación: '+inv.customer.get('tax_id','Sin registrar'),'SmallNexo'),Spacer(1,20)])
    rows=[[p(x,'SmallNexo') for x in ['Producto','Cant.','Precio','Base','Imp.','Total']]]
    for l in inv.document.lines.all():rows.append([p(f'{l.name}\n{l.sku}','SmallNexo'),p(f'{l.quantity.normalize()} {l.unit}','SmallNexo'),p(f'{l.unit_price:,.2f}','SmallNexo'),p(f'{l.subtotal:,.2f}','SmallNexo'),p(f'{l.tax:,.2f}','SmallNexo'),p(f'{l.total:,.2f}','SmallNexo')])
    table=Table(rows,colWidths=[170,65,65,70,65,80],repeatRows=1,hAlign='LEFT');table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eaf3ef')),('LINEBELOW',(0,0),(-1,0),1,colors.HexColor('#176b5b')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#e2e8ee'))]));story.append(table)
    paid=invoice_paid(inv);status=invoice_status(inv);remaining=0 if status in ['credit','credited'] else inv.document.total-paid
    totals=Table([[p(label),p(value,'RightNexo')] for label,value in [('Base',money(inv.document.subtotal)),('Impuestos',money(inv.document.tax)),('Total',money(inv.document.total)),('Cobrado',money(paid)),('Saldo pendiente',money(remaining))]],colWidths=[300,215]);totals.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),8),('LINEABOVE',(0,2),(-1,2),1,colors.HexColor('#176b5b'))]));story.extend([Spacer(1,16),KeepTogether(totals),Spacer(1,20)])
    if inv.document.note:story.extend([p('Observaciones','Heading3'),p(inv.document.note,'SmallNexo')])
    if inv.kind=='credit':story.append(p('Documento relacionado: '+inv.document.original.invoice.number,'SmallNexo'))
    story.extend([Spacer(1,20),p('Documento comercial generado por Nexo. Sin timbrado ni autorización fiscal electrónica integrada.','SmallNexo')])
    def footer(canvas,doc):
        canvas.saveState();canvas.setFillColor(colors.HexColor('#80919f'));canvas.setFont('NexoSans',8);canvas.drawString(40,28,f'Nexo · {inv.number}');canvas.drawRightString(A4[0]-40,28,f'Página {doc.page}');canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer);return buffer.getvalue()
