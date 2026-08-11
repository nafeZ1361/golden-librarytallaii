from module.mt5 import *
from module.indicators import *



def tp1_risk_free(position):
    price = mt5.symbol_info_tick(position.symbol)
    #buy
    if position.type == 0 and position.price_open != position.sl :
        tp1_price = position.price_open + (position.price_open - position.sl)
        if price.ask >= tp1_price:
            modify_stop(position.ticket , position.price_open)

    #sell
    if position.type == 1 and position.price_open != position.sl :
        tp1_price = position.price_open - (position.sl - position.price_open)
        if price.bid <= tp1_price:
            modify_stop(position.ticket , position.price_open)



def tp1_risk_free_save_profit(position):
    price = mt5.symbol_info_tick(position.symbol)
    #buy
    if position.type == 0 and position.price_open != position.sl :
        tp1_price = position.price_open + (position.price_open - position.sl)
        if price.ask >= tp1_price:
            modify_stop(position.ticket , position.price_open)
            if position.volume != 0.01 :
                close_half_vol_order(position.ticket)

    #sell
    if position.type == 1 and position.price_open != position.sl :
        tp1_price = position.price_open - (position.sl - position.price_open)
        if price.bid <= tp1_price:
            modify_stop(position.ticket , position.price_open)
            if position.volume != 0.01 :
                close_half_vol_order(position.ticket)



def tp1_save_profit(position):
    price = mt5.symbol_info_tick(position.symbol)
    #buy
    if position.type == 0 and position.price_open != position.sl :
        tp1_price = position.price_open + (position.price_open - position.sl)
        if price.ask >= tp1_price:
            if position.volume != 0.01 :
                close_half_vol_order(position.ticket)

    #sell
    if position.type == 1 and position.price_open != position.sl :
        tp1_price = position.price_open - (position.sl - position.price_open)
        if price.bid <= tp1_price:
            if position.volume != 0.01 :
                close_half_vol_order(position.ticket)



def tp2_risk_free(position):
    price = mt5.symbol_info_tick(position.symbol)
    #buy
    if position.type == 0 and position.price_open != position.sl :
        tp2_price = position.price_open + ((position.price_open - position.sl)*2)
        if price.ask >= tp2_price:
            modify_stop(position.ticket , position.price_open)

    #sell
    if position.type == 1 and position.price_open != position.sl :
        tp2_price = position.price_open - ((position.sl - position.price_open)*2)
        if price.bid <= tp2_price:
            modify_stop(position.ticket , position.price_open)



def tp2_risk_free_save_profit(position):
    price = mt5.symbol_info_tick(position.symbol)
    #buy
    if position.type == 0 and position.price_open != position.sl :
        tp2_price = position.price_open + ((position.price_open - position.sl)*2)
        if price.ask >= tp2_price:
            modify_stop(position.ticket , position.price_open)
            if position.volume != 0.01 :
                close_half_vol_order(position.ticket)

    #sell
    if position.type == 1 and position.price_open != position.sl :
        tp2_price = position.price_open - ((position.sl - position.price_open)*2)
        if price.bid <= tp2_price:
            modify_stop(position.ticket , position.price_open)
            if position.volume != 0.01 :
                close_half_vol_order(position.ticket)



def smartTP(tf , position):
    rsi_val = rsi(position.symbol , tf , 'ca')[-2]
    cnd = check_candle(position.symbol , tf ,-2 ,'ha')
    if position.type == 0 and rsi_val > 70 and cnd == 'short':
        close_order(position.ticket)
    if position.type == 1 and rsi_val < 30 and cnd == 'long':
        close_order(position.ticket)



def smartSL(symbol , tf , maxSl , minSL):
    atr_val = ( Atr(symbol , tf )[-2] ) * 2
    if atr_val > maxSl : 
        return maxSl
    elif atr_val < minSL :
        return minSL
    else:
        return round(atr_val , 6)
    