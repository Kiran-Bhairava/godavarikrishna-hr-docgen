import io
import copy
import os
from datetime import date, datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak, KeepTogether
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.pdfgen import canvas as rl_canvas
from pypdf import PdfReader, PdfWriter

W, H = A4

LETTERHEAD_PATH = os.getenv("LETTERHEAD_PATH", "gk_letter_head.pdf")
WATERMARK_PATH  = os.getenv("WATERMARK_PATH",  "watermark.jpeg")
PDF_OUTPUT_DIR  = os.getenv("PDF_OUTPUT_DIR",  "/tmp/generated_pdfs")


# ── Shared helpers ────────────────────────────────────────────────────────────

def _styles():
    return {
        "heading":  ParagraphStyle("heading",  fontName="Helvetica-Bold",    fontSize=12,   leading=16, alignment=TA_CENTER, spaceAfter=4),
        "subhead":  ParagraphStyle("subhead",  fontName="Helvetica-Bold",    fontSize=11,   leading=15, alignment=TA_CENTER, spaceAfter=4),
        "normal":   ParagraphStyle("normal",   fontName="Helvetica",         fontSize=10.5, leading=16, spaceAfter=6),
        "salute":   ParagraphStyle("salute",   fontName="Helvetica",         fontSize=10.5, leading=16, spaceAfter=3),
        "body":     ParagraphStyle("body",     fontName="Helvetica",         fontSize=10.5, leading=17, alignment=TA_JUSTIFY, spaceAfter=10),
        "italic":   ParagraphStyle("italic",   fontName="Helvetica-Oblique", fontSize=10,   leading=15, alignment=TA_JUSTIFY, spaceAfter=10),
        "small":    ParagraphStyle("small",    fontName="Helvetica",         fontSize=9.5,  leading=13),
        "note":     ParagraphStyle("note",     fontName="Helvetica-Bold",    fontSize=10,   leading=14),
        "annhead":  ParagraphStyle("annhead",  fontName="Helvetica-Bold",    fontSize=11,   leading=15, spaceAfter=6),
        "footer":   ParagraphStyle("footer",   fontName="Helvetica",         fontSize=9.5,  leading=13),
        "sign":     ParagraphStyle("sign",     fontName="Helvetica",         fontSize=10.5, leading=15, spaceAfter=2),
        "signbold": ParagraphStyle("signbold", fontName="Helvetica-Bold",    fontSize=10.5, leading=15),
    }


def _S(h): return Spacer(1, h * mm)


