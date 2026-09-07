# module/state_io.py
import json
import numpy as np
from typing import Any, Dict


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def save_state(state: Dict[str, Any], filename: str = "bot_state.json") -> None:
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(state, f, cls=NumpyEncoder, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save state: {e}")


def load_state(filename: str = "bot_state.json") -> Dict[str, Any]:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"[ERROR] Failed to load state: {e}")
        return {}
