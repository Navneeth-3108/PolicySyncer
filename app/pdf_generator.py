import datetime
from fpdf import FPDF


def _pdf_safe(text) -> str:
    """fpdf2's built-in core fonts (helvetica, used throughout this report)
    only support latin-1/cp1252. Policy obligation text is pasted verbatim
    from real documents (raw_text quoted in prose.py's _modal_phrase) and
    routinely contains curly quotes, em/en dashes, ellipses, or accented
    characters that fall outside latin-1. Writing those straight to a core
    font raises FPDFUnicodeEncodingException and aborts the whole export.
    Replace unsupported characters instead of crashing -- this keeps the
    report readable (an accented name becomes its closest latin-1 spelling,
    anything with no latin-1 equivalent becomes '?') without failing the
    entire /export-pdf request over one character in one finding.
    """
    if text is None:
        return ""
    return str(text).encode("latin-1", errors="replace").decode("latin-1")


class PolicyReportPDF(FPDF):
    def header(self):
        # Draw a subtle header background bar
        self.set_fill_color(30, 27, 75)  # Dark Obsidian Indigo
        self.rect(0, 0, 210, 15, 'F')
        
        # Header text
        self.set_y(4)
        self.set_font('helvetica', 'B', 10)
        self.set_text_color(255, 255, 255)
        self.cell(0, 8, 'POLICY CONFLICT & STALENESS DETECTOR -- REPORT', border=0, align='C')
        self.ln(10)
        
    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(156, 163, 175) # Gray-400
        # Page number
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')

def generate_report_pdf(report: dict) -> bytes:
    pdf = PolicyReportPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    pdf.set_y(25)
    
    # Report Title
    pdf.set_font('helvetica', 'B', 18)
    pdf.set_text_color(30, 27, 75) # Deep Indigo
    pdf.cell(0, 10, 'Policy Analysis Report', ln=1)
    
    pdf.set_font('helvetica', '', 9)
    pdf.set_text_color(107, 114, 128) # Gray-500
    date_str = datetime.date.today().strftime("%B %d, %Y")
    pdf.cell(0, 5, f'Generated on: {date_str}', ln=1)
    pdf.ln(5)
    
    # ----------------------------------------------------
    # SECTION 1: POLICY HEALTH SCORE
    # ----------------------------------------------------
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(17, 24, 39) # Gray-900
    pdf.cell(0, 8, '1. Policy Health Scores', ln=1)
    pdf.set_draw_color(229, 231, 235) # Gray-200
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    
    health_scores = report.get("policy_health_score", {})
    if not health_scores:
        pdf.set_font('helvetica', 'I', 10)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(0, 6, 'No health score calculated.', ln=1)
    else:
        for name, score in health_scores.items():
            # Format policy name
            display_name = name.replace("_", " ").title()
            if display_name.lower() == "overall":
                display_name = "Overall Pipeline Health Score"
            display_name = _pdf_safe(display_name)
                
            pdf.set_font('helvetica', 'B', 10)
            pdf.set_text_color(31, 41, 55) # Gray-800
            pdf.cell(80, 6, f'  {display_name}:', ln=0)
            
            # Score styling
            pdf.cell(20, 6, f'{score}%', ln=0)
            
            # Label indicator
            if score >= 80:
                pdf.set_text_color(22, 163, 74) # Green-600
                status = "GOOD"
            elif score >= 50:
                pdf.set_text_color(202, 138, 4) # Yellow-600
                status = "WARNING"
            else:
                pdf.set_text_color(220, 38, 38) # Red-600
                status = "CRITICAL"
                
            pdf.cell(30, 6, f'[{status}]', ln=1)
            
    pdf.ln(6)
    
    # ----------------------------------------------------
    # SECTION 2: FINDINGS & CONFLICTS
    # ----------------------------------------------------
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(17, 24, 39)
    pdf.cell(0, 8, '2. Detailed Findings & Recommendations', ln=1)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    
    findings = report.get("findings", [])
    if not findings:
        pdf.set_font('helvetica', 'I', 10)
        pdf.set_text_color(22, 163, 74)
        pdf.cell(0, 6, '  No policy conflicts, redundancies, or staleness detected.', ln=1)
    else:
        for idx, finding in enumerate(findings, 1):
            severity = finding.get("severity", "LOW")
            f_type = _pdf_safe(finding.get("finding_type", "INFO"))
            policy_name = _pdf_safe(
                finding.get("policy") or " / ".join(
                    p for p in (finding.get("policy_a"), finding.get("policy_b")) if p
                ) or "Unknown Policy"
            )
            description = _pdf_safe(finding.get("description", ""))
            recommendation = _pdf_safe(finding.get("recommendation", ""))
            compliance = [_pdf_safe(c) for c in finding.get("compliance_impact", [])]
            
            # Header line: e.g. "1. [HIGH] STALE in Password Policy"
            pdf.set_font('helvetica', 'B', 10)
            pdf.set_text_color(17, 24, 39)
            pdf.cell(10, 6, f'{idx}.', ln=0)
            
            # Severity color
            if severity == "HIGH":
                pdf.set_text_color(220, 38, 38) # Red
            elif severity == "MEDIUM":
                pdf.set_text_color(202, 138, 4) # Yellow
            else:
                pdf.set_text_color(37, 99, 235) # Blue
                
            pdf.cell(40, 6, f'[{severity}] {f_type}', ln=0)
            pdf.set_text_color(75, 85, 99) # Gray-600
            pdf.set_font('helvetica', 'I', 10)
            pdf.cell(0, 6, f'in {policy_name}', ln=1)
            
            # Reset style for body
            pdf.set_text_color(31, 41, 55) # Gray-800
            
            # Description
            pdf.set_font('helvetica', 'B', 9)
            pdf.cell(0, 5, '  Description:', ln=1)
            pdf.set_font('helvetica', '', 9)
            pdf.multi_cell(0, 5, '    ' + description)
            pdf.ln(1)

            # Scope Analysis (CONFLICT findings only, when non-trivial)
            scope_analysis = _pdf_safe(finding.get("scope_analysis", ""))
            if scope_analysis:
                pdf.set_font('helvetica', 'B', 9)
                pdf.cell(0, 5, '  Scope Analysis:', ln=1)
                pdf.set_font('helvetica', '', 9)
                pdf.multi_cell(0, 5, '    ' + scope_analysis)
                pdf.ln(1)

            # Recommendation
            if recommendation:
                pdf.set_font('helvetica', 'B', 9)
                pdf.cell(0, 5, '  Remediation Recommendation:', ln=1)
                pdf.set_font('helvetica', '', 9)
                pdf.multi_cell(0, 5, '    ' + recommendation)
                pdf.ln(1)
                
            # Compliance Impact
            if compliance:
                pdf.set_font('helvetica', 'B', 9)
                pdf.cell(0, 5, '  Compliance Standards: ' + ', '.join(compliance), ln=1)
                pdf.ln(1)
                
            pdf.ln(3)
            
    # Output PDF as bytearray
    return bytes(pdf.output())
