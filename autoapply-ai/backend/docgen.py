import io
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

CONTACT_KEYS = ("email", "phone", "linkedin", "github", "website")


def contact_line(profile):
    return "  |  ".join(profile[k] for k in CONTACT_KEYS if profile.get(k))


def _bottom_border(paragraph):
    props = paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for key, value in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "444444")):
        bottom.set(qn(key), value)
    borders.append(bottom)
    props.append(borders)


def build_docx(profile, resume):
    doc = Document()
    page = doc.sections[0]
    page.top_margin = page.bottom_margin = Inches(0.7)
    page.left_margin = page.right_margin = Inches(0.8)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(2)

    def centered(text, size, bold=False):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = bold
        run.font.size = Pt(size)

    def heading(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        run = p.add_run(text.upper())
        run.bold = True
        run.font.size = Pt(11)
        _bottom_border(p)

    centered(profile.get("name", ""), 20, True)
    if resume.get("headline"):
        centered(resume["headline"], 11)
    if contact_line(profile):
        centered(contact_line(profile), 9.5)
    if resume.get("summary"):
        heading("Summary")
        doc.add_paragraph(resume["summary"])
    if resume.get("skills"):
        heading("Skills")
        doc.add_paragraph(", ".join(resume["skills"]))
    for section in resume.get("sections", []):
        heading(section["heading"])
        for entry in section["entries"]:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.add_run(entry["title"]).bold = True
            if entry["subtitle"]:
                p.add_run("  |  " + entry["subtitle"]).italic = True
            for bullet in entry["bullets"]:
                doc.add_paragraph(bullet, style="List Bullet")

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def build_pdf(profile, resume):
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=10, leading=13)
    name = ParagraphStyle("name", parent=base, fontName="Helvetica-Bold", fontSize=20, leading=24, alignment=TA_CENTER)
    center = ParagraphStyle("center", parent=base, alignment=TA_CENTER)
    head = ParagraphStyle("head", parent=base, fontName="Helvetica-Bold", fontSize=11, spaceBefore=8, spaceAfter=2)
    entry_style = ParagraphStyle("entry", parent=base, spaceBefore=4)

    story = [Paragraph(escape(profile.get("name", "")), name)]
    if resume.get("headline"):
        story.append(Paragraph(escape(resume["headline"]), center))
    if contact_line(profile):
        story.append(Paragraph(escape(contact_line(profile)), center))

    def heading(text):
        story.append(Paragraph(escape(text.upper()), head))
        story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#444444"), spaceAfter=3))

    if resume.get("summary"):
        heading("Summary")
        story.append(Paragraph(escape(resume["summary"]), base))
    if resume.get("skills"):
        heading("Skills")
        story.append(Paragraph(escape(", ".join(resume["skills"])), base))
    for section in resume.get("sections", []):
        heading(section["heading"])
        for entry in section["entries"]:
            line = f"<b>{escape(entry['title'])}</b>"
            if entry["subtitle"]:
                line += f"  |  <i>{escape(entry['subtitle'])}</i>"
            story.append(Paragraph(line, entry_style))
            if entry["bullets"]:
                items = [ListItem(Paragraph(escape(b), base), leftIndent=14) for b in entry["bullets"]]
                story.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=14))
    story.append(Spacer(1, 4))

    buffer = io.BytesIO()
    SimpleDocTemplate(
        buffer, pagesize=letter, leftMargin=0.8 * inch, rightMargin=0.8 * inch, topMargin=0.7 * inch, bottomMargin=0.7 * inch
    ).build(story)
    return buffer.getvalue()
