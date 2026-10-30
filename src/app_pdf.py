"""Résumé PDF local d'une ou deux estimations, à partir de résultats figés."""
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

from src.app_services import LABELS, DPE_COLORS

LIMITS = ("Estimation statistique pédagogique : ne remplace pas un DPE réglementaire. "
          "Fiabilité limitée sur les logements existants et les classes F/G. "
          "Les erreurs moyennes des modèles ne sont pas des intervalles de confiance individuels. "
          "Consommation finale totale des cinq usages, sans estimation de facture.")
COMPARISON_LIMIT = "Comparer deux estimations ne démontre pas l'effet d'une rénovation : cette comparaison n'est pas une preuve causale."


def french_number(value, decimals=0):
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def estimation_pdf(records):
    if not 1 <= len(records) <= 2:
        raise ValueError("Le résumé attend une ou deux estimations")
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=(210 * mm, 297 * mm), rightMargin=19 * mm,
                           leftMargin=19 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                           title="Habitat & énergie - Résumé des estimations", author="Habitat & énergie")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Brand", fontName="Helvetica-Bold", fontSize=22, leading=28, textColor=colors.HexColor("#123e35"), spaceAfter=10))
    styles.add(ParagraphStyle(name="Sub", fontName="Helvetica-Bold", fontSize=13, leading=18, textColor=colors.HexColor("#123e35"), spaceBefore=12, spaceAfter=8))
    styles.add(ParagraphStyle(name="Copy", fontName="Helvetica", fontSize=11, leading=16, spaceAfter=7, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="SmallCopy", parent=styles["Copy"], fontSize=9, leading=13, textColor=colors.HexColor("#4a5e57")))
    def p(text, style="Copy"):
        return Paragraph(escape(str(text)), styles[style])
    story = []
    for index, record in enumerate(records):
        if index:
            story.append(PageBreak())
        story.extend([p("Habitat & énergie", "Brand"), p("Comparaison de deux logements" if len(records) == 2 else "Votre estimation", "Sub")])
        if len(records) == 2:
            delta = records[1]["consumption"] - records[0]["consumption"]
            story.append(p(f"Écart estimé (logement B - logement A) : {french_number(delta)} kWh/an."))
            story.append(p(COMPARISON_LIMIT, "SmallCopy"))
        story.append(p(record["name"], "Sub"))
        story.append(p(f"Consommation finale estimée : {french_number(record['consumption'])} kWh/an. Lettre DPE estimée : {record['label']}.", "Sub"))
        scale = Table([[letter + (" *" if letter == record["label"] else "") for letter in "ABCDEFG"]], colWidths=[24 * mm] * 7)
        commands = [("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]
        for i, color in enumerate(DPE_COLORS):
            commands.append(("BACKGROUND", (i, 0), (i, 0), colors.HexColor(color)))
            commands.append(("TEXTCOLOR", (i, 0), (i, 0), colors.white if i in [0, 6] else colors.HexColor("#102a20")))
        commands.append(("BOX", (ord(record["label"]) - 65, 0), (ord(record["label"]) - 65, 0), 2, colors.HexColor("#123e35")))
        scale.setStyle(TableStyle(commands))
        story.extend([scale, Spacer(1, 5 * mm), p("Caractéristiques prises en compte", "Sub")])
        rows = []
        for key, value in record["values"].items():
            shown = french_number(value, 2).rstrip("0").rstrip(",") if isinstance(value, float) else str(value)
            rows.append([p(LABELS[key]), p(shown)])
        table = Table(rows, colWidths=[105 * mm, 63 * mm], hAlign="LEFT")
        table.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#f1f5ef")),
                                   ("BOTTOMPADDING", (0,0), (-1,-1), 5), ("TOPPADDING", (0,0), (-1,-1), 5)]))
        story.append(table)
        story.extend([Spacer(1, 4 * mm), p("Localisation : " + record.get("location", "Saisie manuelle")),
                      p("Âge calculé avec l'année de référence 2026 ; âge nul imputé aux logements neufs.", "SmallCopy"),
                      p("Date du calcul : " + datetime.fromisoformat(record["calculated_at"]).strftime("%d/%m/%Y à %H:%M %z") + " (Europe/Paris)", "SmallCopy"),
                      p("Version des modèles : " + record["model_version"], "SmallCopy"),
                      p("Modèles de consommation et de classification distincts. La lettre n'est pas déduite de la consommation.", "SmallCopy"),
                      p("À garder en tête", "Sub"), p(LIMITS, "SmallCopy")])
    def footer(canvas, document):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#4a5e57"))
        canvas.drawString(19 * mm, 11 * mm, "Étude locale - Résultats non réglementaires")
        canvas.drawRightString(191 * mm, 11 * mm, f"{document.page} / {len(records)}")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
