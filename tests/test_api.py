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
