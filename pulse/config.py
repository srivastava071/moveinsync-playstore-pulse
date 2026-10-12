"""Which apps to track. Add or remove entries here; everything else adapts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "reviews.db"
OUTPUT_DIR = ROOT / "output"

# role: "own" apps are analyzed in depth, "competitor" apps are used as a benchmark only.
APPS = [
    {"id": "com.moveinsync.ets", "name": "MoveInSync (Employee)", "role": "own"},
    {"id": "com.moveinsync.driver.lite", "name": "MoveInSync Partner Lite (Driver)", "role": "own"},
    {"id": "com.moveinsync.driver.dco", "name": "MoveInSync Driver Partner", "role": "own"},
    {"id": "field.moveinsync.ets", "name": "MoveInSync Field", "role": "own"},
    {"id": "in.mtap.iincube.safetrax.commuter", "name": "Safetrax Commuter", "role": "competitor"},
    {"id": "com.nivaata.routematic.tripsheet", "name": "Routematic", "role": "competitor"},
]

PRIMARY_APP = "com.moveinsync.ets"

LANG = "en"
COUNTRY = "in"
