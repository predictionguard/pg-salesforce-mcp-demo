import math
import pandas as pd


def clean_for_json(obj):
    """Recursively clean object for JSON serialization."""
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, (float, int)):
        try:
            if math.isnan(obj) or math.isinf(obj):
                return None
        except (TypeError, ValueError):
            pass
        return float(obj) if isinstance(obj, float) else int(obj)
    elif obj is None:
        return None
    else:
        try:
            if pd.isna(obj):
                return None
        except (TypeError, ValueError):
            pass
    return obj
