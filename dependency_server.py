from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import json
from pathlib import Path
from datetime import datetime

app = FastAPI()
FILE = Path("dependencies.json")

# Allow frontend JS (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Helpers ----------
def load_json():
    if FILE.exists() and FILE.stat().st_size > 0:
        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    # default structure
    return {
        "name": "my-python-project",
        "version": "0.1.0",
        "private": True,
        "private_dependencies": {},
        "dependencies": {},
        "history": []
    }

def save_json(data):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ---------- Routes ----------
@app.get("/dependencies")
def get_dependencies():
    return load_json()

@app.post("/dependencies")
def add_dependency(
    name: str = Query(...),
    version: str = Query("latest"),
    dep_type: str = Query("global")  # "global" or "local"
):
    data = load_json()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if dep_type == "local":
        data["private_dependencies"][name] = version
    else:
        data["dependencies"][name] = version

    data["history"].append({
        "date": timestamp,
        "installed": [f"{name}=={version}"],
        "type": dep_type
    })

    save_json(data)
    return {"message": f"{name} added to {dep_type}", "data": data}

@app.delete("/dependencies/{dep_type}/{name}")
def delete_dependency(dep_type: str, name: str):
    data = load_json()

    if dep_type == "local":
        if name not in data["private_dependencies"]:
            raise HTTPException(status_code=404, detail=f"{name} not found in private deps")
        del data["private_dependencies"][name]
    else:
        if name not in data["dependencies"]:
            raise HTTPException(status_code=404, detail=f"{name} not found in global deps")
        del data["dependencies"][name]

    save_json(data)
    return {"message": f"{name} removed from {dep_type}", "data": data}
