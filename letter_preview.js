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

  // ── Shared letterhead wrapper — pixel-perfect GK letterhead ─────────────────
  function wrap(bodyHtml) {
    return `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:Arial,Helvetica,sans-serif;font-size:10pt;color:#1a1a1a;background:#fff}
  .page{width:100%;min-height:100vh;display:flex;flex-direction:column;background:#fff}

  /* HEADER */
  .lh{background:#fff;padding:8px 16px 0;display:flex;align-items:flex-start;gap:10px}
  .lh-emblem{flex-shrink:0;width:92px;height:92px}
  .lh-right{flex:1;min-width:0;display:flex;flex-direction:column}

  .lh-certs{
    display:flex;justify-content:flex-end;gap:20px;
    font-size:6.8pt;font-weight:700;color:#1F3864;
    letter-spacing:0.01em;margin-bottom:1px;
  }
  .lh-name{
    font-size:20pt;font-weight:900;color:#1F3864;
    line-height:1.1;letter-spacing:0.01em;white-space:nowrap;
  }
  .lh-sub-wrap{text-align:center;margin:3px 0 4px}
  .lh-sub{
    display:inline-block;background:#F5C518;color:#1F3864;
    font-size:9pt;font-weight:700;font-style:italic;padding:2px 16px;
  }
  .lh-addr{text-align:center;font-size:8.2pt;color:#1a1a1a;margin-bottom:2px}
  .lh-web{display:flex;justify-content:center;gap:70px;font-size:8.2pt;color:#1a1a1a;padding-bottom:5px}
  .lh-rule{height:1.5px;background:#4a8040;width:100%}

  /* CONTENT */
  .content{flex:1;padding:18px 30px 20px;position:relative;overflow:hidden}
  .wm{
    position:absolute;top:36%;left:50%;
    transform:translate(-50%,-50%);
    width:300px;height:300px;
    opacity:0.055;pointer-events:none;z-index:0;
  }
  .content>:not(.wm){position:relative;z-index:1}

  .doc-title{font-size:12pt;font-weight:700;text-align:center;color:#1F3864;
             letter-spacing:.07em;margin-bottom:2px;
             text-decoration:underline;text-underline-offset:3px}
  .title-rule{height:1.5px;background:#1F3864;margin-bottom:16px}
  .date-line{font-size:10pt;margin-bottom:10px}
  .to-block{margin-bottom:13px;line-height:1.85;font-size:10pt}
  p{font-size:10pt;line-height:1.75;margin-bottom:10px;text-align:justify}
  b{font-weight:700}i{font-style:italic}

  table{width:100%;border-collapse:collapse;margin-bottom:11px;font-size:9pt}
  th,td{padding:5px 8px;border:1px solid #aaa;text-align:left;vertical-align:top}
  thead th{background:#1F3864;color:#fff;font-weight:700;text-align:center}
  .row-alt{background:#f4f5f9}
  .cell-label{background:#e6eaf4;font-weight:700;color:#1F3864;width:36%}

  .annex-title{font-size:10pt;font-weight:700;color:#1F3864;
               margin:14px 0 5px;border-bottom:1.5px solid #1F3864;padding-bottom:2px}
  .sig-row{display:flex;justify-content:space-between;margin-top:28px}
  .sig-col{width:48%}
  .sig-org{font-size:8.5pt;color:#555;margin-bottom:22px}
  .sig-name{font-weight:700;font-size:10pt;color:#111}
  .sig-title{font-size:8.5pt;color:#555}
  .note{font-size:8.5pt;font-weight:700;margin-top:8px;color:#333}

  /* FOOTER */
  .lh-footer{flex-shrink:0;height:72px;position:relative;overflow:hidden}
  .lh-footer svg{position:absolute;bottom:0;left:0;width:100%;height:100%}
</style>
</head>
<body>
<div class="page">

  <!-- HEADER -->
  <div class="lh">
    <!-- Circular GK emblem -->
    <svg class="lh-emblem" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <circle cx="50" cy="50" r="47" fill="#fff" stroke="#3d7a35" stroke-width="4"/>
      <circle cx="50" cy="50" r="42" fill="none" stroke="#3d7a35" stroke-width="1.2"/>
      <text x="50" y="65" text-anchor="middle"
            font-family="Times New Roman,Times,serif"
            font-size="38" font-weight="900" font-style="italic" fill="#1F3864">gk</text>
      <path id="arcT" d="M 9,50 A 41,41 0 0,1 91,50" fill="none"/>
      <text font-family="Arial,sans-serif" font-size="7.5" font-weight="700"
            fill="#3d7a35" letter-spacing="1.5">
        <textPath href="#arcT" startOffset="3%">GODAVARI ~ KRISHNA</textPath>
      </text>
      <path id="arcB" d="M 15,58 A 37,37 0 0,0 85,58" fill="none"/>
      <text font-family="Arial,sans-serif" font-size="7" font-weight="700"
            fill="#3d7a35" letter-spacing="2">
        <textPath href="#arcB" startOffset="22%">~ KRISHNA ~</textPath>
      </text>
    </svg>

    <!-- Text block -->
    <div class="lh-right">
      <div class="lh-certs">
        <span>AP MAC Society ACT 1995</span>
        <span>ISO Certified 9001-2015</span>
        <span>Regd No.: AMC/KNA/DCO/2019/122</span>
      </div>
      <div class="lh-name">GODAVARI &nbsp;~&nbsp; KRISHNA CO-OP SOCIETY LTD.,</div>
      <div class="lh-sub-wrap">
        <span class="lh-sub">(Mutually Aided Thrift and Credit Society)</span>
      </div>
      <div class="lh-addr">
        # 9-61-13, BRP Road, Islam Pet, VIjayawada-520001.&nbsp;&nbsp;&nbsp;Ph : 0866-2566334, Toll free No. : 1800 8899570
      </div>
      <div class="lh-web">
        <span>www.godavarikrishna.com</span>
        <span>admin@godavarikrishna.com</span>
      </div>
    </div>
  </div>
  <div class="lh-rule"></div>

  <!-- CONTENT -->
  <div class="content">
    <!-- Hibiscus watermark (faint pink) -->
    <svg class="wm" viewBox="0 0 300 300" xmlns="http://www.w3.org/2000/svg">
      <ellipse cx="150" cy="90"  rx="26" ry="82" fill="#c33" transform="rotate(0   150 165)"/>
      <ellipse cx="150" cy="90"  rx="26" ry="82" fill="#c33" transform="rotate(45  150 165)"/>
      <ellipse cx="150" cy="90"  rx="26" ry="82" fill="#c33" transform="rotate(90  150 165)"/>
      <ellipse cx="150" cy="90"  rx="26" ry="82" fill="#c33" transform="rotate(135 150 165)"/>
      <ellipse cx="150" cy="90"  rx="26" ry="82" fill="#c33" transform="rotate(180 150 165)"/>
      <ellipse cx="150" cy="90"  rx="26" ry="82" fill="#c33" transform="rotate(225 150 165)"/>
      <ellipse cx="150" cy="90"  rx="26" ry="82" fill="#c33" transform="rotate(270 150 165)"/>
      <ellipse cx="150" cy="90"  rx="26" ry="82" fill="#c33" transform="rotate(315 150 165)"/>
      <line x1="150" y1="90" x2="150" y2="275" stroke="#922" stroke-width="4"/>
      <ellipse cx="128" cy="188" rx="22" ry="9" fill="#922" transform="rotate(-35 128 188)"/>
      <ellipse cx="172" cy="205" rx="22" ry="9" fill="#922" transform="rotate(35 172 205)"/>
    </svg>
    ${bodyHtml}
  </div>

  <!-- FOOTER: navy wave + gold stripe -->
  <div class="lh-footer">
    <svg viewBox="0 0 1000 72" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M0,40 Q160,16 380,28 Q520,35 620,25 L620,36 Q520,46 380,38 Q160,28 0,52 Z"
            fill="#F5C518"/>
      <path d="M0,72 L0,44 Q120,20 280,30 Q450,42 620,24 Q760,10 900,27 Q960,34 1000,30 L1000,72 Z"
            fill="#1F3864"/>
    </svg>
  </div>

</div>
</body>
</html>`;
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

  // ── 1. Offer Letter ────────────────────────────────────────────────────────
  function offerLetter(d, dateStr) {
    const monthly = d.monthly_salary || "";
    const yearly  = monthly ? (Number(monthly) * 12).toLocaleString("en-IN") : "";

    return wrap(`
      <div class="doc-title">LETTER OF EMPLOYMENT</div>
      <div class="title-rule"></div>

      <div class="date-line"><b>Date:</b> ${dateStr}</div>
      <div class="to-block">
        To,<br>
        <b>Mr./Ms. ${d.full_name || ""},</b>
      </div>

      <p>In continuation of our discussions on possible employment with M/s Godavari Krishna Co-Op Society Limited Vijayawada, we are pleased to make you an offer as <b>${d.designation || ""}</b> Initially as per the norms fixed in the Appointment letter and Duty list. Your complete appointment letter will be processed on the date of joining post completion of your joining formalities with Godavari Krishna Co-Operative Society Limited.</p>

      <p>Your fixed remuneration will be INR <b>${monthly}/-</b> (in words Rupees <b>${d.monthly_salary_words || ""}</b> only) per month and INR <b>${yearly}/-</b> (in words Rupees <b>${d.yearly_salary_words || ""}</b> only) per annum.</p>

      <p><i>(Your remuneration details are attached in <b>Annexure – I</b> for your reference).</i></p>

      <p>It is mandatory to achieve your monthly set target of business given by your superior, to justify your monthly fixed pay. Your career with us is based on your performance and achievement of the set business goals and Objectives of the Organization. As discussed with you during your interview, your 'Salary / Position' or maybe both will be revised after the first 6 months after you join, such revision shall be purely based on the level of your performance in these first 6 months.</p>

      <p>If the Employee wants to resign from their duties/Job role within One year of their service in such case the Employee has to serve three months of Notice Period or has to pay three months of their Salary to the Society. If the Employee wants to resign from their duties/Job role after one year of their service in such case the Employee has to serve two months of Notice Period or has to pay two months of their Salary to the Society.</p>

      <p>You have to submit the following details for generating your employment with the Society.</p>

      <table>
        <thead><tr><th colspan="2">Required Documents</th></tr></thead>
        <tbody>
          <tr><td>Aadhaar Card &amp; PAN Card.</td><td>2 Nationalised Bank Cheques.</td></tr>
          <tr class="row-alt"><td>3 Passport Size Photos (White Background).</td><td>Previous Employment Offer Letters.</td></tr>
          <tr><td>Academic Certificates: SSC, Inter, Degree &amp; PG if any.</td><td>Pay Slips: Latest 3 Months and Salary Account Statement.</td></tr>
          <tr class="row-alt"><td>Police Verification Certificate (15 Days will be given; can be obtained through E Seva).</td><td>Relieving Letter.</td></tr>
          <tr><td>Nominee Aadhaar Card &amp; PAN Card (For PF &amp; ESI).</td><td>Physical fitness certificate by Govt. physician.</td></tr>
          <tr class="row-alt"><td>PF service history &amp; PF passbook Statement (Available in UAN Login).</td><td></td></tr>
        </tbody>
      </table>

      <p><i>(You should submit these details within <b>7 days</b> from the date of receipt of this OFFER.)</i></p>
      <p>This is only an offer of employment and you shall communicate your acceptance of this offer within <b>3 days</b> from the receipt thereof, failing which this offer shall stand cancelled.</p>

      <div class="annex-title">Annexure – I</div>
      <table>
        <tbody>
          <tr><td class="cell-label">Name</td><td>${d.full_name || ""}</td></tr>
          <tr class="row-alt"><td class="cell-label">Designation</td><td>${d.designation || ""}</td></tr>
          <tr><td class="cell-label">Grade</td><td>${d.grade || ""}</td></tr>
          <tr class="row-alt"><td class="cell-label">Department</td><td>${d.department || ""}</td></tr>
          <tr><td class="cell-label">Date of Birth</td><td>${fmtDate(d.date_of_birth)}</td></tr>
          <tr class="row-alt"><td class="cell-label">Father Name</td><td>${d.father_name || ""}</td></tr>
        </tbody>
      </table>
      <div class="note">NOTE: PF, ESI, and Professional Tax will be deducted as applicable.</div>
    `);
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
        S/o ${d.father_name || ""}<br>
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

      <div class="annex-title">ANNEXURE - II (CTC Details)</div>
      <table>
        <thead><tr><th colspan="4">SALARY BREAK UP</th></tr></thead>
        <tbody>
          <tr><td class="cell-label" colspan="2">Gross Salary</td><td colspan="2"><b>${gross.toLocaleString("en-IN")}</b></td></tr>
          <tr class="row-alt"><td class="cell-label">BASIC</td><td>${n("basic")}</td><td class="cell-label">PF</td><td>${n("pf_deduction")}</td></tr>
          <tr><td class="cell-label">HRA</td><td>${n("hra")}</td><td class="cell-label">ESI</td><td>${n("esi_deduction")}</td></tr>
          <tr class="row-alt"><td class="cell-label">MEDICAL</td><td>${n("medical")}</td><td class="cell-label">PT</td><td>${n("pt_deduction")}</td></tr>
          <tr><td class="cell-label">SPL. ALLOWANCE</td><td>${n("special_allowance")}</td><td colspan="2"></td></tr>
          <tr class="row-alt"><td class="cell-label">D.A.</td><td>${n("da")}</td><td colspan="2"></td></tr>
          <tr><td class="cell-label" colspan="2"><b>Total Net Salary</b></td><td colspan="2"><b>${net.toLocaleString("en-IN")}</b></td></tr>
        </tbody>
      </table>
      <p><b>Annual CTC:</b> Rs.${Number(d.annual_ctc || 0).toLocaleString("en-IN")}/-</p>
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
        Mr./Ms. <b>${d.full_name || ""},</b><br>
        ${d.designation || ""}<br>
        ${d.branch || ""} Branch.
      </div>

      <p>We Congratulate you for your hard work, enthusiasm, dedication, and continuous efforts in meeting the organization's objectives on an efficient basis being <b>${d.designation || ""}</b> for the last FY ${d.fy || ""}. On reviewing your performance for the last FY, as a part of Appraisal program you were granted an Increment of Rs.<b>${d.increment_amount || ""}/-</b> (Rs. <b>${d.increment_words || ""}</b>) in your salary, where your new CTC will be <b>${d.new_ctc || ""}/-</b> w.e.f <b>${fmtDate(d.effective_date)}</b>.</p>

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
        Mr./Ms. <b>${d.full_name || ""},</b><br>
        ${d.current_designation || ""}<br>
        ${d.branch || ""} Branch.
      </div>

      <p>We Congratulate you for your hard work, enthusiasm, dedication, and continuous efforts in meeting the organization's objectives on an efficient basis being <b>${d.current_designation || ""}</b> for the last FY ${d.fy || ""}. On reviewing your performance for the last FY, as a part of Appraisal program you were promoted as <b>${d.new_designation || ""}</b> based at the <b>${d.branch || ""} Branch</b>, and the Management has granted an Increment of Rs.<b>${d.increment_amount || ""}/-</b> (Rs. <b>${d.increment_words || ""}</b>) in your salary, where your new CTC will be <b>${d.new_ctc || ""}/-</b> w.e.f <b>${fmtDate(d.effective_date)}</b>.</p>

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
      <div style="display:flex;justify-content:space-between;margin-bottom:14px;font-size:9.5pt">
        <span><b>Ref No:</b> ${d.ref_number || ""}</span>
        <span><b>Date:</b> ${dateStr}</span>
      </div>

      <div class="doc-title">RELIEVING CUM EXPERIENCE LETTER</div>
      <div class="title-rule"></div>

      <p style="text-align:center;font-weight:700;letter-spacing:.04em;font-size:10.5pt">TO WHOMSOEVER IT MAY CONCERN</p>

      <p><b>Mr./Ms. ${d.full_name || ""}</b></p>

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

      <p>Regards,</p>
      <div style="margin-top:32px">
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

  return { render };
})();