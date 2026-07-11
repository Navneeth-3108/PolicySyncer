# Policy Conflict & Staleness Detector

A three-layer system for analyzing policy documents to identify conflicts, redundancies, scope overlaps, and outdated requirements.

## Quick Start

### 1. Install Dependencies

From the root directory, run:

```bash
bash install_dependencies.sh
```

This will:
- Install core dependencies for all three layers (pytest only; core pipeline needs nothing else)
- Optionally install advanced NLP models (sentence-transformers, spaCy, transformers) for enhanced accuracy

**Note:** The core pipeline runs with zero hard dependencies. Optional NLP packages auto-upgrade functionality if available.

### 2. Run the Full Pipeline

Process a policy document through all three layers:

```bash
python run_pipeline.py
```

This runs the default sample policy. To process your own policy file:

```bash
python run_pipeline.py path/to/your/policy.txt
```

**Output files generated:**
- `layer1_output.json` - Extracted obligations and structured metadata
- `layer2_output.json` - Detected conflicts, redundancies, and staleness signals
- `final_report.json` - Final report with recommendations and policy health score

## Web UI & API Server

A minimal, high-aesthetic web interface and API is available around the policy analysis pipeline.

### 1. Install Web App Dependencies

The web app has its own dependencies (FastAPI, Uvicorn, Jinja2, python-multipart, fpdf2), listed in `app/requirements.txt`:

```bash
pip install -r app/requirements.txt
```

This is also handled automatically by `install_dependencies.sh`.

### 2. Run the Web Server

Start the Uvicorn server from the root directory:

```bash
.venv/bin/uvicorn app.main:app --reload
```

Then open [http://localhost:8000](http://localhost:8000) in your web browser.

### 3. API Endpoints

- **`GET /`**: Renders the web-based file-upload dashboard.
- **`POST /analyze`**: Accepts a policy document upload (form data) and returns the rendered HTML dashboard containing findings, recommendations, and health scores.
- **`POST /api/analyze`**: Accepts a policy document upload (form data) and returns the analysis report directly in JSON format.
- **`POST /export-pdf`**: Accepts a stringified JSON report and returns a downloadable, formatted PDF report.

## Project Structure

```
policy-conflict/
├── policy_layer1/              Layer 1: Rule-Based Obligation Extraction
│   ├── policy_layer1/
│   ├── examples/
│   ├── tests/
│   └── requirements.txt
├── policy_layer2/              Layer 2: Semantic Conflict & Staleness Analysis
│   ├── policy_layer2/
│   ├── examples/
│   ├── tests/
│   └── requirements.txt
├── policy_layer3/              Layer 3: Recommendations & Reporting
│   ├── policy_layer3/
│   ├── examples/
│   ├── tests/
│   └── requirements.txt
├── install_dependencies.sh     Setup script for dependencies
├── run_pipeline.py             Main end-to-end runner
└── README.md                   This file
```

## Detailed Layer Information

### Layer 1: Rule-Based Obligation Extraction
Parses policy text to extract structured obligation records containing:
- Modal type (obligation, prohibition, recommendation, permission)
- Actor, action, object, and scope
- Temporal constraints and exceptions
- Category classification and confidence scores

**Standalone usage:**
```bash
cd policy_layer1
python examples/run_example.py
pytest tests/
```

### Layer 2: Semantic Conflict & Staleness Analysis
Analyzes obligation pairs to detect:
- Direct conflicts (contradictory modalities)
- Redundancy and subsumption
- Scope overlaps
- Staleness signals (outdated references)

**Standalone usage:**
```bash
cd policy_layer2
python examples/run_example.py
pytest tests/
```

### Layer 3: Recommendations & Reporting
Produces human-readable reports with:
- Natural language descriptions of conflicts
- Remediation recommendations
- Scope analysis
- Policy health score

**Integrated example (also in policy_layer3):**
```bash
cd policy_layer3
python examples/run_example.py
```

## Advanced Configuration

Each layer can be configured independently through config objects:

```python
from policy_layer1 import run_layer1
from policy_layer1.config import Config as Layer1Config

config = Layer1Config(
    category_priority=['authentication', 'encryption', 'other'],
    use_spacy_if_available=True
)
records = run_layer1(text, config=config)
```

See individual layer READMEs for detailed configuration options.

## Optional NLP Enhancements

For production use with better accuracy, install:

```bash
pip install sentence-transformers  # Advanced similarity scoring
pip install transformers torch     # NLI model for contradiction detection
pip install spacy                  # Dependency parsing for slot extraction
python -m spacy download en_core_web_sm
```

## Testing

Run all tests across layers:

```bash
cd policy_layer1 && pytest tests/
cd ../policy_layer2 && pytest tests/
cd ../policy_layer3 && pytest tests/
```

Or test without pytest:

```bash
cd policy_layer1 && python tests/_run_without_pytest.py
cd ../policy_layer2 && python tests/_run_without_pytest.py
cd ../policy_layer3 && python tests/_run_without_pytest.py
cd ../dataset_integration/tests && python _run_without_pytest.py
```

## Dataset Evaluation (Problem-11 sample dataset)

`dataset_integration/` adapts the Problem-11 sample dataset (30 markdown
policy files + `findings_labels.csv` ground truth) into the pipeline's
native input format and scores the pipeline's output against it:

```bash
python run_dataset_evaluation.py path/to/dataset/problem_11
python run_dataset_evaluation.py path/to/dataset/problem_11 --json
```

Reports obligation-extraction accuracy plus conflict/redundancy/staleness
detection recall and a false-positive rate on the dataset's
scope-differentiated "apparent conflict" pairs. See
`dataset_integration/evaluate.py` for exactly how each metric is derived
from `findings_labels`, and `CHANGELOG.md` for the current numbers.

## Design Principles

- **Zero hard dependencies**: Core runs on stdlib only
- **Formal specification adherence**: Explicitly traced to design documents
- **Deterministic & auditable**: No LLM calls; fully traceable reasoning
- **Safety-first**: Won't fabricate data or make unfounded assumptions

See [SCOPE.md](SCOPE.md) for how this implementation maps to the project
brief's "Option C: Simple Policy Scanner" requirements, and which parts of
the pipeline intentionally go beyond them.

## License & Documentation

See individual layer READMEs for:
- Design document traceability
- Known limitations
- Open governance choices
- Detailed configuration examples
