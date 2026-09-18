import unittest
import pandas as pd
from module.timeframe_data import resample_m1_ohlcv

class TimeframeDataTests(unittest.TestCase):
    def test_resamples_m1_to_three_minute_deterministically(self):
        df=pd.DataFrame({"time":pd.date_range("2026-01-01",periods=6,freq="min"),"open":[1,2,3,4,5,6],"high":[2,3,4,5,6,7],"low":[0,1,2,3,4,5],"close":[1.5,2.5,3.5,4.5,5.5,6.5],"tick_volume":[1,2,3,4,5,6]})
        out=resample_m1_ohlcv(df,"3m")
        self.assertEqual(len(out),2); self.assertEqual(out.loc[0,"open"],1); self.assertEqual(out.loc[0,"high"],4); self.assertEqual(out.loc[0,"low"],0); self.assertEqual(out.loc[0,"volume"],6)

if __name__ == "__main__": unittest.main()
