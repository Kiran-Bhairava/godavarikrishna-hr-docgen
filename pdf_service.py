import io
import copy
import os
from datetime import date, datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable
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


def _make_white_mask_pdf() -> bytes:
    """White mask over content area + watermark.jpeg centered on top.
    Matches the live preview: faint hibiscus flower centered in the body.
    The image is already pre-faded, drawn at alpha 0.55 to match browser preview.
    """
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)

    # White mask — wipes the letterhead's own background in the content band
    mask_y      = 128   # pts from bottom (45mm footer)
    mask_height = 572   # pts content area
    c.setFillColorRGB(1, 1, 1)
    c.rect(30, mask_y, W - 60, mask_height, fill=1, stroke=0)

    # Draw watermark.jpeg centered in the content area — matches live preview
    if os.path.exists(WATERMARK_PATH):
        wm_size = 340   # pts (~120mm), visually matches preview
        wm_x    = (W - wm_size) / 2
        wm_y    = mask_y + (mask_height - wm_size) / 2
        c.saveState()
        c.setFillAlpha(0.55)
        c.drawImage(WATERMARK_PATH, wm_x, wm_y,
                    width=wm_size, height=wm_size,
                    mask="auto", preserveAspectRatio=True)
        c.restoreState()

    c.save()
    return buf.getvalue()