def _fmt_date(val: str) -> str:
    """Convert YYYY-MM-DD -> DD-MM-YYYY for display."""
    if not val:
        return ""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(val, fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue
    return val


def _indian_words(n: int) -> str:
    """Convert integer to Indian numbering words (Lakhs/Crores)."""
    if not n:
        return "Zero"
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def _two(n):
        return ones[n] if n < 20 else tens[n // 10] + (" " + ones[n % 10] if n % 10 else "")

    def _three(n):
        if n >= 100:
            r = ones[n // 100] + " Hundred"
            return r + (" " + _two(n % 100) if n % 100 else "")
        return _two(n)

    parts = []
    if n >= 10_000_000:
        parts.append(_three(n // 10_000_000) + " Crore"); n %= 10_000_000
    if n >= 100_000:
        parts.append(_three(n // 100_000) + " Lakh");     n %= 100_000
    if n >= 1_000:
        parts.append(_three(n // 1_000) + " Thousand");   n %= 1_000
    if n > 0:
        parts.append(_three(n))
    return " ".join(parts)


# ── Salary Grid — from New_Salary_Grid.xlsx ───────────────────────────────────
# (scale, grade, designation_hint, min_salary, max_salary)
_SALARY_GRID = [
    ("Scale IV",  "President",            "State Head in all depts",                          90500, 100000),
    ("Scale IV",  "Vice President",       "Sr.Zonal Head/HOD",                                80500,  90000),
    ("Scale IV",  "Deputy Vice President","Zonal Head/HOD",                                   75500,  80000),
    ("Scale IV",  "Asst.Vice President",  "Zonal Head/HOD",                                   70500,  75000),
    ("Scale III", "Sr.Chief Manager",     "Sr.Regional Head",                                 60500,  70000),
    ("Scale III", "Chief Manager",        "Sr.Cluster Business Head/Regional Head/Ops Head",  50500,  60000),
    ("Scale II",  "Sr.Manager",           "Cluster Business Head/Vertical Head",              40500,  50000),
    ("Scale II",  "Manager",              "Sr.Branch Manager",                                35500,  40000),
    ("Scale II",  "Deputy Manager",       "Branch Manager/Branch Incharge",                   25500,  35000),
    ("Scale II",  "Asst.Manager",         "ABM Sales/Loans/BI",                               23500,  25000),
    ("Scale I",   "Sr.Officer",           "DBH/ABM Sales/ABM L&C",                            20500,  23000),
    ("Scale I",   "Officer",              "Sr.Clerk",                                         17500,  20000),
    ("Scale I",   "Jr.Officer",           "Clerk",                                            15000,  17000),
    ("Scale I",   "Jr.Officer Trainee",   "Jr.Clerk",                                             0,      0),
    ("Scale I",   "Office Assistant",     "Peon/Facility Assistant",                          10000,  12000),
]


def _lookup_grade_scale(monthly_salary: int) -> tuple[str, str]:
    """Return (grade, scale) for a given monthly salary based on the salary grid."""
    for scale, grade, _, lo, hi in _SALARY_GRID:
        if hi == 0:
            continue   # Jr.Officer Trainee — no salary range, skip auto-match
        if lo <= monthly_salary <= hi:
            return grade, scale
    return "", ""




def _make_base_pdf() -> bytes:
    """Builds a clean base page: pure white background + faint watermark.

    New layer order (bottom to top):
      1. This base PDF  — full white + faint watermark
      2. Letterhead PDF — header/footer graphics are opaque, body is transparent
      3. Content PDF    — text and tables

    White goes UNDER the letterhead so header/footer render crisp with no tint.
    The letterhead body area is transparent so the watermark shows through cleanly.
    """
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)

    # Full white page — kills all background tint
    c.setFillColorRGB(1, 1, 1)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Faint watermark centered in body area
    if os.path.exists(WATERMARK_PATH):
        body_y      = 95
        body_height = H - 178 - 95
        wm_size = 300
        wm_x    = (W - wm_size) / 2
        wm_y    = body_y + (body_height - wm_size) / 2
        c.saveState()
        c.setFillAlpha(0.06)
        c.drawImage(WATERMARK_PATH, wm_x, wm_y,
                    width=wm_size, height=wm_size,
                    mask="auto", preserveAspectRatio=True)
        c.restoreState()

    c.save()
    return buf.getvalue()


def _frame_doc(buf, top_mm=52, bot_mm=47, left_mm=18, right_mm=18):
    """Creates document template with frame adjusted for Godavari Krishna letterhead.
    
    Top margin: 52mm (matches header image height)
    Bottom margin: 47mm (matches footer + safe buffer, default for most letters)
    Left/Right: 18mm for maximum usable content width
    """
    TOP   = top_mm  * mm
    BOT   = bot_mm  * mm
    LEFT  = left_mm * mm
    RIGHT = right_mm * mm
    CW    = W - LEFT - RIGHT
    frame = Frame(LEFT, BOT, CW, H - TOP - BOT,
                  id="main", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    tpl = PageTemplate(id="main", frames=[frame], onPage=lambda c, d: None)
    doc = BaseDocTemplate(buf, pagesize=A4, pageTemplates=[tpl])
    return doc, CW


def _dual_sign_table(cw, st,
                     left_name="Jeevan Meduri",    left_title="(The Chairman)",
                     right_name="Purnima Damarla", right_title="(Secretary General)"):
    data = [
        [Paragraph("For Godavari Krishna Co-op Society Ltd.", st["sign"]),
         Paragraph("For Godavari Krishna Co-op Society Ltd.", st["sign"])],
        [Paragraph(f"<b>{left_name}</b>",  st["signbold"]),
         Paragraph(f"<b>{right_name}</b>", st["signbold"])],
        [Paragraph(left_title,  st["sign"]),
         Paragraph(right_title, st["sign"])],
    ]
    t = Table(data, colWidths=[cw / 2, cw / 2])
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


# ── 1. Offer Letter ───────────────────────────────────────────────────────────

def _build_offer_letter(form_data: dict, date_str: str) -> bytes:
    buf = io.BytesIO()
    # top=56mm clears the real 52mm header. bot=37mm clears the real 35mm footer.
    # Page 1: letter body + required docs + signature. Page 2: Annexure-I & II.
    doc, CW = _frame_doc(buf, top_mm=56, bot_mm=32, left_mm=18, right_mm=18)
    d  = form_data
    st = _styles()

    designation = d.get("designation", "")
    try:
        monthly_salary = int(float(str(d.get("monthly_salary", 0) or 0)))
    except (ValueError, TypeError):
        monthly_salary = 0

    # All salary components auto-derived — only monthly_salary is a user input
    basic  = round(monthly_salary * 0.40)
    hra    = round(basic * 0.50)
    convey = round(basic * 0.15)
    spl    = monthly_salary - basic - hra - convey   # balancing figure
    emp_pf = 1800 if basic > 15000 else round(basic * 0.12)
    gross  = monthly_salary                           # basic+hra+convey+spl == monthly
    ctc    = gross + emp_pf
    yearly = monthly_salary * 12
    monthly_words = _indian_words(monthly_salary)
    yearly_words  = _indian_words(yearly)

    # Auto-lookup grade and scale from salary grid (override with form value if provided)
    _auto_grade, _auto_scale = _lookup_grade_scale(monthly_salary)
    grade = d.get("grade") or _auto_grade
    scale = d.get("scale") or _auto_scale

    def _fmt(v): return f"{v:,}" if v else ""

    # ── Styles — tightened to fit page 1 body + docs in one page ─────────────
    title_st  = ParagraphStyle("otitle", fontName="Helvetica-Bold", fontSize=12,
                                alignment=TA_CENTER, leading=15, spaceAfter=2,
                                underlineWidth=0.5, underline=True)
    date_st   = ParagraphStyle("odate",  fontName="Helvetica-Bold", fontSize=10.5,
                                alignment=2, leading=13, spaceAfter=3)
    to_st     = ParagraphStyle("oto",    fontName="Helvetica-Bold", fontSize=10.5,
                                leading=13, leftIndent=6, spaceAfter=1)
    name_st   = ParagraphStyle("oname",  fontName="Helvetica-Bold", fontSize=10.5,
                                leading=13, leftIndent=36, spaceAfter=4)
    body_st   = ParagraphStyle("obody",  fontName="Helvetica", fontSize=9.5,
                                alignment=TA_JUSTIFY, leading=14, leftIndent=6, spaceAfter=7)
    italic_st = ParagraphStyle("oital",  fontName="Helvetica-Oblique", fontSize=9.5,
                                alignment=TA_JUSTIFY, leading=13, leftIndent=6, spaceAfter=3)
    left_st   = ParagraphStyle("oleft",  fontName="Helvetica", fontSize=9.5,
                                alignment=TA_LEFT, leading=13, spaceAfter=7)
    ann_ttl   = ParagraphStyle("oannttl", fontName="Helvetica-Bold", fontSize=11,
                                alignment=TA_LEFT, leading=14,
                                underlineWidth=0.5, underline=True,
                                spaceAfter=3, spaceBefore=4)
    ctr_st    = ParagraphStyle("octr",   fontName="Helvetica",     fontSize=9,
                                alignment=TA_CENTER, leading=11)
    ctr_b     = ParagraphStyle("octrb",  fontName="Helvetica-Bold", fontSize=9,
                                alignment=TA_CENTER, leading=11)
    note_st   = ParagraphStyle("onote",  fontName="Helvetica-Bold", fontSize=9.5,
                                alignment=TA_LEFT, leading=13, spaceBefore=3)

    # ── Page 1: Letter body ───────────────────────────────────────────────────
    story = [
        Paragraph("<u>LETTER OF EMPLOYMENT</u>", title_st),
        # HRFlowable(width=CW, thickness=1, color=colors.HexColor("#1F3864"), spaceAfter=4),
        Paragraph(f"<b>Date: {date_str}</b>", date_st),
        Paragraph("<b>To,</b>", to_st),
        Paragraph(f"<b>Mr./Ms. {d.get('full_name', '')},</b>", name_st),
        Paragraph(
            f"In continuation of our discussions on possible employment with M/s Godavari Krishna "
            f"Co-Op Society Limited Vijayawada, we are pleased to make you an offer as "
            f"<b>{designation}</b> Initially as per the norms fixed in the Appointment letter and "
            f"Duty list. Your complete appointment letter will be processed on the date of joining "
            f"post completion of your joining formalities with Godavari Krishna Co-Operative Society Limited.",
            body_st),
        Paragraph(
            f"Your fixed remuneration will be INR <b><u>{monthly_salary:,}/-</u></b> "
            f"(in words Rupees <b><u>{monthly_words}</u></b> only) per month and INR "
            f"<b>{yearly:,}/-</b> (in words Rupees <b><u>{yearly_words}</u></b>) per annum.",
            body_st),
        Paragraph(
            "<i>(Your remuneration details are attached in Annexure – II for your reference).</i>",
            italic_st),
        Paragraph(
            "It is mandatory to achieve your monthly set target of business given by your superior, "
            "to justify your monthly fixed pay. Your career with us is based on your performance and "
            "achievement of the set business goals and Objectives of the Organization. As discussed "
            "with you during your interview, your 'Salary / Position' or maybe both will be revised "
            "after the first 6 months after you join, such revision shall be purely based on the level "
            "of your performance in these first 6 months.", body_st),
        Paragraph(
            "If the Employee wants to resign from their duties/Job role within One year of their "
            "service in such case the Employee has to serve three months of Notice Period or has to "
            "pay three months of their Salary to the Society. If the Employee wants to resign from "
            "their duties/Job role after one year of their service in such case the Employee has to "
            "serve two months of Notice Period or has to pay two months of their Salary to the Society. "
            "At the time of joining, you are advised to carry your true copies of all your credentials "
            "along with the list of documents mentioned below.", body_st),
        Paragraph(
            "You have to submit the following details for generating your employment with the Society.",
            body_st),
    ]

    # ── Required Documents — yellow header, ► bullets (still on page 1) ──────
    rq_th = ParagraphStyle("rqth", fontName="Helvetica-Bold", fontSize=10,
                            alignment=TA_CENTER, underlineWidth=0.5, underline=True)
    rq_bd = ParagraphStyle("rqbd", fontName="Helvetica", fontSize=8.5,
                            alignment=TA_JUSTIFY, leading=12, spaceAfter=3)
    ARROW = "► "

    col1 = [
        f"{ARROW}Aadhaar Card & PAN Card.",
        f"{ARROW}3 Pass Port Size Photos (White Back Ground).",
        f"{ARROW}Academic Certificates: SSC, Inter, Degree & PG if any.",
        f"{ARROW}Police Verification Certificate. (15 Days will be given to obtain this certificate and can be obtained through E Seva also).",
        f"{ARROW}Nominee Pass Port Size Photo, Aadhaar Card & PAN Card (For the sake of PF & ESI).",
        f"{ARROW}PF service history & PF passbook Statement (Available in UAN Log in).",
    ]
    col2 = [
        f"{ARROW}2 Nationalised Bank Cheques.",
        f"{ARROW}Bank A/C Passbook Xerox (Front Page) or Cancelled Cheque.",
        f"{ARROW}Previous Employment Offer Letters.",
        f"{ARROW}Play Slips: Latest 3 Months and Salary Account Statement.",
        f"{ARROW}Relieving Letter.",
        f"{ARROW}Physical fitness certificate by Govt. physician.",
    ]

    docs_tbl = Table(
        [[Paragraph("<u>Required Documents</u>", rq_th), ""],
         [[Paragraph(i, rq_bd) for i in col1], [Paragraph(i, rq_bd) for i in col2]]],
        colWidths=[CW/2, CW/2], splitByRow=1,
    )
    docs_tbl.setStyle(TableStyle([
        ("SPAN",          (0, 0), (1, 0)),
        ("BACKGROUND",    (0, 0), (1, 0),  colors.HexColor("#F5C518")),
        ("TEXTCOLOR",     (0, 0), (1, 0),  colors.HexColor("#1F3864")),
        ("BOX",           (0, 0), (-1, -1), 1.2, colors.HexColor("#1F3864")),
        ("INNERGRID",     (0, 0), (-1, -1), 0.8, colors.HexColor("#1F3864")),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))

    story += [
        _S(3),
        docs_tbl,
        Paragraph(
            "(You should submit these details within <b>7 days</b> from the date of receipt of this OFFER.)",
            left_st),
        Paragraph(
            "This is only an offer of employment and you shall communicate your acceptance of this "
            "offer within <b>3 days</b> from the receipt thereof, failing which this offer shall stand cancelled.",
            left_st),
        _S(2),
        # _dual_sign_table(CW, st),
        # Page 1 ends here — Annexures on page 2
        PageBreak(),
    ]

    # ── Page 2: Annexure-I ────────────────────────────────────────────────────
    story.append(Paragraph("<u>Annexure-I</u>", ann_ttl))
    story.append(_S(2))

    ann1 = [
        [Paragraph("Name",          ctr_st), Paragraph(d.get("full_name",""),               ctr_st)],
        [Paragraph("Designation",   ctr_st), Paragraph(designation,                          ctr_st)],
        [Paragraph("Grade",         ctr_st), Paragraph(grade,                                ctr_st)],
        [Paragraph("Scale",         ctr_st), Paragraph(d.get("scale",""),                    ctr_st)],
        [Paragraph("Department",    ctr_st), Paragraph(d.get("department",""),               ctr_st)],
        [Paragraph("Date of Birth", ctr_st), Paragraph(_fmt_date(d.get("date_of_birth","")), ctr_st)],
    ]
    ann1_tbl = Table(ann1, colWidths=[CW*0.35, CW*0.65])
    ann1_tbl.setStyle(TableStyle([
        ("BOX",           (0,0), (-1,-1), 0.8, colors.HexColor("#1F3864")),
        ("INNERGRID",     (0,0), (-1,-1), 0.4, colors.HexColor("#BDC7E0")),
        ("BACKGROUND",    (0,1), (-1,1),  colors.HexColor("#F4F5F9")),
        ("BACKGROUND",    (0,3), (-1,3),  colors.HexColor("#F4F5F9")),
        ("BACKGROUND",    (0,5), (-1,5),  colors.HexColor("#F4F5F9")),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))

    story += [ann1_tbl, _S(2)]

    # ── Annexure-II — LEFT Bold+Underline title, ALL CENTER 3-col table ──────
    story.append(Paragraph("<u>Annexure-II</u>", ann_ttl))
    story.append(_S(2))

    ann2 = [
        [Paragraph("<b>Pay Component</b>", ctr_b), Paragraph("<b>Monthly Amount</b>", ctr_b), Paragraph("<b>Annual Amount</b>", ctr_b)],
        [Paragraph("<b>Fixed</b>",         ctr_b), Paragraph(f"<b>{_fmt(monthly_salary)}</b>", ctr_b), Paragraph(f"<b>{_fmt(yearly)}</b>", ctr_b)],
        [Paragraph("Basic",                ctr_st), Paragraph(_fmt(basic),    ctr_st), Paragraph(_fmt(basic*12),   ctr_st)],
        [Paragraph("HRA",                  ctr_st), Paragraph(_fmt(hra),      ctr_st), Paragraph(_fmt(hra*12),     ctr_st)],
        [Paragraph("Conveyance Allowance", ctr_st), Paragraph(_fmt(convey),   ctr_st), Paragraph(_fmt(convey*12),  ctr_st)],
        [Paragraph("Special Allowance",    ctr_st), Paragraph(_fmt(spl),      ctr_st), Paragraph(_fmt(spl*12),     ctr_st)],
        [Paragraph("<b>Gross Salary</b>",  ctr_b),  Paragraph(f"<b>{_fmt(gross)}</b>",  ctr_b), Paragraph(f"<b>{_fmt(gross*12)}</b>",  ctr_b)],
        [Paragraph("Employer PF",          ctr_st), Paragraph(_fmt(emp_pf),   ctr_st), Paragraph(_fmt(emp_pf*12),  ctr_st)],
        [Paragraph("<b>CTC</b>",           ctr_b),  Paragraph(f"<b>{_fmt(ctc)}</b>",    ctr_b), Paragraph(f"<b>{_fmt(ctc*12)}</b>",    ctr_b)],
    ]
    c1=CW*0.42; c2=CW*0.29; c3=CW*0.29
    ann2_tbl = Table(ann2, colWidths=[c1,c2,c3])
    ann2_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#1F3864")),
        ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
        ("BACKGROUND",    (0,2), (-1,2),  colors.HexColor("#F4F5F9")),
        ("BACKGROUND",    (0,4), (-1,4),  colors.HexColor("#F4F5F9")),
        ("BACKGROUND",    (0,6), (-1,6),  colors.HexColor("#D9E1F2")),
        ("BACKGROUND",    (0,7), (-1,7),  colors.HexColor("#F4F5F9")),
        ("BACKGROUND",    (0,8), (-1,8),  colors.HexColor("#D9E1F2")),
        ("BOX",           (0,0), (-1,-1), 0.8, colors.HexColor("#1F3864")),
        ("INNERGRID",     (0,0), (-1,-1), 0.4, colors.HexColor("#BDC7E0")),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
    ]))

    story += [
        ann2_tbl, _S(2),
        Paragraph("<b>*NOTE: PF, ESI, and Professional Tax will be deducted as applicable</b>", note_st),
    ]

    doc.build(story)
    return buf.getvalue()
# ── 2. Appointment Letter ─────────────────────────────────────────────────────

def _build_appointment_letter(form_data: dict, date_str: str) -> bytes:
    buf = io.BytesIO()
    doc, CW = _frame_doc(buf)
    d  = form_data
    st = _styles()

    joining = _fmt_date(d.get("joining_date", ""))

    def _n(k):
        try: return int(float(str(d.get(k, 0) or 0)))
        except: return 0

    basic   = _n("basic")
    hra     = _n("hra")
    medical = _n("medical")
    spl     = _n("special_allowance")
    da      = _n("da")
    gross   = basic + hra + medical + spl + da
    pf      = _n("pf_deduction")
    esi     = _n("esi_deduction")
    pt      = _n("pt_deduction")
    net     = gross - pf - esi - pt

    # Acceptance block style
    acc_style = ParagraphStyle("acc", fontName="Helvetica", fontSize=10, leading=15, leftIndent=8, spaceAfter=4)
    acc_bold  = ParagraphStyle("accb", fontName="Helvetica-Bold", fontSize=10, leading=15, leftIndent=8, spaceAfter=4)
    box_ts    = TableStyle([
        ("BOX",        (0, 0), (-1, -1), 0.8, colors.HexColor("#1F3864")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
    ])

    def acceptance_block():
        inner = [
            Paragraph("<b>ACCEPTANCE</b>", acc_bold),
            Paragraph(f"I <b>{d.get('full_name', '')},</b> agree and accept the terms and conditions as contained in the Letter of Appointment. Signed and accepted.", acc_style),
            Paragraph(f"<b>Date: {date_str} &nbsp;&nbsp;&nbsp; Signature: _______________________</b>", acc_style),
            Paragraph(f"<b>Place: {d.get('branch', '')} &nbsp;&nbsp;&nbsp; (Name in BLOCK Letters): _______________________</b>", acc_style),
        ]
        t = Table([[inner]], colWidths=[CW])
        t.setStyle(box_ts)
        return t

    body_style = ParagraphStyle("body2", fontName="Helvetica", fontSize=10.5, leading=16, alignment=TA_JUSTIFY, spaceAfter=7)

    story = [
        Paragraph("LETTER OF APPOINTMENT", st["heading"]),
        HRFlowable(width=CW, thickness=0.5, color=colors.HexColor("#1F3864"), spaceAfter=8),
        _S(2),
        Paragraph(f"<b>Date:</b> {date_str}", st["normal"]),
        _S(2),
        Paragraph(f"<b>Mr./Ms. {d.get('full_name', '')},</b>", st["salute"]),
        Paragraph(f"S/o {d.get('father_name', '')},", st["salute"]),
        Paragraph(d.get("address", ""), st["salute"]),
        _S(2),
        Paragraph(f"<b>Dear {d.get('full_name', '')},</b>", st["salute"]),
        _S(1),
        Paragraph(f"<b>Employee Code – {d.get('employee_code', '')} / Branch – {d.get('branch', '')}</b>", st["normal"]),
        _S(2),
        Paragraph(
            f"We are pleased to appoint you as <b>{d.get('designation', '')}</b> post our recent discussions and meetings. "
            f"Your appointment with <b>Godavari Krishna Co-Op Society Ltd.</b> shall be effective <b>{joining}</b> in "
            f"<b>{d.get('scale', '')}</b>. Your posting shall be at <b>{d.get('branch', '')}</b>.",
            st["body"]),
        Paragraph(
            "Your appointment is subject to the Service Rules and Regulations, Code of Conduct, Policies, and existing "
            "service conditions of the Society and any other amendments thereto that may be brought into force from time "
            "to time and also contained in <b>Annexure - I</b> attached hereto.",
            st["body"]),
        Paragraph(
            "The details of your CTC are contained in <b>Annexure - II</b> attached hereto. Both these Annexures form "
            "part and parcel of this letter of appointment.",
            st["body"]),
        Paragraph(
            "We welcome you to the Society and wish you the very best in your new assignment. As a token of your acceptance "
            "of the appointment and the terms and conditions as contained therein, you are advised to sign the counterpart "
            "of this letter of appointment and return the same to the HR Department.",
            st["body"]),
        _S(3),
        Paragraph("Yours faithfully,", st["normal"]),
        _S(5),
        acceptance_block(),
        _S(6),
        HRFlowable(width=CW, thickness=0.5, color=colors.HexColor("#1F3864"), spaceBefore=2, spaceAfter=6),
        Paragraph("ANNEXURE - I", st["annhead"]),
        _S(2),
        Paragraph("The terms and conditions of your employment are as follows:", st["normal"]),
        _S(3),
        Paragraph("<b>Appointment</b>", body_style),
        Paragraph("1. Your appointment is subject to verification of your credentials, testimonials, and other particulars. In case, the information provided by you is found to be incorrect, your appointment is liable to be terminated forthwith without any notice. This offer is subject to: (a) Submission of copies of your certificates and testimonials; (b) Three passport-size photographs; (c) Last three months salary slips and relieving letter; (d) Submission of two acceptable professional references.", body_style),
        Paragraph("2. Your appointment is subject to your being medically fit. If for any reason you are unable to attend work for 180 days in the preceding twelve months, or found medically unfit, you are liable to be discharged from services.", body_style),
        Paragraph("3. The Society reserves its right to carry out formal/informal checks of your credentials with former employers or any other third parties.", body_style),
        Paragraph("<b>Probation and Confirmation</b>", body_style),
        Paragraph("4. You shall be on training for 6 Months and on probation for the next 6 Months, for a total of 12 months from date of Joining.", body_style),
        Paragraph("5. At the end of the probation period, your services may be confirmed in writing at the sole discretion of the Society.", body_style),
        Paragraph("6. The Society reserves its right to extend the probation period for a further 6 months if your services are found to be unsatisfactory.", body_style),
        Paragraph("7. You are required to perform your services as per work assigned and achieve targets communicated to you from time to time.", body_style),
        Paragraph("<b>Code of Conduct</b>", body_style),
        Paragraph("8. On your employment, you shall devote your full time and attention to your duties. You shall render services exclusively to the Society and shall not engage in any outside activity without written permission of the Society.", body_style),
        Paragraph("9. You shall use your best endeavor to promote the interest of the Society. Your conduct shall not damage the interest of the Society.", body_style),
        Paragraph("10. Your appointment is subject to the Society's Rules and Regulations, Code of Conduct, Policies, and existing service conditions as contained in the HR Handbook.", body_style),
        Paragraph("<b>Working Hours</b>", body_style),
        Paragraph("The working hours are from 9.30 a.m. to 6.30 p.m., Mondays to Saturdays, or such other hours as informed by the Management from time to time.", body_style),
        Paragraph("<b>Transfer</b>", body_style),
        Paragraph("11. Transfer is an incident and condition of service. Your services are liable to be transferred anywhere in the Society's Jurisdiction area at the sole discretion of the Society.", body_style),
        Paragraph("12. In the event of failure to report to duty at the transfer location within 3 days, the Society reserves its right to terminate your services without any notice or notice pay.", body_style),
        Paragraph("<b>Resignation</b>", body_style),
        Paragraph("13. You may resign during the training/probation period by giving 2 months' written notice or paying 2 months' salary instead of the notice period.", body_style),
        Paragraph("14. Upon confirmation, you may resign by giving not less than 2 months written notice or paying 2 months' Notice pay instead of the notice period.", body_style),
        Paragraph("<b>Termination</b>", body_style),
        Paragraph("15. The Society reserves its right to terminate your services during the probation period if your performance is found unsatisfactory, by giving 30 days' notice.", body_style),
        Paragraph("16. Upon confirmation, your services may be terminated by written notice of not less than 1 month or by paying Notice pay in lieu of notice period.", body_style),
        Paragraph("17. Your services may be terminated forthwith without notice if: (a) information submitted is found incorrect; (b) any act of dishonesty, misconduct or neglect of duty; (c) on becoming insolvent; (d) misconduct that may damage the reputation of the Society; (e) unauthorized concurrent employment.", body_style),
        Paragraph("<b>Confidential Information</b>", body_style),
        Paragraph("18. You shall keep all information received in connection with employment strictly confidential and shall not divulge or communicate the same to any person without written approval from the Society.", body_style),
        Paragraph("<b>Intellectual Property Rights</b>", body_style),
        Paragraph("19. All written work or inventions made during your engagement shall inure exclusively to the benefit of the Society. You shall not claim any proprietary interest in such inventions, discoveries, or improvements.", body_style),
        Paragraph("<b>Non-Solicitation</b>", body_style),
        Paragraph("20. Post termination of your services, you shall not solicit any of the clients or employees of the Society. This clause survives the termination of your services.", body_style),
        Paragraph("<b>Territorial Jurisdiction</b>", body_style),
        Paragraph("This letter of appointment is subject to the exclusive territorial jurisdiction of the Courts in Vijayawada.", body_style),
        _S(3),
        Paragraph("If you are willing to agree with the conditions outlined in this Letter of Appointment, please signify your receipt and acceptance and return a copy to HR.", body_style),
        Paragraph("Yours faithfully,", st["normal"]),
        _S(4),
        acceptance_block(),
        _S(8),
        HRFlowable(width=CW, thickness=0.5, color=colors.HexColor("#1F3864"), spaceBefore=2, spaceAfter=6),
        Paragraph("ANNEXURE - II  (CTC Details)", st["annhead"]),
        _S(2),
        Paragraph(
            f"Terms and conditions of your CTC as agreed between you and the Society are as below:",
            st["normal"]),
        _S(2),
        Paragraph(f"1. Your Annual CTC will be <b>Rs. {d.get('annual_ctc', '')}/-</b> (<b>{d.get('annual_ctc_words', '')}</b> only) inclusive of all statutory payments. This would be reviewed periodically.", body_style),
        Paragraph("2. Any other payments like incentives, commissions, or performance bonuses would be communicated separately in writing.", body_style),
        Paragraph("3. All payments will be subject to applicable taxes and deduction of tax at source.", body_style),
        Paragraph("4. Your salary particulars are as shown in the below table.", body_style),
        _S(2),
    ]

    cw4 = CW / 4
    ctc_data = [
        [Paragraph("<b>SALARY BREAK UP</b>", st["small"]), "", "", ""],
        [Paragraph("<b>SALARY</b>",          st["small"]), Paragraph(f"<b>{gross}</b>", st["small"]), "", ""],
        [Paragraph("BASIC",          st["small"]), Paragraph(str(basic),   st["small"]),
         Paragraph("PF",             st["small"]), Paragraph(str(pf),      st["small"])],
        [Paragraph("HRA",            st["small"]), Paragraph(str(hra),     st["small"]),
         Paragraph("ESI",            st["small"]), Paragraph(str(esi),     st["small"])],
        [Paragraph("MEDICAL",        st["small"]), Paragraph(str(medical), st["small"]),
         Paragraph("PT",             st["small"]), Paragraph(str(pt),      st["small"])],
        [Paragraph("SPL. ALLOWANCE", st["small"]), Paragraph(str(spl),     st["small"]), "", ""],
        [Paragraph("D.A.",           st["small"]), Paragraph(str(da),      st["small"]), "", ""],
        [Paragraph("<b>Total Net Salary</b>", st["small"]), Paragraph(f"<b>{net}</b>", st["small"]), "", ""],
    ]
    ctc_table = Table(ctc_data, colWidths=[cw4 * 1.5, cw4 * 0.7, cw4 * 1.1, cw4 * 0.7])
    ctc_table.setStyle(TableStyle([
        ("SPAN",       (0, 0), (3, 0)),
        ("SPAN",       (0, 1), (1, 1)), ("SPAN", (2, 1), (3, 1)),
        ("SPAN",       (0, 5), (1, 5)), ("SPAN", (2, 5), (3, 5)),
        ("SPAN",       (0, 6), (1, 6)), ("SPAN", (2, 6), (3, 6)),
        ("SPAN",       (0, 7), (1, 7)), ("SPAN", (2, 7), (3, 7)),
        ("BACKGROUND", (0, 0), (3, 0),  colors.HexColor("#D9E1F2")),
        ("BACKGROUND", (0, 7), (3, 7),  colors.HexColor("#D9E1F2")),
        ("BOX",        (0, 0), (-1, -1), 0.7, colors.HexColor("#1F3864")),
        ("INNERGRID",  (0, 0), (-1, -1), 0.4, colors.HexColor("#BDC7E0")),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
    ]))

    story += [
        ctc_table,
        _S(4),
        Paragraph("Yours faithfully,", st["normal"]),
        _S(4),
        acceptance_block(),
        _S(2),
        Paragraph("<b>NOTE:</b> PF, ESI, and Professional Tax will be deducted as applicable.", st["note"]),
    ]

    doc.build(story)
    return buf.getvalue()


# ── 3. Salary Increment Letter ────────────────────────────────────────────────

def _build_salary_increment(form_data: dict, date_str: str) -> bytes:
    buf = io.BytesIO()
    doc, CW = _frame_doc(buf)
    d  = form_data
    st = _styles()

    eff = _fmt_date(d.get("effective_date", ""))

    story = [
        Paragraph("SALARY INCREMENT LETTER", st["heading"]),
        HRFlowable(width=CW, thickness=0.5, color=colors.HexColor("#1F3864"), spaceAfter=8),
        _S(2),
        Paragraph(f"<b>Date:</b> {date_str}", st["normal"]),
        _S(2),
        Paragraph(f"<b>{d.get('full_name', '')},</b>", st["salute"]),
        Paragraph(f"{d.get('designation', '')},", st["salute"]),
        Paragraph(f"{d.get('branch', '')} Branch.", st["salute"]),
        _S(6),
        Paragraph(
            f"We Congratulate you for your hard work, enthusiasm, dedication, and continuous efforts in meeting "
            f"the organization's objectives on an efficient basis being <b>{d.get('designation', '')}</b> for the last "
            f"FY {d.get('fy', '')}. On reviewing your performance for the last FY, as a part of Appraisal program "
            f"you were granted an Increment of Rs.<b>{d.get('increment_amount', '')}/-</b> "
            f"(Rs. <b>{d.get('increment_words', '')}</b>) in your salary, where your new CTC will be "
            f"<b>{d.get('new_ctc', '')}/-</b> w.e.f <b>{eff}</b>.",
            st["body"]),
        Paragraph(
            "We look forward for your vital contributions towards the organizational growth and wishing you all "
            "the very best for your future endeavors.",
            st["body"]),
        _S(14),
        _dual_sign_table(CW, st),
    ]

    doc.build(story)
    return buf.getvalue()


# ── 4. Promotion Letter ───────────────────────────────────────────────────────

def _build_promotion_letter(form_data: dict, date_str: str) -> bytes:
    buf = io.BytesIO()
    doc, CW = _frame_doc(buf)
    d  = form_data
    st = _styles()

    eff = _fmt_date(d.get("effective_date", ""))

    story = [
        Paragraph("PROMOTION & SALARY INCREMENT LETTER", st["heading"]),
        HRFlowable(width=CW, thickness=0.5, color=colors.HexColor("#1F3864"), spaceAfter=8),
        _S(2),
        Paragraph(f"<b>Date:</b> {date_str}", st["normal"]),
        _S(2),
        Paragraph(f"<b>{d.get('full_name', '')},</b>", st["salute"]),
        Paragraph(f"{d.get('current_designation', '')},", st["salute"]),
        Paragraph(f"{d.get('branch', '')} Branch.", st["salute"]),
        _S(6),
        Paragraph(
            f"We Congratulate you for your hard work, enthusiasm, dedication, and continuous efforts in meeting "
            f"the organization's objectives on an efficient basis being <b>{d.get('current_designation', '')}</b> "
            f"for the last FY {d.get('fy', '')}. On reviewing your performance for the last FY, as a part of "
            f"Appraisal program you were promoted as <b>{d.get('new_designation', '')}</b> based at the "
            f"<b>{d.get('branch', '')} Branch</b>, and the Management has granted an Increment of "
            f"Rs.<b>{d.get('increment_amount', '')}/-</b> (Rs. <b>{d.get('increment_words', '')}</b>) in your "
            f"salary, where your new CTC will be <b>{d.get('new_ctc', '')}/-</b> w.e.f <b>{eff}</b>.",
            st["body"]),
        Paragraph(
            "We look forward for your vital contributions towards the organizational growth and wishing you all "
            "the very best for your future endeavors.",
            st["body"]),
        _S(14),
        _dual_sign_table(CW, st),
    ]

    doc.build(story)
    return buf.getvalue()


# ── 5. Relieving Letter ───────────────────────────────────────────────────────

def _build_relieving_letter(form_data: dict, date_str: str) -> bytes:
    buf = io.BytesIO()
    doc, CW = _frame_doc(buf)
    d  = form_data
    st = _styles()

    joining  = _fmt_date(d.get("joining_date", ""))
    last_day = _fmt_date(d.get("last_working_date", ""))
    dues_dt  = _fmt_date(d.get("dues_settled_date", ""))

    story = [
        Table(
            [[Paragraph(f"<b>Ref No: {d.get('ref_number', '')}</b>", st["normal"]),
              Paragraph(f"<b>Date: {date_str}</b>", ParagraphStyle("rr", fontName="Helvetica-Bold", fontSize=10.5, alignment=1))]],
            colWidths=[CW * 0.6, CW * 0.4]
        ),
        _S(2),
        Paragraph("RELIEVING CUM EXPERIENCE LETTER", st["heading"]),
        HRFlowable(width=CW, thickness=0.5, color=colors.HexColor("#1F3864"), spaceAfter=8),
        _S(2),
        Paragraph("TO WHOMSOEVER IT MAY CONCERN", st["subhead"]),
        _S(4),
        Paragraph(f"<b>{d.get('full_name', '')}</b>", ParagraphStyle("rname", fontName="Helvetica-Bold", fontSize=12, leading=16, spaceAfter=4)),
        _S(2),
        Paragraph(
            f"This letter is to formally acknowledge and confirm the acceptance of your resignation from the "
            f"position of <b>{d.get('designation', '')}</b> in the <b>{d.get('department', '')} Department</b> "
            f"at <b>{d.get('branch', '')}</b> of <b>Godavari ~ Krishna Co-Operative Society Limited</b>. "
            f"Your last working day with the society was <b>{last_day}</b>.",
            st["body"]),
        _S(2),
        Paragraph("<b>Employment Details:</b>", st["normal"]),
        _S(1),
    ]

    emp_data = [
        [Paragraph("<b>Employee Code</b>",     st["small"]), Paragraph(d.get("employee_code", ""),   st["small"])],
        [Paragraph("<b>Employment Tenure</b>", st["small"]), Paragraph(f"{joining} To {last_day}",    st["small"])],
        [Paragraph("<b>Last Drawn Salary</b>", st["small"]), Paragraph(d.get("last_drawn_salary", ""), st["small"])],
    ]
    emp_table = Table(emp_data, colWidths=[CW * 0.35, CW * 0.65])
    emp_table.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.7, colors.HexColor("#1F3864")),
        ("INNERGRID",     (0, 0), (-1, -1), 0.4, colors.HexColor("#BDC7E0")),
        ("BACKGROUND",    (0, 0), (0, -1),  colors.HexColor("#F2F5FB")),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))

    story += [
        emp_table,
        _S(4),
        Paragraph(
            f"As per our records, all dues and entitlements have been settled by <b>{dues_dt}</b>.",
            st["body"]),
        _S(12),
        Paragraph("<b>Regards,</b>", st["normal"]),
        _S(4),
        Paragraph("<b>Jeevan Meduri</b>", st["signbold"]),
        Paragraph("<b>(Chairman)</b>",    st["sign"]),
    ]

    doc.build(story)
    return buf.getvalue()


# ── Dispatcher ────────────────────────────────────────────────────────────────

_BUILDERS = {
    "offer_letter":       _build_offer_letter,
    "appointment_letter": _build_appointment_letter,
    "salary_increment":   _build_salary_increment,
    "promotion_letter":   _build_promotion_letter,
    "relieving_letter":   _build_relieving_letter,
}


def _merge_with_letterhead(content_bytes: bytes, letterhead_path: str) -> bytes:
    """Merges content PDF with letterhead on every page.

    Layer order (bottom to top):
      1. Base PDF       — pure white + faint watermark
      2. Letterhead PDF — header/footer graphics composite on top (opaque), body transparent
      3. Content PDF    — text and tables

    White goes under letterhead so header/footer are always crisp with no tint bleed.
    """
    base_bytes     = _make_base_pdf()
    content_reader = PdfReader(io.BytesIO(content_bytes))

    writer = PdfWriter()
    for content_page in content_reader.pages:
        # Start with clean white + watermark base
        base_page = PdfReader(io.BytesIO(base_bytes)).pages[0]

        # Letterhead on top — header/footer images render crisp over white
        lh_page = PdfReader(letterhead_path).pages[0]
        base_page.merge_page(lh_page)

        # Content on top
        base_page.merge_page(content_page)

        writer.add_page(base_page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def generate_pdf(
    document_id: str,
    doc_type_code: str,
    form_data: dict,
    date_str: str = None,
    letterhead_path: str = None,
    output_dir: str = None,
) -> str:
    """
    Generates a PDF for any supported document type.
    Returns the saved file path stored in documents.pdf_path.
    """
    if date_str is None:
        date_str = date.today().strftime("%d-%m-%Y")
    if letterhead_path is None:
        letterhead_path = LETTERHEAD_PATH
    if output_dir is None:
        output_dir = PDF_OUTPUT_DIR

    builder = _BUILDERS.get(doc_type_code)
    if not builder:
        raise ValueError(f"No PDF builder for doc type: {doc_type_code}")

    content_bytes = builder(form_data, date_str)
    final_bytes   = _merge_with_letterhead(content_bytes, letterhead_path)

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{document_id}.pdf")
    with open(output_path, "wb") as f:
        f.write(final_bytes)

    return output_path


# Backwards-compat alias — documents.py imports this name, no change needed there
def generate_offer_letter(document_id, form_data, date_str=None, letterhead_path=None, output_dir=None):
    return generate_pdf(document_id, "offer_letter", form_data, date_str, letterhead_path, output_dir)