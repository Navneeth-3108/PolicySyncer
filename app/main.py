import sys
import json
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Add all layer directories to sys.path (same as run_pipeline.py)
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "policy_layer1"))
sys.path.insert(0, str(root_dir / "policy_layer2"))
sys.path.insert(0, str(root_dir / "policy_layer3"))

# Pipeline imports
from policy_layer1 import run_layer1
from policy_layer2 import run_layer2
from policy_layer2.config import Config as Layer2Config
from policy_layer3 import run_layer3, Layer3Config

# PDF Generator
from app.pdf_generator import generate_report_pdf

app = FastAPI(title="Policy Analyzer Web UI")

# Templates setup
templates_dir = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

def run_analysis_pipeline(raw_text: str) -> dict:
    """Invokes the three-layer pipeline sequentially on raw text."""
    # Layer 1: Obligation Extraction
    layer1_records = run_layer1(raw_text)
    layer1_dicts = [r.to_dict() for r in layer1_records]
    
    # Layer 2: Analysis (use loosened threshold)
    layer2_config = Layer2Config(blocking_similarity_threshold=0.0)
    layer2_output = run_layer2(layer1_dicts, config=layer2_config)
    
    # Layer 3: Recommendations & Reporting
    layer3_config = Layer3Config()
    report = run_layer3(
        layer2_output,
        layer1_records,
        config=layer3_config,
        layer2_config=layer2_config,
    )
    return report

@app.get("/", response_class=HTMLResponse)
async def get_upload_page(request: Request):
    """Renders the drag-and-drop file upload UI."""
    return templates.TemplateResponse(request=request, name="upload.html")

@app.post("/analyze", response_class=HTMLResponse)
async def analyze_file(request: Request, file: UploadFile = File(...)):
    """Handles file uploads via the UI and renders the HTML results page."""
    if not file.filename.endswith(('.txt', '.md')):
        raise HTTPException(status_code=400, detail="Only text (.txt) or markdown (.md) files are supported.")
        
    try:
        contents = await file.read()
        raw_text = contents.decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")
        
    try:
        report = run_analysis_pipeline(raw_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis pipeline failed: {str(e)}")
        
    # Serialize JSON report string for hidden template input to export PDF statelessly
    report_json_str = json.dumps(report)
    
    return templates.TemplateResponse(
        request=request,
        name="results.html",
        context={
            "report": report,
            "report_json": report_json_str
        }
    )

@app.post("/api/analyze")
async def api_analyze_file(file: UploadFile = File(...)):
    """API endpoint to run analysis and return the generated JSON report directly."""
    if not file.filename.endswith(('.txt', '.md')):
        raise HTTPException(status_code=400, detail="Only text (.txt) or markdown (.md) files are supported.")
        
    try:
        contents = await file.read()
        raw_text = contents.decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")
        
    try:
        report = run_analysis_pipeline(raw_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis pipeline failed: {str(e)}")
        
    return report

@app.post("/export-pdf")
async def export_pdf(report_json: str = Form(...)):
    """Receives JSON report data and returns a formatted PDF file download."""
    try:
        report = json.loads(report_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid report JSON format: {str(e)}")
        
    try:
        pdf_bytes = generate_report_pdf(report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")
        
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=policy_analysis_report.pdf"
        }
    )