def _frame_doc(buf, top_mm=52, bot_mm=47, left_mm=22, right_mm=22):
    """Creates document template with frame adjusted for Godavari Krishna letterhead.
    
    Top margin: 52mm (50mm header + 2mm buffer)
    Bottom margin: 47mm (45mm footer + 2mm buffer)
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
    doc, CW = _frame_doc(buf)
    d  = form_data
    st = _styles()

    designation    = d.get("designation", "")
    monthly_salary = d.get("monthly_salary", "")
    monthly_words  = d.get("monthly_salary_words", "")
    yearly_words   = d.get("yearly_salary_words", "")
    try:
        yearly = int(float(str(monthly_salary))) * 12
    except (ValueError, TypeError):
        yearly = 0

    story = [
        Paragraph("LETTER OF EMPLOYMENT", st["heading"]),
        HRFlowable(width=CW, thickness=0.5, color=colors.HexColor("#1F3864"), spaceAfter=8),
        _S(2),
        Paragraph(f"<b>Date:</b> {date_str}", st["normal"]),
        _S(1),
        Paragraph("To,", st["salute"]),
        Paragraph(f"<b>Mr./Ms. {d.get('full_name', '')},</b>", st["salute"]),
        _S(4),
        Paragraph(
            f"In continuation of our discussions on possible employment with M/s Godavari Krishna "
            f"Co-Op Society Limited Vijayawada, we are pleased to make you an offer as "
            f"<b>{designation}</b> Initially as per the norms fixed in the Appointment letter and "
            f"Duty list.  Your complete appointment letter will be processed on the date of joining "
            f"post completion of your joining formalities with Godavari Krishna Co-Operative Society Limited.",
            st["body"]),
        Paragraph(
            f"Your fixed remuneration will be INR <b>{monthly_salary}/-</b> "
            f"(in words Rupees <b>{monthly_words}</b> only) per month and INR <b>{yearly}/-</b> "
            f"(in words Rupees <b>{yearly_words}</b> only) per annum.",
            st["body"]),
        Paragraph(
            "<i>(Your remuneration details are attached in <b>Annexure - I</b> for your reference).</i>",
            st["italic"]),
        Paragraph(
            "It is mandatory to achieve your monthly set target of business given by your superior, "
            "to justify your monthly fixed pay. Your career with us is based on your performance and "
            "achievement of the set business goals and Objectives of the Organization. As discussed "
            "with you during your interview, your 'Salary / Position' or maybe both will be revised "
            "after the first 6 months after you join, such revision shall be purely based on the level "
            "of your performance in these first 6 months.",
            st["body"]),
        Paragraph(
            "If the Employee wants to resign from their duties/Job role within One year of their "
            "service in such case the Employee has to serve three months of Notice Period or has to "
            "pay three months of their Salary to the Society. If the Employee wants to resign from "
            "their duties/Job role after one year of their service in such case the Employee has to "
            "serve two months of Notice Period or has to pay two months of their Salary to the Society. "
            "At the time of joining, you are advised to carry your true copies of all your credentials "
            "along with the list of documents mentioned below.",
            st["body"]),
        Paragraph(
            "You have to submit the following details for generating your employment with the Society.",
            st["normal"]),
        _S(3),
    ]

    # ── Required Documents table — yellow header, ➤ bullets, JUSTIFY ───────────
    # Use one row with two cells (each containing all items) so it can page-break
    rq_th_st = ParagraphStyle("rqth", fontName="Helvetica-Bold", fontSize=10.5,
                               alignment=TA_CENTER,
                               underlineWidth=0.5, underline=True)
    rq_body  = ParagraphStyle("rqbody", fontName="Helvetica", fontSize=9.8,
                               alignment=TA_JUSTIFY, leading=16, spaceAfter=0)

    ARROW = "► "   # ➤ solid right arrow

    col1_items = [
        f"{ARROW}Aadhaar Card & PAN Card.",
        f"{ARROW}3 Pass Port Size Photos (White Back Ground).",
        f"{ARROW}Academic Certificates: SSC, Inter, Degree & PG if any.",
        f"{ARROW}Police Verification Certificate. (15 Days will be given to obtain this certificate and can be obtained through E Seva also).",
        f"{ARROW}Nominee Pass Port Size Photo, Aadhaar Card & PAN Card (For the sake of PF & ESI).",
        f"{ARROW}PF service history & PF passbook Statement (Available in UAN Log in).",
    ]
    col2_items = [
        f"{ARROW}2 Nationalised Bank Cheques.",
        f"{ARROW}Bank A/C Passbook Xerox (Front Page) or Cancelled Cheque.",
        f"{ARROW}Previous Employment Offer Letters.",
        f"{ARROW}Play Slips: Latest 3 Months and Salary Account Statement.",
        f"{ARROW}Relieving Letter.",
        f"{ARROW}Physical fitness certificate by Govt. physician.",
    ]

    def _bullet_cell(items):
        """Each item as its own Paragraph so they wrap and justify correctly."""
        return [Paragraph(item, rq_body) for item in items]

    doc_table = Table(
        [[Paragraph("<u>Required Documents</u>", rq_th_st), ""],
         [_bullet_cell(col1_items), _bullet_cell(col2_items)]],
        colWidths=[CW / 2, CW / 2],
        splitByRow=1,          # allow page break inside the table
    )
    doc_table.setStyle(TableStyle([
        ("SPAN",          (0, 0), (1, 0)),
        ("BACKGROUND",    (0, 0), (1, 0),  colors.HexColor("#F5C518")),  # yellow
        ("TEXTCOLOR",     (0, 0), (1, 0),  colors.HexColor("#1F3864")),  # navy text
        ("BOX",           (0, 0), (-1, -1), 1.2, colors.HexColor("#1F3864")),
        ("INNERGRID",     (0, 0), (-1, -1), 0.8, colors.HexColor("#1F3864")),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))

    story += [
        doc_table,
        _S(3),
        Paragraph(
            "<i>(You should submit these details within <b>7 days</b> from the date of receipt of this OFFER.)</i>",
            st["footer"]),
        _S(3),
        Paragraph(
            "This is only an offer of employment and you shall communicate your acceptance of this "
            "offer within <b>3 days</b> from the receipt thereof, failing which this offer shall stand cancelled.",
            st["body"]),
        _S(6),
        HRFlowable(width=CW, thickness=0.5, color=colors.HexColor("#1F3864"), spaceBefore=2, spaceAfter=6),
        Paragraph("Annexure - I", st["annhead"]),
        _S(2),
    ]

    adata = [
        [Paragraph("<b>Name</b>",          st["small"]), Paragraph(d.get("full_name", ""),               st["small"])],
        [Paragraph("<b>Designation</b>",   st["small"]), Paragraph(designation,                           st["small"])],
        [Paragraph("<b>Grade</b>",         st["small"]), Paragraph(d.get("grade", ""),                    st["small"])],
        [Paragraph("<b>Department</b>",    st["small"]), Paragraph(d.get("department", ""),               st["small"])],
        [Paragraph("<b>Date of Birth</b>", st["small"]), Paragraph(_fmt_date(d.get("date_of_birth", "")), st["small"])],
        [Paragraph("<b>Father Name</b>",   st["small"]), Paragraph(d.get("father_name", ""),              st["small"])],
    ]
    ann_table = Table(adata, colWidths=[CW * 0.32, CW * 0.68])
    ann_table.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.7, colors.HexColor("#1F3864")),
        ("INNERGRID",     (0, 0), (-1, -1), 0.4, colors.HexColor("#BDC7E0")),
        ("BACKGROUND",    (0, 0), (0, -1),  colors.HexColor("#F2F5FB")),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))

    story += [
        ann_table,
        _S(4),
        Paragraph("<b>NOTE:</b> PF, ESI, and Professional Tax will be deducted as applicable.", st["note"]),
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
    
    Process for each page:
    1. Get fresh copy of letterhead page
    2. Apply white mask to block watermark in content area
    3. Merge content page on top
    """
    mask_bytes     = _make_white_mask_pdf()
    lh_reader      = PdfReader(letterhead_path)
    mask_reader    = PdfReader(io.BytesIO(mask_bytes))
    content_reader = PdfReader(io.BytesIO(content_bytes))

    writer = PdfWriter()
    for content_page in content_reader.pages:
        # Get fresh letterhead page (not a copy - read it fresh each time)
        lh_page = PdfReader(letterhead_path).pages[0]
        
        # Apply mask
        lh_page.merge_page(mask_reader.pages[0])
        
        # Apply content
        lh_page.merge_page(content_page)
        
        # Add to output
        writer.add_page(lh_page)

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