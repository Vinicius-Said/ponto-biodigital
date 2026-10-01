from io import BytesIO
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from app.models.time_record import RECORD_LABELS, RECORD_TYPES
from app.services.clock import datetime_label, local_time, utc_now
from app.services.time_calculator import format_duration


FONT_ROOT = Path(__file__).resolve().parent.parent / "static" / "fonts"
BRAND_LOGO = FONT_ROOT.parent / "images" / "logo-biodigital-color.png"
pdfmetrics.registerFont(TTFont("BiodigitalSans", str(FONT_ROOT / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("BiodigitalSansBold", str(FONT_ROOT / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily(
    "BiodigitalSans",
    normal="BiodigitalSans",
    bold="BiodigitalSansBold",
    italic="BiodigitalSans",
    boldItalic="BiodigitalSansBold",
)


def clean(value):
    return escape(str(value).replace("−", "-").replace("–", "-").replace("—", "-"))


def build_pdf(reports, start, end):
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=13 * mm,
        leftMargin=13 * mm,
        topMargin=16 * mm,
        bottomMargin=17 * mm,
        title="Relatório de ponto - Biodigital",
        author="Biodigital",
    )
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = (
            "BiodigitalSansBold" if style.name in ("Title", "Heading1", "Heading2", "Heading3") else "BiodigitalSans"
        )
    styles.add(ParagraphStyle(name="ReportCell", fontName="BiodigitalSans", fontSize=8, leading=11))
    styles.add(
        ParagraphStyle(name="ReportHead", fontName="BiodigitalSansBold", fontSize=8, leading=11, textColor=colors.white)
    )
    styles.add(
        ParagraphStyle(
            name="SmallNote", fontName="BiodigitalSans", fontSize=8, leading=12, textColor=colors.HexColor("#62626b")
        )
    )
    styles.add(ParagraphStyle(name="Metric", fontName="BiodigitalSans", fontSize=10, leading=15, alignment=TA_CENTER))
    emitted = datetime_label(utc_now())

    def paragraph(value, style="ReportCell"):
        return Paragraph(clean(value), styles[style])

    def header(employee=None):
        logo = Image(str(BRAND_LOGO))
        aspect_ratio = logo.imageHeight / logo.imageWidth
        logo.drawWidth = 105
        logo.drawHeight = 105 * aspect_ratio
        title = [Paragraph("Relatório de ponto", styles["Heading2"])]
        if employee is not None:
            title.append(paragraph(f"Funcionário: {employee.name}"))
        title.append(paragraph(f"Período: {start:%d/%m/%Y} a {end:%d/%m/%Y}"))
        table = Table([[logo, title]], colWidths=[130, doc.width - 130])
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#dedee2"))
        canvas.line(doc.leftMargin, 13 * mm, landscape(A4)[0] - doc.rightMargin, 13 * mm)
        canvas.setFont("BiodigitalSans", 8)
        canvas.setFillColor(colors.HexColor("#62626b"))
        canvas.drawString(doc.leftMargin, 8 * mm, f"Biodigital | America/Sao_Paulo | Emitido em {emitted}")
        canvas.drawRightString(landscape(A4)[0] - doc.rightMargin, 8 * mm, f"Página {document.page}")
        canvas.restoreState()

    story = []
    if not reports:
        story.append(header())
        story.append(paragraph("Nenhum funcionário cadastrado para o período."))
    for index, report in enumerate(reports):
        if index:
            story.append(PageBreak())
        employee, totals = report["employee"], report["totals"]
        story.append(header(employee))
        story.append(Spacer(1, 4 * mm))
        metrics = Table(
            [
                [
                    paragraph(f"Realizado (inclui parcial): {format_duration(totals['worked'])}", "Metric"),
                    paragraph(f"Previsto: {format_duration(totals['expected'])}", "Metric"),
                    paragraph(f"Saldo apurado: {format_duration(totals['difference'], signed=True)}", "Metric"),
                    paragraph(f"Dias pendentes: {totals['pending_days']}", "Metric"),
                ]
            ],
            colWidths=[doc.width / 4] * 4,
        )
        metrics.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f4f5")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dedee2")),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.extend([metrics, Spacer(1, 5 * mm)])
        headers = [
            "Data",
            "Entrada",
            "Saída intervalo",
            "Retorno",
            "Saída",
            "Previsto",
            "Realizado",
            "Saldo",
            "Situação",
        ]
        data = [[paragraph(h, "ReportHead") for h in headers]]
        for row in report["rows"]:
            stamps = [
                local_time(row["by_type"][kind].effective_at).strftime("%H:%M:%S") if kind in row["by_type"] else "-"
                for kind in RECORD_TYPES
            ]
            data.append(
                [
                    paragraph(row["day"].strftime("%d/%m/%Y")),
                    *[paragraph(s) for s in stamps],
                    paragraph(format_duration(row["expected"])),
                    paragraph(format_duration(row["worked"])),
                    paragraph(format_duration(row["difference"], signed=True)),
                    paragraph(row["status"]),
                ]
            )
        if len(data) == 1:
            data.append([paragraph("Sem dados")] + [paragraph("-") for _ in range(8)])
        table = LongTable(
            data,
            colWidths=[doc.width * w / 100 for w in [10, 9, 11, 9, 9, 10, 10, 10, 22]],
            repeatRows=1,
            hAlign="LEFT",
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#202024")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f6f7")]),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#dedee2")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 3 * mm))
        story.append(
            paragraph(
                "Saldo apurado soma somente dias concluídos, folgas e dias passados sem registro. Dias incompletos, em andamento ou sem jornada ficam pendentes. Atraso e diferença são informações de acompanhamento conforme a jornada cadastrada.",
                "SmallNote",
            )
        )
        if report["corrections"]:
            story.append(Paragraph("Histórico de correções", styles["Heading2"]))
            correction_data = [
                [
                    paragraph(h, "ReportHead")
                    for h in ["Data / marcação", "Anterior", "Solicitado", "Situação / decisão", "Motivo"]
                ]
            ]
            for correction in report["corrections"]:
                correction_data.append(
                    [
                        paragraph(f"{correction.work_date:%d/%m/%Y} - {RECORD_LABELS[correction.requested_type]}"),
                        paragraph(datetime_label(correction.previous_value)),
                        paragraph(datetime_label(correction.requested_value)),
                        paragraph(
                            f"{correction.status} | {correction.reviewer.username if correction.reviewer else '-'} | {datetime_label(correction.reviewed_at)} | {correction.review_reason or '-'}"
                        ),
                        paragraph(correction.reason),
                    ]
                )
            corrections_table = LongTable(
                correction_data, colWidths=[doc.width * w / 100 for w in [20, 15, 15, 25, 25]], repeatRows=1
            )
            corrections_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#202024")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#dedee2")),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(corrections_table)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
