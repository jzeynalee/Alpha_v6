from src.core.records.M001 import get_m001_record
from src.core.records.M002 import get_m002_record
from src.core.records.M003 import get_m003_record
from src.core.records.M004 import get_m004_record
from src.core.records.M005 import get_m005_record
from src.core.records.M006 import get_m006_record
from src.core.records.M007 import get_m007_record
from src.core.records.M008 import get_m008_record
from src.core.records.M009 import get_m009_record
from src.core.records.M010 import get_m010_record
from src.core.records.M011 import get_m011_record
from src.core.records.M012 import get_m012_record
from src.core.records.M013 import get_m013_record
from src.core.records.M014 import get_m014_record
from src.core.records.M015 import get_m015_record

MECHANISM_LOADERS = {
    "M001": get_m001_record,
    "M002": get_m002_record,
    "M003": get_m003_record,
    "M004": get_m004_record,
    "M005": get_m005_record,
    "M006": get_m006_record,
    "M007": get_m007_record,
    "M008": get_m008_record,
    "M009": get_m009_record,
    "M010": get_m010_record,
    "M011": get_m011_record,
    "M012": get_m012_record,
    "M013": get_m013_record,
    "M014": get_m014_record,
    "M015": get_m015_record,
}

def get_record(mechanism_id: str):
    loader = MECHANISM_LOADERS.get(mechanism_id)
    if loader:
        return loader()
    return None
