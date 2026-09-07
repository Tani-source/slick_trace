import pytest
from fastapi.testclient import TestClient
from app.main import app
import json
from app.config import PROTOTYPE_CACHE_DIR
import os

client = TestClient(app)

def test_prototype_endpoints_no_run_id_required():
    # Write a dummy cache file to avoid 404s
    os.makedirs(PROTOTYPE_CACHE_DIR, exist_ok=True)
    with open(os.path.join(PROTOTYPE_CACHE_DIR, "dark_ship.json"), "w") as f:
        json.dump({"prototype": True, "label": "test"}, f)
        
    # The endpoints should work without a run_id
    response = client.get("/api/prototype/dark-ship")
    assert response.status_code == 200
    assert response.json()["prototype"] is True
    
    response = client.get("/api/prototype/oil-type")
    assert response.status_code == 200
    assert response.json()["prototype"] is True

def test_prototype_endpoints_ignore_run_id():
    # If a run_id is provided, it shouldn't affect the response
    response = client.get("/api/prototype/dark-ship?run_id=123")
    assert response.status_code == 200
    assert response.json()["prototype"] is True
