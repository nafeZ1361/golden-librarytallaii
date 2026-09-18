# module/state_io.py (فایل جداگانه)
"""
ماژول ذخیره و بارگذاری state به/از فایل JSON
با پشتیبانی از انواع NumPy
"""

import json
import numpy as np
from typing import Any, Dict


class NumpyEncoder(json.JSONEncoder):
    """
    Encoder سفارشی برای تبدیل انواع NumPy به انواع Python استاندارد
    این کلاس مشکل serialize کردن np.int64, np.float64 و... را حل می‌کند
    """
    def default(self, obj):
        # تبدیل اعداد صحیح NumPy به int
        if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(obj)
        
        # تبدیل اعداد اعشاری NumPy به float
        if isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
            return float(obj)
        
        # تبدیل آرایه NumPy به لیست
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        
        # برای بقیه موارد، از encoder پیش‌فرض استفاده شود
        return super().default(obj)


def save_state(state: Dict[str, Any], filename: str = "bot_state.json") -> None:
    """
    ذخیره state در فایل JSON
    
    پارامترها:
        state: دیکشنری state برای ذخیره
        filename: نام فایل (پیش‌فرض: bot_state.json)
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(
                state, 
                f, 
                cls=NumpyEncoder,  # استفاده از encoder سفارشی
                ensure_ascii=False,  # پشتیبانی از فارسی
                indent=2  # فرمت خوانا
            )
    except Exception as e:
        print(f"[ERROR] Failed to save state: {e}")


def load_state(filename: str = "bot_state.json") -> Dict[str, Any]:
    """
    بارگذاری state از فایل JSON
    
    پارامترها:
        filename: نام فایل (پیش‌فرض: bot_state.json)
    
    خروجی:
        دیکشنری state (اگر فایل وجود نداشت یا خطا رخ داد، {} برمی‌گرداند)
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # اگر فایل وجود ندارد (اولین اجرا)، state خالی برگردان
        return {}
    except Exception as e:
        print(f"[ERROR] Failed to load state: {e}")
        return {}