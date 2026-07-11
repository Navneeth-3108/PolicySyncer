import io
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_upload_page():
    """Verify that the home page (upload form) renders correctly."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Policy Analyzer" in response.text

def test_api_analyze_success():
    """Verify that the JSON API endpoint returns findings and health scores."""
    policy_text = (
        "--- Password Policy (v1.0, Last Reviewed: 2022-01-01) ---\n"
        "Section 1.1: Passwords must be at least 12 characters with uppercase and lowercase letters.\n"
    )
    files = {"file": ("policy.txt", policy_text, "text/plain")}
    response = client.post("/api/analyze", files=files)
    assert response.status_code == 200
    
    data = response.json()
    assert "findings" in data
    assert "policy_health_score" in data
    assert isinstance(data["findings"], list)
    assert isinstance(data["policy_health_score"], dict)

def test_api_analyze_invalid_file_extension():
    """Verify that uploading a non-supported file type returns a 400 error."""
    files = {"file": ("policy.pdf", "%PDF-1.4...", "application/pdf")}
    response = client.post("/api/analyze", files=files)
    assert response.status_code == 400
    assert "Only text" in response.json()["detail"]

def test_html_analyze_success():
    """Verify that the HTML analysis endpoint renders the results page."""
    policy_text = (
        "--- Password Policy (v1.0, Last Reviewed: 2022-01-01) ---\n"
        "Section 1.1: Passwords must be at least 12 characters.\n"
    )
    files = {"file": ("policy.txt", policy_text, "text/plain")}
    response = client.post("/analyze", files=files)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Analysis Results" in response.text
    assert "Policy Health" in response.text

def test_export_pdf_success():
    """Verify that the PDF export endpoint returns a PDF file."""
    report_data = {
        "findings": [
            {
                "finding_type": "STALE",
                "severity": "HIGH",
                "policy": "Password Policy v1.0",
                "description": "Last reviewed on 2023-01-15 -- over 3 years ago.",
                "recommendation": "Schedule a policy review.",
                "compliance_impact": ["ISO 27001", "NIST IA-5"]
            }
        ],
        "policy_health_score": {
            "password_policy": 70,
            "overall": 70
        }
    }
    
    response = client.post("/export-pdf", data={"report_json": json.dumps(report_data)})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")

def test_conflict_finding_shows_real_policy_names_not_unknown():
    """CONFLICT findings only carry policy_a/policy_b (no `policy` field). Verify
    /analyze, /api/analyze, and /export-pdf all surface the real policy names
    instead of falling back to blank or "Unknown Policy" (see FIX 1)."""
    pypdf = pytest.importorskip("pypdf")

    # Two-policy MFA / password-rotation example known to produce a CONFLICT
    # finding (policy_layer1/examples/sample_input.txt).
    policy_text = (
        "--- Password Policy (v2.1, Last Reviewed: 2021-08-15) ---\n"
        "Section 3.1: All employees must rotate their passwords every 90 days.\n"
        "Section 3.2: Passwords must be at least 12 characters with uppercase,\n"
        "lowercase, numbers, and special characters.\n"
        "Section 3.3: Previous 10 passwords may not be reused.\n"
        "\n"
        "--- Cloud Security Policy (v1.4, Last Reviewed: 2023-02-10) ---\n"
        "Section 5.1: All cloud-hosted systems must implement MFA for user accounts.\n"
        "Section 5.2: Password rotation shall not be required for cloud systems; "
        "MFA replaces the need for periodic credential changes.\n"
        "Section 5.3: Service accounts must rotate credentials every 365 days.\n"
    )

    # --- /api/analyze (JSON) ---
    files = {"file": ("policy.txt", policy_text, "text/plain")}
    api_response = client.post("/api/analyze", files=files)
    assert api_response.status_code == 200
    report = api_response.json()

    conflict_findings = [f for f in report["findings"] if f["finding_type"] == "CONFLICT"]
    assert conflict_findings, "expected at least one CONFLICT finding"
    for finding in conflict_findings:
        assert finding.get("policy_a") and finding.get("policy_b")

    # --- /analyze (HTML) ---
    files = {"file": ("policy.txt", policy_text, "text/plain")}
    html_response = client.post("/analyze", files=files)
    assert html_response.status_code == 200
    assert "Unknown Policy" not in html_response.text
    assert "Password Policy" in html_response.text
    assert "Cloud Security Policy" in html_response.text

    # --- /export-pdf ---
    pdf_response = client.post("/export-pdf", data={"report_json": json.dumps(report)})
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF")

    reader = pypdf.PdfReader(io.BytesIO(pdf_response.content))
    pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Unknown Policy" not in pdf_text
    assert "Password Policy" in pdf_text
    assert "Cloud Security Policy" in pdf_text
