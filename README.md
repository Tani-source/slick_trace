# SlickTrace 🌊

**Oil Spill Source Attribution System**  
Built for the **SIH26143 Hackathon** (NTRO - Disaster Management Theme)

SlickTrace is an automated pipeline and visual dashboard that takes a detected oil slick from satellite imagery, models its backward drift to find where and when it originated, cross-references AIS vessel-traffic data for that spatial-temporal window, and ranks the vessels most likely responsible for the spill.

It is designed to give coast guards and investigators an evidence-backed shortlist of suspect vessels with transparent, explainable sub-scores.

---

## 🌟 Key Features

### Pipeline Stages
1. **Perception (Stage 0):** U-Net segmentation on Sentinel-1 SAR imagery to detect and characterize an oil slick polygon, area, and age.
2. **Backward Drift (Stage 1):** Uses OpenDrift/OilDrift reversed advection (with CMEMS ocean currents and ERA5 wind) to trace the slick back to its origin envelope.
3. **AIS Ingestion & Candidate Filtering (Stage 2 & 3):** Spatially indexes AIS vessel-position records and filters by discharge-capable vessel types.
4. **Anomaly Scoring (Stage 4):** Scores candidates based on AIS blackout/gaps, speed anomalies, route deviation, and draft inconsistency to generate a shortlist.
5. **Forward Drift Simulation (Stage 5):** Runs a forward physics simulation (advection + wind drag + Fay spreading) from the shortlisted candidate release points.
6. **Verification & Matching (Stage 6):** Compares the simulated drift footprints to the original SAR observation using Intersection-over-Union (IoU) and centroid distance to produce a final, ranked MatchScore.

### Advanced Prototypes (Tier 2)
- **Dark-Ship Detection:** Analyzes the SAR scene for un-transponding (dark) vessels via CFAR object detection.
- **Oil-Type Fingerprinting:** Classifies crude/bunker oil signatures using Sentinel-2 EO imagery.

---

## 🛠 Tech Stack

**Frontend**
* **Framework:** React 18 with Vite
* **Styling:** Tailwind CSS v4 (with standard utility CSS)
* **State Management:** Zustand
* **Map Engine:** React Leaflet + CartoDB Basemaps

**Backend**
* **Framework:** FastAPI (Python 3.10+)
* **Processing:** NumPy, GeoPandas, Shapely
* **Simulation:** OpenDrift wrapper (mocked for demo purposes, seamlessly swappable)
* **Server:** Uvicorn

---

## 📁 Repository Structure

```
slick_trace/
├── backend/
│   ├── app/
│   │   ├── api/         # FastAPI router endpoints
│   │   ├── pipeline/    # Core business logic and pipeline orchestrator (Stages 0 - 6)
│   │   ├── schemas/     # Pydantic data contracts
│   │   └── services/    # Artifact storage and external engine wrappers
│   ├── data/            # Local cache, uploads, and prototype JSON mock data
│   ├── tests/           # Pytest suite validating backend logic
│   └── requirements.txt # Python dependencies
│
├── frontend/
│   ├── src/
│   │   ├── api/         # Typed fetch clients wrapping FastAPI
│   │   ├── components/  # Reusable UI components (Sidebar, BottomPanel, Map)
│   │   ├── state/       # Zustand stores (pipelineStore, uiStore)
│   │   └── types/       # TypeScript interfaces (contracts.ts)
│   └── package.json     # Node dependencies
│
├── prd.md               # Product Requirements Document
├── architecture.md      # Tech Stack and Software Architecture Design
├── design.md            # UX/UI Styling Tokens
├── phases.md            # Build Sequencing Checklist
└── rules.md             # Strict constraints and code guidelines
```

---

## 🚀 Setup & Installation

### 1. Backend Setup
Make sure you have Python 3.10+ installed.

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Frontend Setup
Make sure you have Node.js 18+ installed.

```bash
cd frontend
npm install
```

---

## 💻 Running the Application

To run the application locally for the demo:

**1. Start the FastAPI Backend**
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**2. Start the Vite Frontend**
In a new terminal window:
```bash
cd frontend
npm run dev
```

Navigate to `http://localhost:5173` in your browser. The frontend is automatically configured to proxy API requests to the backend on port 8000.

---

## 🧪 Testing

The backend includes a full test suite validating all data pipelines, mock ingestion routes, and error halting configurations.

```bash
cd backend
python -m pytest tests/ -v
```

---
*Developed for the Smart India Hackathon (SIH).*
