from src.core.records.M001 import get_m001_record
from src.core.records.M002 import get_m002_record
from src.core.records.M003 import get_m003_record
from src.core.records.M004 import get_m004_record
from src.core.records.M005 import get_m005_record

MECHANISM_LOADERS = {
    "M001": get_m001_record,
    "M002": get_m002_record,
    "M003": get_m003_record,
    "M004": get_m004_record,
    "M005": get_m005_record,
}

def get_record(mechanism_id: str):
    loader = MECHANISM_LOADERS.get(mechanism_id)
    if loader:
        return loader()
    return None
