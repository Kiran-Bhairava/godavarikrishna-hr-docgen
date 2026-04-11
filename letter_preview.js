/**
 * letter_preview.js
 * Generates a full styled HTML string for any GK document type.
 * Used to render a live preview inside an iframe in both admin and recruiter dashboards.
 */

const LetterPreview = (() => {

  const NAVY  = "#1F3864";
  const GOLD  = "#F5C518";
  const MUTED = "#6b7280";
  const BORDER= "#dde3f0";

  // ── Image cache: fetched once as base64, reused on every render ─────────────
  const _imgCache = { header: null, footer: null, watermark: null };

  async function _toBase64(url) {
    const res  = await fetch(url);
    const blob = await res.blob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload  = () => resolve(reader.result); // data:image/jpeg;base64,...
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  // Internal promise — set by preloadImages(), awaited by renderAsync()
  let _readyPromise = null;

  /**
   * Call ONCE at page load. Returns a promise; stores it internally so
   * renderAsync() can wait for it even if called before images finish loading.
   */
  function preloadImages() {
    _readyPromise = Promise.all([
      _toBase64("/gk_header.jpeg"),
      _toBase64("/gk_footer.jpeg"),
      _toBase64("/watermark.jpeg"),
    ]).then(([header, footer, watermark]) => {
      _imgCache.header    = header;
      _imgCache.footer    = footer;
      _imgCache.watermark = watermark;
    });
    return _readyPromise;
  }

  /**
   * Async version of render — waits for images to be cached first.
   * Use this in refreshPreview() so watermark is ALWAYS embedded.
   */
  async function renderAsync(doc) {
    if (_readyPromise) await _readyPromise;
    return render(doc);
  }

  function fmtDate(val) {
    if (!val) return "";
    // Convert YYYY-MM-DD → DD-MM-YYYY
    const m = String(val).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (m) return `${m[3]}-${m[2]}-${m[1]}`;
    return val;
  }

  function today() {
    const d = new Date();
    return `${String(d.getDate()).padStart(2,"0")}-${String(d.getMonth()+1).padStart(2,"0")}-${d.getFullYear()}`;
  }

  // ── A4 Page simulation — exact match to pdf_service.py layout ───────────────
  // PDF margins: top=56mm, bot=32mm, left=18mm, right=18mm
  // Each "page" div is A4 (210×297mm) with header/footer images and content frame.
  // Page 1: letter body + required docs  |  Page 2: Annexure-I + Annexure-II
  function wrapPages(page1Html, page2Html) {
    const pageStyle = `
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');
      *{box-sizing:border-box;margin:0;padding:0}
      html,body{background:#e8ebf4;font-family:Helvetica,Arial,sans-serif;
                overflow-x:hidden;width:100%}

      /* A4 page shell — fluid width, scales to iframe container */
      .page{
        width:100%;
        background:#fff;
        position:relative;
        display:flex; flex-direction:column;
        margin:0 0 8px 0;
        box-shadow:0 4px 32px rgba(31,56,100,0.18);
        overflow:hidden;
        page-break-after:always;
      }

      /* Header image — full width, ~56mm tall */
      .lh-header{width:100%;display:block;flex-shrink:0}
      .lh-header img{width:100%;height:auto;display:block}

      /* Content frame — mirrors pdf frame: left/right ~8.5% (18mm of 210mm), top/bottom small */
      .lh-body{
        flex:1;
        padding:1.5% 8.5% 2% 8.5%;
        position:relative;
        overflow:hidden;
      }

      /* Watermark — centered in body, very faint, matches pdf alpha=0.06 */
      .wm{
        position:absolute;
        top:50%;left:50%;
        transform:translate(-50%,-50%);
        width:35%;height:35%;
        opacity:0.06;
        pointer-events:none;z-index:0;
        object-fit:contain;
      }
      .lh-body>:not(.wm){position:relative;z-index:1}

      /* Footer image — full width, ~32mm, pinned to bottom */
      .lh-footer{width:100%;display:block;flex-shrink:0;margin-top:auto}
      .lh-footer img{width:100%;height:auto;display:block}

      /* ── Typography — mirrors pdf_service styles exactly ── */
      /* title_st: Helvetica-Bold 12pt, CENTER, underline, spaceAfter=2 */
      .doc-title{
        font-size:12pt;font-weight:700;text-align:center;color:#1F3864;
        text-decoration:underline;text-underline-offset:2px;
        letter-spacing:.04em;margin-bottom:3pt;
      }
      /* date_st: Helvetica-Bold 10.5pt, RIGHT, spaceAfter=3 */
      .date-line{font-size:10.5pt;font-weight:700;text-align:right;margin-bottom:4pt}
      /* to_st: Helvetica-Bold 10.5pt, leftIndent=6, spaceAfter=1 */
      .to-line{font-size:10.5pt;font-weight:700;margin-bottom:1pt;padding-left:6pt}
      /* name_st: Helvetica-Bold 10.5pt, leftIndent=6, spaceAfter=4 — aligns under To, */
      .name-line{font-size:10.5pt;font-weight:700;padding-left:6pt;margin-bottom:5pt}
      /* body_st: Helvetica 9.5pt, JUSTIFY, leading=14, leftIndent=6, spaceAfter=7 */
      .body-p{
        font-size:9.5pt;line-height:14pt;text-align:justify;
        padding-left:6pt;margin-bottom:7pt;
      }
      /* italic_st: Helvetica-Oblique 9.5pt, JUSTIFY, leading=13, spaceAfter=3 */
      .italic-p{
        font-size:9.5pt;line-height:13pt;text-align:justify;font-style:italic;
        padding-left:6pt;margin-bottom:3pt;
      }
      /* left_st: Helvetica 9.5pt, LEFT, leading=13, spaceAfter=7 */
      .left-p{font-size:9.5pt;line-height:13pt;text-align:left;margin-bottom:7pt}
      /* ann_ttl: Helvetica-Bold 11pt, LEFT, underline, spaceAfter=3, spaceBefore=4 */
      .ann-title{
        font-size:11pt;font-weight:700;text-align:left;color:#1F3864;
        text-decoration:underline;text-underline-offset:2px;
        margin-top:4pt;margin-bottom:3pt;
      }
      /* ctr_st: Helvetica 9pt, CENTER, leading=11 */
      /* ctr_b:  Helvetica-Bold 9pt, CENTER, leading=11 */
      /* note_st: Helvetica-Bold 9.5pt, LEFT */
      .note{font-size:9.5pt;font-weight:700;text-align:left;margin-top:3pt}

      /* Required docs table */
      .docs-table{
        width:100%;border-collapse:collapse;margin-top:3pt;margin-bottom:0;
        font-size:8.5pt;
      }
      .docs-table th{
        background:#F5C518;color:#1F3864;text-align:center;
        padding:4pt 6pt;font-size:10pt;font-weight:700;
        text-decoration:underline;border:1.2pt solid #1F3864;
      }
      .docs-table td{
        border:0.8pt solid #1F3864;padding:6pt 6pt;
        vertical-align:top;text-align:justify;
        line-height:11pt;width:50%;
      }

      /* Annexure tables */
      .ann1-table{width:100%;border-collapse:collapse;margin-bottom:4pt;font-size:9pt}
      .ann1-table td{
        border:0.8pt solid #BDC7E0;padding:3pt 4pt;text-align:center;vertical-align:middle;
      }
      .ann1-table tr:nth-child(even) td{background:#F4F5F9}
      .ann1-table td:first-child{width:35%;background:#F4F5F9}

      .ann2-table{width:100%;border-collapse:collapse;margin-bottom:4pt;font-size:9pt}
      .ann2-table th{
        background:#87CEEB;color:#1F3864;padding:3pt 6pt;
        text-align:center;border:0.8pt solid #0094da;font-size:9pt;font-weight:700;
      }
      .ann2-table td{
        border:0.8pt solid #BDC7E0;padding:3pt 6pt;
        text-align:center;vertical-align:middle;font-size:9pt;
      }
      .ann2-table .row-fixed td{font-weight:700}
      .ann2-table .row-alt td{background:#F4F5F9}
      .ann2-table .row-gross td{background:#D9E1F2;font-weight:700}
      .ann2-table .row-empf td{background:#F4F5F9}
      .ann2-table .row-ctc td{background:#D9E1F2;font-weight:700}

      b{font-weight:700}
      u{text-decoration:underline}
      i,em{font-style:italic}
    `;

    const pageTemplate = (bodyHtml, isFirstPage) => `
    <div class="page">
      <div class="lh-header">
        <img src="${_imgCache.header || '/gk_header.jpeg'}" alt="GK Letterhead"/>
      </div>
      <div class="lh-body">
        <img class="wm" src="${_imgCache.watermark || '/watermark.jpeg'}" alt=""/>
        ${bodyHtml}
      </div>
      <div class="lh-footer">
        <img src="${_imgCache.footer || '/gk_footer.jpeg'}" alt=""/>
      </div>
    </div>`;

    return `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>${pageStyle}</style>
</head>
<body style="margin:0;padding:0;background:#e8ebf4">
${pageTemplate(page1Html, true)}
${page2Html ? pageTemplate(page2Html, false) : ''}
</body>
</html>`;
  }

  // Single-page wrap for letters that don't need 2 pages (appointment etc.)
  function wrap(bodyHtml) {
    return wrapPages(bodyHtml, null);
  }

    // ── Dual signature block ───────────────────────────────────────────────────
  function sigBlock() {
    return `<div class="sig-row">
      <div class="sig-col">
        <div class="sig-org">For Godavari Krishna Co-op Society Ltd.</div>
        <div class="sig-name">Jeevan Meduri</div>
        <div class="sig-title">(The Chairman)</div>
      </div>
      <div class="sig-col" style="text-align:right">
        <div class="sig-org">For Godavari Krishna Co-op Society Ltd.</div>
        <div class="sig-name">Purnima Damarla</div>
        <div class="sig-title">(Secretary General)</div>
      </div>
    </div>`;
  }

  // ── Indian number words (mirrors pdf_service._indian_words) ────────────────
  function indianWords(n) {
    if (!n) return "Zero";
    const ones = ["","One","Two","Three","Four","Five","Six","Seven","Eight","Nine",
                  "Ten","Eleven","Twelve","Thirteen","Fourteen","Fifteen","Sixteen",
                  "Seventeen","Eighteen","Nineteen"];
    const tens = ["","","Twenty","Thirty","Forty","Fifty","Sixty","Seventy","Eighty","Ninety"];
    function two(n)   { return n < 20 ? ones[n] : tens[Math.floor(n/10)] + (n%10 ? " "+ones[n%10] : ""); }
    function three(n) { return n>=100 ? ones[Math.floor(n/100)]+" Hundred"+(n%100?" "+two(n%100):"") : two(n); }
    const parts = [];
    if (n >= 10000000) { parts.push(three(Math.floor(n/10000000))+" Crore"); n %= 10000000; }
    if (n >= 100000)   { parts.push(three(Math.floor(n/100000))+" Lakh");    n %= 100000; }
    if (n >= 1000)     { parts.push(three(Math.floor(n/1000))+" Thousand");  n %= 1000; }
    if (n > 0)         { parts.push(three(n)); }
    return parts.join(" ");
  }

  // ── Salary Grid — mirrors _SALARY_GRID in pdf_service.py ──────────────────
  const SALARY_GRID = [
    { scale: "Scale IV",  grade: "President",             min: 90500, max: 100000 },
    { scale: "Scale IV",  grade: "Vice President",        min: 80500, max:  90000 },
    { scale: "Scale IV",  grade: "Deputy Vice President", min: 75500, max:  80000 },
    { scale: "Scale IV",  grade: "Asst.Vice President",   min: 70500, max:  75000 },
    { scale: "Scale III", grade: "Sr.Chief Manager",      min: 60500, max:  70000 },
    { scale: "Scale III", grade: "Chief Manager",         min: 50500, max:  60000 },
    { scale: "Scale II",  grade: "Sr.Manager",            min: 40500, max:  50000 },
    { scale: "Scale II",  grade: "Manager",               min: 35500, max:  40000 },
    { scale: "Scale II",  grade: "Deputy Manager",        min: 25500, max:  35000 },
    { scale: "Scale II",  grade: "Asst.Manager",          min: 23500, max:  25000 },
    { scale: "Scale I",   grade: "Sr.Officer",            min: 20500, max:  23000 },
    { scale: "Scale I",   grade: "Officer",               min: 17500, max:  20000 },
    { scale: "Scale I",   grade: "Jr.Officer",            min: 15000, max:  17000 },
    { scale: "Scale I",   grade: "Office Assistant",      min: 10000, max:  12000 },
  ];

  function lookupGradeScale(salary) {
    const s = Number(salary) || 0;
    const row = SALARY_GRID.find(r => s >= r.min && s <= r.max);
    return row ? { grade: row.grade, scale: row.scale } : { grade: "", scale: "" };
  }

  // ── Salutation — mirrors pdf_service._salutation ──────────────────────────
  function salutation(gender, maritalStatus) {
    const g = (gender || "").trim().toLowerCase();
    const m = (maritalStatus || "").trim().toLowerCase();
    if (g === "male")   return "Mr.";
    if (g === "female") return (m === "married" || m === "divorced") ? "Mrs." : "Ms.";
    return "Mx.";
  }

  // ── 1. Offer Letter — 2 pages, pixel-perfect match to pdf_service.py ───────
  function offerLetter(d, dateStr) {
    const ms     = Math.round(Number(d.monthly_salary) || 0);
    const basic  = Math.round(ms * 0.40);
    const hra    = Math.round(basic * 0.50);
    const convey = Math.round(basic * 0.15);
    const spl    = ms - basic - hra - convey;
    const empPF  = basic > 15000 ? 1800 : Math.round(basic * 0.12);
    const gross  = ms;
    const ctc    = gross + empPF;
    const yearly = ms * 12;

    const monthlyWords = indianWords(ms);
    const yearlyWords  = indianWords(yearly);

    const _gs   = lookupGradeScale(ms);
    const grade = d.grade || _gs.grade;
    const scale = d.scale || _gs.scale;
    const sal   = salutation(d.gender, d.marital_status);

    function fmt(v) { return v ? Number(v).toLocaleString("en-IN") : ""; }

    // ── PAGE 1: Letter body + Required Documents ──────────────────────────────
    const page1 = `
      <div class="doc-title">LETTER OF EMPLOYMENT</div>
      <div class="date-line">Date: ${dateStr}</div>
      <div class="to-line">To,</div>
      <div class="name-line">${sal} ${d.full_name || ""},</div>

      <p class="body-p">In continuation of our discussions on possible employment with M/s Godavari Krishna Co-Op Society Limited Vijayawada, we are pleased to make you an offer as <b>${d.designation || ""}</b> Initially as per the norms fixed in the Appointment letter and Duty list. Your complete appointment letter will be processed on the date of joining post completion of your joining formalities with Godavari Krishna Co-Operative Society Limited.</p>

      <p class="body-p">Your fixed remuneration will be INR <b><u>${fmt(ms)}/-</u></b> (in words Rupees <b><u>${monthlyWords}</u></b> only) per month and INR <b>${fmt(yearly)}/-</b> (in words Rupees <b><u>${yearlyWords}</u></b>) per annum.</p>

      <p class="italic-p">(Your remuneration details are attached in Annexure – II for your reference).</p>

      <p class="body-p">It is mandatory to achieve your monthly set target of business given by your superior, to justify your monthly fixed pay. Your career with us is based on your performance and achievement of the set business goals and Objectives of the Organization. As discussed with you during your interview, your 'Salary / Position' or maybe both will be revised after the first 6 months after you join, such revision shall be purely based on the level of your performance in these first 6 months.</p>

      <p class="body-p">If the Employee wants to resign from their duties/Job role within One year of their service in such case the Employee has to serve three months of Notice Period or has to pay three months of their Salary to the Society. If the Employee wants to resign from their duties/Job role after one year of their service in such case the Employee has to serve two months of Notice Period or has to pay two months of their Salary to the Society. At the time of joining, you are advised to carry your true copies of all your credentials along with the list of documents mentioned below.</p>

      <p class="body-p">You have to submit the following details for generating your employment with the Society.</p>

      <!-- Required Documents table — yellow header, ► bullets -->
      <table class="docs-table">
        <thead>
          <tr><th colspan="2">Required Documents</th></tr>
        </thead>
        <tbody>
          <tr>
            <td>
              &#9658; Aadhaar Card &amp; PAN Card.<br>
              &#9658; 3 Pass Port Size Photos (White Back Ground).<br>
              &#9658; Academic Certificates: SSC, Inter, Degree &amp; PG if any.<br>
              &#9658; Police Verification Certificate. (15 Days will be given to obtain this certificate and can be obtained through E Seva also).<br>
              &#9658; Nominee Pass Port Size Photo, Aadhaar Card &amp; PAN Card (For the sake of PF &amp; ESI).<br>
              &#9658; PF service history &amp; PF passbook Statement (Available in UAN Log in).
            </td>
            <td>
              &#9658; 2 Nationalised Bank Cheques.<br>
              &#9658; Bank A/C Passbook Xerox (Front Page) or Cancelled Cheque.<br>
              &#9658; Physical fitness certificate by Govt. physician.<br>
              <div style="display:table;background:#3D5A8A;color:#fff;font-size:7.5pt;font-weight:700;padding:2pt 7pt;margin:5pt 0 4pt 0;letter-spacing:.06em;white-space:nowrap;">IF EXPERIENCED</div>
              &#9658; Previous Employment Offer Letters.<br>
              &#9658; Pay Slips: Latest 3 Months and Salary Account Statement.<br>
              &#9658; Relieving Letter.
            </td>
          </tr>
        </tbody>
      </table>

      <p class="left-p" style="margin-top:5pt">(You should submit these details within <b>7 days</b> from the date of receipt of this OFFER.)</p>
      <p class="left-p">This is only an offer of employment and you shall communicate your acceptance of this offer within <b>3 days</b> from the receipt thereof, failing which this offer shall stand cancelled.</p>
    `;

    // ── PAGE 2: Annexure-I + Annexure-II ─────────────────────────────────────
    const page2 = `
      <div class="ann-title">Annexure-I</div>
      <table class="ann1-table">
        <tbody>
          <tr><td>Name</td><td>${d.full_name || ""}</td></tr>
          <tr><td>Designation</td><td>${d.designation || ""}</td></tr>
          <tr><td>Grade</td><td>${grade}</td></tr>
          <tr><td>Scale</td><td>${scale}</td></tr>
          <tr><td>Department</td><td>${d.department || ""}</td></tr>
        </tbody>
      </table>

      <div class="ann-title" style="margin-top:6pt">Annexure-II</div>
      <table class="ann2-table">
        <thead>
          <tr>
            <th style="width:42%">Pay Component</th>
            <th style="width:29%">Monthly Amount</th>
            <th style="width:29%">Annual Amount</th>
          </tr>
        </thead>
        <tbody>
          <tr class="row-fixed"><td><b>Fixed</b></td><td><b>${fmt(ms)}</b></td><td><b>${fmt(yearly)}</b></td></tr>
          <tr class="row-alt"><td>Basic</td><td>${fmt(basic)}</td><td>${fmt(basic*12)}</td></tr>
          <tr><td>HRA</td><td>${fmt(hra)}</td><td>${fmt(hra*12)}</td></tr>
          <tr class="row-alt"><td>Conveyance Allowance</td><td>${fmt(convey)}</td><td>${fmt(convey*12)}</td></tr>
          <tr><td>Special Allowance</td><td>${fmt(spl)}</td><td>${fmt(spl*12)}</td></tr>
          <tr class="row-gross"><td><b>Gross Salary</b></td><td><b>${fmt(gross)}</b></td><td><b>${fmt(gross*12)}</b></td></tr>
          <tr class="row-empf"><td>Employer PF</td><td>${fmt(empPF)}</td><td>${fmt(empPF*12)}</td></tr>
          <tr class="row-ctc"><td><b>CTC</b></td><td><b>${fmt(ctc)}</b></td><td><b>${fmt(ctc*12)}</b></td></tr>
        </tbody>
      </table>

      <p class="note">*NOTE: PF, ESI, and Professional Tax will be deducted as applicable</p>
    `;

    return wrapPages(page1, page2);
  }

    // ── 2. Appointment Letter ──────────────────────────────────────────────────
  function appointmentLetter(d, dateStr) {
    function n(k) { return Number(d[k] || 0); }
    const gross = n("basic") + n("hra") + n("medical") + n("special_allowance") + n("da");
    const net   = gross - n("pf_deduction") - n("esi_deduction") - n("pt_deduction");

    return wrap(`
      <div class="doc-title">LETTER OF APPOINTMENT</div>
      <div class="title-rule"></div>

      <div class="date-line"><b>Date:</b> ${dateStr}</div>
      <div class="to-block">
        <b>Mr./Ms. ${d.full_name || ""},</b><br>
        S/o ${d.father_name || ""},<br>
        ${d.address || ""}
      </div>

      <p><b>Dear ${d.full_name || ""},</b></p>
      <p style="margin-bottom:6px"><b>Employee Code – ${d.employee_code || ""} / Branch – ${d.branch || ""}</b></p>

      <p>We are pleased to appoint you as <b>${d.designation || ""}</b> post our recent discussions and meetings. Your appointment with <b>Godavari Krishna Co-Op Society Ltd.</b> shall be effective <b>${fmtDate(d.joining_date)}</b> in <b>${d.scale || ""}</b>. Your posting shall be at <b>${d.branch || ""}</b>.</p>

      <p>Your appointment is subject to the Service Rules and Regulations, Code of Conduct, Policies, and existing service conditions of the Society and any other amendments thereto that may be brought into force from time to time and also contained in <b>Annexure - I</b> attached hereto.</p>

      <p>The details of your CTC are contained in <b>Annexure - II</b> attached hereto. Both these Annexures form part and parcel of this letter of appointment.</p>

      <p>We welcome you to the Society and wish you the very best in your new assignment. As a token of your acceptance of the appointment and the terms and conditions as contained therein, you are advised to sign the counterpart of this letter of appointment and return the same to the HR Department.</p>

      <p>Yours faithfully,</p>
      ${sigBlock()}

      <div style="border:1px solid #1F3864;padding:12px;margin:16px 0;font-size:10pt">
        <p style="margin-bottom:6px"><b>ACCEPTANCE</b></p>
        <p>I <b>${d.full_name || ""},</b> agree and accept the terms and conditions as contained in the Letter of Appointment. Signed and accepted.</p>
        <p style="margin-top:10px"><b>Date: ${dateStr} &nbsp;&nbsp;&nbsp;&nbsp; Signature: _______________</b></p>
        <p><b>Place: ${d.branch || ""} &nbsp;&nbsp;&nbsp;&nbsp; (Name in BLOCK Letters): _______________</b></p>
      </div>

      <div class="annex-title">ANNEXURE - I</div>
      <p>The terms and conditions of your employment are as follows:</p>

      <p><b>Appointment</b></p>
      <p>1. Your appointment is subject to verification of your credentials, testimonials, and other particulars mentioned in your application at the time of your appointment. In case, the information provided by you is found to be incorrect your appointment is liable to be terminated forthwith without any notice or notice pay in lieu thereof. This offer of appointment is subject to: (a) Submission of copies of your certificates and testimonials. (b) Three passport-size photographs. (c) Last three months' salary slips/salary certificate and relieving letter from your previous employer. (d) Submission of two acceptable professional references.</p>
      <p>2. Your appointment is subject to your being medically fit and your retention of reasonable medical fitness during the tenure of your employment.</p>
      <p>3. The Society reserves its right to carry out formal/informal checks of your credentials, testimonials, and other particulars mentioned in your application.</p>

      <p><b>Probation and Confirmation</b></p>
      <p>4. You shall be on training for a period of 6 Months and on probation for a period of the next 6 Months i.e., for a total period of 12 months from the date of Joining.</p>
      <p>5. At the end of the probation period, your services may be confirmed in writing, provided your services are found to be suitable and at the sole discretion of the Society.</p>
      <p>6. The Society reserves its right to extend the probation period, for a further term of 6 months at its sole discretion.</p>
      <p>7. You are required to perform your services as per the work assigned and achieve such targets/results that have been determined and communicated to/by you from time to time.</p>

      <p><b>Code of Conduct</b></p>
      <p>8. On your employment with the Society, you shall devote your full business time and attention to the performance of your duties. You shall render services exclusively to the Society and shall not engage in any outside interest or activity without written permission of the Society's Board.</p>
      <p>9. You shall use your best endeavor to promote the interest of the Society and your conduct at all times shall be such as not to damage the interest of the Society.</p>
      <p>10. Your appointment is subject to the Society's Rules and Regulations, Code of Conduct, Policies, and existing service conditions as contained in the HR Handbook.</p>

      <p><b>Working Hours</b></p>
      <p>The working hours of the Society are from 9.30 a.m. to 6.30 p.m., from Mondays to Saturdays, or such other working hours as may be informed from time to time by the Management of the Society.</p>

      <p><b>Transfer</b></p>
      <p>11. Transfer is an incident and condition of service and your services are liable to be transferred anywhere in the Society's Jurisdiction area at the sole discretion of the Society.</p>
      <p>12. In the event of your failure to report to duty at the location of your transfer within 3 days, the Society reserves its right to terminate your services without any notice or notice pay.</p>

      <p><b>Resignation</b></p>
      <p>13. You may resign the services of your employment with the Society at any time during the training/probation period by giving 2 months' written notice or paying 2 months' salary instead of the notice period.</p>
      <p>14. Upon confirmation of your service, you may resign by giving not less than 2 months written notice or paying 2 months' Notice pay instead of the notice period.</p>

      <p><b>Termination</b></p>
      <p>15. The Society reserves its right to terminate your services at any time during the probation period if your performance is found to be unsatisfactory by giving 30 days' notice.</p>
      <p>16. Upon confirmation of your service, your services may be terminated by issue of written notice of not less than 1 month or by paying Notice pay instead of notice period.</p>
      <p>17. Your services may be terminated forthwith without notice if: (a) information submitted by you is found incorrect; (b) any act of dishonesty, disobedience, misconduct or neglect of duty; (c) on becoming insolvent; (d) any misconduct that may damage the reputation of the Society; (e) unauthorized concurrent employment.</p>

      <p><b>Confidential Information</b></p>
      <p>18. You shall keep all information received in connection with your employment strictly confidential and shall not divulge, share, or communicate the same to any person, directly or indirectly, without written approval from the Society.</p>

      <p><b>Intellectual Property Rights</b></p>
      <p>19. All written work or invention made or produced by you in connection with your activities during the period of your engagement with the Society shall inure exclusively to the benefit of the Society.</p>

      <p><b>Non-Solicitation</b></p>
      <p>20. Post the termination of your services, you shall not solicit any of the clients or employees of the Society. This clause survives the termination of your services.</p>

      <p><b>Territorial Jurisdiction</b></p>
      <p>This letter of appointment is subject to the exclusive territorial jurisdiction of the Courts in Vijayawada.</p>

      <p>If you are willing to agree with the conditions outlined in this Letter of Appointment, please signify your receipt and acceptance and return a copy of this letter to HR.</p>
      <p>Yours faithfully,</p>

      <div style="border:1px solid #1F3864;padding:12px;margin:16px 0;font-size:10pt">
        <p style="margin-bottom:6px"><b>ACCEPTANCE</b></p>
        <p>I <b>${d.full_name || ""},</b> agree and accept all the terms and conditions mentioned in this letter of Appointment, signed and accepted here under.</p>
        <p style="margin-top:10px"><b>Date: ${dateStr} &nbsp;&nbsp;&nbsp;&nbsp; Signature: _______________</b></p>
        <p><b>Place: ${d.branch || ""} &nbsp;&nbsp;&nbsp;&nbsp; (Name in BLOCK Letters): _______________</b></p>
        <p style="font-size:9pt;font-style:italic;margin-top:8px">[Note: Please initial each page of the Letter of Appointment]</p>
      </div>

      <div class="annex-title">ANNEXURE - II (CTC Details)</div>
      <p>Terms and conditions of your CTC as agreed between you and the Society are as below:</p>
      <p>1. Your Annual CTC will be <b>Rs. ${Number(d.annual_ctc || 0).toLocaleString("en-IN")}/-</b> (<b>${d.annual_ctc_words || ""}</b> only) inclusive of all statutory payments.</p>
      <p>2. Any other payments like incentives, commissions, or performance bonuses would be communicated separately in writing.</p>
      <p>3. All payments will be subject to applicable taxes and deduction of tax at source.</p>
      <p>4. Your salary particulars are as shown in the below table.</p>
      <table>
        <thead><tr><th colspan="4">SALARY BREAK UP</th></tr></thead>
        <tbody>
          <tr><td class="cell-label">SALARY</td><td colspan="3"><b>${gross.toLocaleString("en-IN")}</b></td></tr>
          <tr class="row-alt"><td class="cell-label">BASIC</td><td>${n("basic")}</td><td class="cell-label">PF</td><td>${n("pf_deduction")}</td></tr>
          <tr><td class="cell-label">HRA</td><td>${n("hra")}</td><td class="cell-label">ESI</td><td>${n("esi_deduction")}</td></tr>
          <tr class="row-alt"><td class="cell-label">MEDICAL</td><td>${n("medical")}</td><td class="cell-label">PT</td><td>${n("pt_deduction")}</td></tr>
          <tr><td class="cell-label">SPL. ALLOWANCE</td><td>${n("special_allowance")}</td><td colspan="2"></td></tr>
          <tr class="row-alt"><td class="cell-label">D.A.</td><td>${n("da")}</td><td colspan="2"></td></tr>
          <tr><td class="cell-label" colspan="2"><b>Total Net Salary</b></td><td colspan="2"><b>${net.toLocaleString("en-IN")}</b></td></tr>
        </tbody>
      </table>

      <p>Yours faithfully,</p>
      <div style="border:1px solid #1F3864;padding:12px;margin:16px 0;font-size:10pt">
        <p style="margin-bottom:6px"><b>ACCEPTANCE</b></p>
        <p>I <b>${d.full_name || ""},</b> agree and accept all the terms and conditions mentioned in this letter of Appointment, signed and accepted here under.</p>
        <p style="margin-top:10px"><b>Date: ${dateStr} &nbsp;&nbsp;&nbsp;&nbsp; Signature: _______________</b></p>
        <p><b>Place: ${d.branch || ""} &nbsp;&nbsp;&nbsp;&nbsp; (Name in BLOCK Letters): _______________</b></p>
      </div>
      <div class="note">NOTE: PF, ESI, and Professional Tax will be deducted as applicable.</div>
    `);
  }

  // ── 3. Salary Increment Letter ─────────────────────────────────────────────
  function salaryIncrement(d, dateStr) {
    return wrap(`
      <div class="doc-title">SALARY INCREMENT LETTER</div>
      <div class="title-rule"></div>

      <div class="date-line"><b>Date:</b> ${dateStr}</div>
      <div class="to-block">
        <b>${d.full_name || ""},</b><br>
        ${d.designation || ""},<br>
        ${d.branch || ""} Branch.
      </div>

      <p style="margin-top:14px">We Congratulate you for your hard work, enthusiasm, dedication, and continuous efforts in meeting the organization's objectives on an efficient basis being <b>${d.designation || ""}</b> for the last FY ${d.fy || ""}. On reviewing your performance for the last FY, as a part of Appraisal program you were granted an Increment of Rs.<b>${d.increment_amount || ""}/-</b> (Rs. <b>${d.increment_words || ""}</b>) in your salary, where your new CTC will be <b>${d.new_ctc || ""}/-</b> w.e.f <b>${fmtDate(d.effective_date)}</b>.</p>

      <p>We look forward for your vital contributions towards the organizational growth and wishing you all the very best for your future endeavors.</p>

      ${sigBlock()}
    `);
  }

  // ── 4. Promotion Letter ────────────────────────────────────────────────────
  function promotionLetter(d, dateStr) {
    return wrap(`
      <div class="doc-title">PROMOTION &amp; SALARY INCREMENT LETTER</div>
      <div class="title-rule"></div>

      <div class="date-line"><b>Date:</b> ${dateStr}</div>
      <div class="to-block">
        <b>${d.full_name || ""},</b><br>
        ${d.current_designation || ""},<br>
        ${d.branch || ""} Branch.
      </div>

      <p style="margin-top:14px">We Congratulate you for your hard work, enthusiasm, dedication, and continuous efforts in meeting the organization's objectives on an efficient basis being <b>${d.current_designation || ""}</b> for the last FY ${d.fy || ""}. On reviewing your performance for the last FY, as a part of Appraisal program you were promoted as <b>${d.new_designation || ""}</b> based at the <b>${d.branch || ""} Branch</b>, and the Management has granted an Increment of Rs.<b>${d.increment_amount || ""}/-</b> (Rs. <b>${d.increment_words || ""}</b>) in your salary, where your new CTC will be <b>${d.new_ctc || ""}/-</b> w.e.f <b>${fmtDate(d.effective_date)}</b>.</p>

      <p>We look forward for your vital contributions towards the organizational growth and wishing you all the very best for your future endeavors.</p>

      ${sigBlock()}
    `);
  }

  // ── 5. Relieving Letter ────────────────────────────────────────────────────
  function relievingLetter(d, dateStr) {
    const joining  = fmtDate(d.joining_date);
    const lastDay  = fmtDate(d.last_working_date);
    const duesDt   = fmtDate(d.dues_settled_date);

    return wrap(`
      <div style="display:flex;justify-content:space-between;margin-bottom:14px;font-size:10pt">
        <span><b>Ref No: ${d.ref_number || ""}</b></span>
        <span><b>Date: ${dateStr}</b></span>
      </div>

      <div class="doc-title">RELIEVING CUM EXPERIENCE LETTER</div>
      <div class="title-rule"></div>

      <p style="text-align:center;font-weight:700;letter-spacing:.04em;font-size:10.5pt">TO WHOMSOEVER IT MAY CONCERN</p>

      <p style="font-size:11pt;font-weight:700;margin:14px 0 6px">Mr./Ms. ${d.full_name || ""}</p>

      <p>This letter is to formally acknowledge and confirm the acceptance of your resignation from the position of <b>${d.designation || ""}</b> in the <b>${d.department || ""} Department</b> at <b>${d.branch || ""}</b> of <b>Godavari ~ Krishna Co-Operative Society Limited</b>. Your last working day with the society was <b>${lastDay}</b>.</p>

      <p><b>Employment Details:</b></p>
      <table>
        <tbody>
          <tr><td class="cell-label">Employee Code</td><td>${d.employee_code || ""}</td></tr>
          <tr class="row-alt"><td class="cell-label">Employment Tenure</td><td>${joining} To ${lastDay}</td></tr>
          <tr><td class="cell-label">Last Drawn Salary</td><td>${d.last_drawn_salary || ""}</td></tr>
        </tbody>
      </table>

      <p>As per our records, all dues and entitlements have been settled by <b>${duesDt}</b>.</p>

      <p><b>Regards,</b></p>
      <div style="margin-top:28px">
        <div class="sig-name">Jeevan Meduri</div>
        <div class="sig-title">(Chairman)</div>
      </div>
    `);
  }

  // ── Dispatcher ─────────────────────────────────────────────────────────────
  const BUILDERS = {
    offer_letter:       offerLetter,
    appointment_letter: appointmentLetter,
    salary_increment:   salaryIncrement,
    promotion_letter:   promotionLetter,
    relieving_letter:   relievingLetter,
  };

  function guessCode(label) {
    const map = {
      "Offer Letter":            "offer_letter",
      "Appointment Letter":      "appointment_letter",
      "Salary Increment Letter": "salary_increment",
      "Promotion Letter":        "promotion_letter",
      "Relieving Letter":        "relieving_letter",
    };
    return map[label] || "offer_letter";
  }

  /**
   * render(doc) → full HTML string
   * doc must have: form_data, document_type_code (or document_type_label)
   */
  function render(doc) {
    const code    = doc.document_type_code || guessCode(doc.document_type_label || "");
    const builder = BUILDERS[code];
    if (!builder) return wrap(`<p>No preview available for this document type.</p>`);
    const dateStr = today();
    return builder(doc.form_data || {}, dateStr);
  }

  return { render, renderAsync, preloadImages };
})();