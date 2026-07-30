from pathlib import Path

APP_NAME = "LeipzigerFlow"
VERSION = "2026.22.0"

BASE_DIR = Path(__file__).resolve().parents[3]

DATA_DIR = BASE_DIR / "data"
LOG_DIR = DATA_DIR / "logs"

DATABASE_FILE = DATA_DIR / "leipzigerflow.db"

AVERAGE_SPEED = 65
DEFAULT_LOADING_TIME = 60
DEFAULT_UNLOADING_TIME = 60
# Routing / Entfernungswerk
# URLs can be replaced by an internal OSRM/Nominatim server without changing the planner.
ROUTING_ENABLED = True
ROUTING_OSRM_URL = "https://router.project-osrm.org"
ROUTING_GEOCODER_URL = "https://nominatim.openstreetmap.org/search"
ROUTING_CACHE_DAYS = 180
ROUTING_DEFAULT_DURATION_MINUTES = 60
# Routing
ROUTING_FALLBACK_SPEED_KMH = 65
ROUTING_REQUEST_TIMEOUT = 10
ROUTING_CACHE_ENABLED = True
