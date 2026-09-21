# استراتژی‌های پله‌ای (Martingale/Grid) - GOLD-LIBRARY

"""
این فایل مخصوص استراتژی‌های مارتینگل و گرید است که توسط کاربر اضافه می‌شود.
تمامی توابع باید از قوانین ایمنی ASTRA پیروی کنند.
"""

def calculate_grid_levels(entry_price, grid_step, num_levels, direction='BUY'):
    """
    محاسبه سطوح گرید برای ورود پله‌ای
    
    Parameters:
        entry_price: قیمت ورود اولیه
        grid_step: فاصله هر پله (به پیپ)
        num_levels: تعداد پله‌ها
        direction: جهت معامله ('BUY' یا 'SELL')
    
    Returns:
        list of dict: [{level: 1, price: 2000.5, lot: 0.01}, ...]
    """
    levels = []
    for i in range(num_levels):
        if direction == 'BUY':
            price = entry_price - (grid_step * i)
        else:  # SELL
            price = entry_price + (grid_step * i)
        
        # محاسبه لات پله‌ای (مارتینگل ساده)
        lot = 0.01 * (2 ** i)  # هر پله دو برابر پله قبل
        
        levels.append({
            'level': i + 1,
            'price': round(price, 2),
            'lot': round(lot, 2),
            'direction': direction
        })
    
    return levels


def calculate_take_profit_grid(levels, tp_distance, direction='BUY'):
    """
    محاسبه نقاط خروج برای هر پله گرید
    
    Parameters:
        levels: لیست سطوح گرید (خروجی calculate_grid_levels)
        tp_distance: فاصله سود به پیپ
        direction: جهت معامله
    
    Returns:
        list of dict: [{level: 1, tp_price: 2005.5}, ...]
    """
    tp_levels = []
    for level in levels:
        if direction == 'BUY':
            tp_price = level['price'] + tp_distance
        else:  # SELL
            tp_price = level['price'] - tp_distance
        
        tp_levels.append({
            'level': level['level'],
            'tp_price': round(tp_price, 2),
            'lot': level['lot']
        })
    
    return tp_levels


def calculate_total_risk(levels, stop_loss_distance):
    """
    محاسبه ریسک کل استراتژی گرید
    
    Parameters:
        levels: لیست سطوح گرید
        stop_loss_distance: فاصله استاپ لاس نهایی به پیپ
    
    Returns:
        dict: {total_lot, total_risk_usd, risk_per_level}
    """
    total_lot = sum(level['lot'] for level in levels)
    
    # ریسک کل = مجموع لات‌ها × فاصله استاپ
    total_risk_units = total_lot * stop_loss_distance
    total_risk_usd = total_risk_units * 10  # برای XAUUSD، هر پیپ ≈ 10 دلار بر اونس
    
    risk_per_level = []
    for level in levels:
        risk = level['lot'] * stop_loss_distance * 10
        risk_per_level.append({
            'level': level['level'],
            'risk_usd': round(risk, 2)
        })
    
    return {
        'total_lot': round(total_lot, 2),
        'total_risk_usd': round(total_risk_usd, 2),
        'risk_per_level': risk_per_level
    }


def check_grid_entry_conditions(df, direction='BUY'):
    """
    بررسی شرایط ورود به گرید
    
    شرایط نمونه:
        - RSI < 30 برای BUY
        - RSI > 70 برای SELL
        - قیمت به حمایت/مقاومت رسیده باشد
    
    Parameters:
        df: DataFrame شامل داده‌های قیمتی و اندیکاتورها
        direction: جهت معامله
    
    Returns:
        bool: True اگر شرایط ورود برقرار بود
    """
    if len(df) < 2:
        return False
    
    last_row = df.iloc[-1]
    
    if direction == 'BUY':
        # شرط نمونه: RSI اشباع فروش
        if 'RSI' in df.columns:
            if last_row['RSI'] < 30:
                return True
        # اگر RSI نبود، فقط بر اساس قیمت تصمیم بگیر
        return True
    
    elif direction == 'SELL':
        # شرط نمونه: RSI اشباع خرید
        if 'RSI' in df.columns:
            if last_row['RSI'] > 70:
                return True
        return True
    
    return False


def manage_grid_positions(current_positions, levels, current_price):
    """
    مدیریت پوزیشن‌های باز گرید
    
    Parameters:
        current_positions: لیست پوزیشن‌های باز فعلی
        levels: سطوح گرید تعریف شده
        current_price: قیمت فعلی بازار
    
    Returns:
        dict: {action: 'HOLD'/'ADD'/'CLOSE_ALL', details: {...}}
    """
    if not current_positions:
        return {'action': 'HOLD', 'details': 'No positions'}
    
    # بررسی اینکه آیا همه پله‌ها پر شده‌اند
    filled_levels = len(current_positions)
    total_levels = len(levels)
    
    if filled_levels < total_levels:
        # بررسی اینکه آیا قیمت به پله بعدی رسیده
        next_level_idx = filled_levels
        next_level_price = levels[next_level_idx]['price']
        
        # بررسی فاصله قیمت فعلی تا پله بعدی
        price_diff = abs(current_price - next_level_price)
        grid_step = abs(levels[1]['price'] - levels[0]['price']) if len(levels) > 1 else grid_step
        
        if price_diff <= grid_step * 0.1:  # تحمل ۱۰٪ خطا
            return {
                'action': 'ADD',
                'details': {
                    'level': next_level_idx + 1,
                    'price': next_level_price,
                    'lot': levels[next_level_idx]['lot']
                }
            }
    
    # بررسی سود کل
    total_profit = sum(pos.get('profit', 0) for pos in current_positions)
    if total_profit > 50:  # مثال: اگر سود کل بیشتر از ۵۰ دلار
        return {
            'action': 'CLOSE_ALL',
            'details': {
                'reason': 'Take Profit reached',
                'total_profit': total_profit
            }
        }
    
    return {'action': 'HOLD', 'details': 'Waiting for next level or TP'}


# مثال استفاده در استراتژی
if __name__ == "__main__":
    # مثال: گرید خرید با ۵ پله، فاصله ۲ پیپ
    entry_price = 2030.0
    grid_step = 2.0
    num_levels = 5
    
    levels = calculate_grid_levels(entry_price, grid_step, num_levels, 'BUY')
    print("سطوح گرید:")
    for lvl in levels:
        print(f"  پله {lvl['level']}: قیمت={lvl['price']}, لات={lvl['lot']}")
    
    # محاسبه نقاط خروج
    tp_levels = calculate_take_profit_grid(levels, tp_distance=5.0, direction='BUY')
    print("\nنقاط خروج:")
    for tp in tp_levels:
        print(f"  پله {tp['level']}: TP={tp['tp_price']}")
    
    # محاسبه ریسک
    risk_info = calculate_total_risk(levels, stop_loss_distance=20.0)
    print(f"\nریسک کل:")
    print(f"  مجموع لات: {risk_info['total_lot']}")
    print(f"  ریسک دلاری: ${risk_info['total_risk_usd']}")
