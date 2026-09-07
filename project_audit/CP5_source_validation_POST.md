# CP5 SOURCE VALIDATION - POST run
Fixtures: frozen Sep-3 control windows (regression fixtures only, NOT CP5 data).
Structural facts only: hashes / counts / day attribution. No performance metrics.
window_1_df.csv: A1 hash=41793652169bd58c events=226 | A2 hash=c5772337230b374e event_bars=5544 event_days=31 (days: 32/33 eligible) ineligible_event_days=0
window_2_df.csv: A1 hash=773e47af9a052acc events=227 | A2 hash=d5f2df2415e5b56f event_bars=2865 event_days=28 (days: 31/32 eligible) ineligible_event_days=0
window_3_df.csv: A1 hash=c298d76c7e595d60 events=227 | A2 hash=d957c954d5a99c22 event_bars=382 event_days=18 (days: 32/33 eligible) ineligible_event_days=0
window_4_df.csv: A1 hash=aa2b54ed4a8a9ba2 events=225 | A2 hash=86aea480546be7f6 event_bars=331 event_days=26 (days: 31/32 eligible) ineligible_event_days=0
window_5_df.csv: A1 hash=3993fa2bb6f9ccfa events=228 | A2 hash=fbaa631655e6a074 event_bars=366 event_days=27 (days: 32/33 eligible) ineligible_event_days=0
window_6_df.csv: A1 hash=7954df3f0b62ecdc events=246 | A2 hash=16f9f61db504c453 event_bars=475 event_days=31 (days: 31/32 eligible) ineligible_event_days=0
A1 NaN synthetic: no_crash=True first30_all_hold=True len_ok=True hash=44fc7284074b9231

```json
{
 "tag": "POST",
 "windows": [
  {
   "window": "window_1_df.csv",
   "rows": 14400,
   "a1_hash": "41793652169bd58c",
   "a1_events": 226,
   "a2_hash": "c5772337230b374e",
   "a2_event_bars": 5544,
   "a2_event_days": 31,
   "total_days": 33,
   "eligible_days": 32,
   "a2_event_days_on_ineligible": []
  },
  {
   "window": "window_2_df.csv",
   "rows": 14400,
   "a1_hash": "773e47af9a052acc",
   "a1_events": 227,
   "a2_hash": "d5f2df2415e5b56f",
   "a2_event_bars": 2865,
   "a2_event_days": 28,
   "total_days": 32,
   "eligible_days": 31,
   "a2_event_days_on_ineligible": []
  },
  {
   "window": "window_3_df.csv",
   "rows": 14400,
   "a1_hash": "c298d76c7e595d60",
   "a1_events": 227,
   "a2_hash": "d957c954d5a99c22",
   "a2_event_bars": 382,
   "a2_event_days": 18,
   "total_days": 33,
   "eligible_days": 32,
   "a2_event_days_on_ineligible": []
  },
  {
   "window": "window_4_df.csv",
   "rows": 14400,
   "a1_hash": "aa2b54ed4a8a9ba2",
   "a1_events": 225,
   "a2_hash": "86aea480546be7f6",
   "a2_event_bars": 331,
   "a2_event_days": 26,
   "total_days": 32,
   "eligible_days": 31,
   "a2_event_days_on_ineligible": []
  },
  {
   "window": "window_5_df.csv",
   "rows": 14400,
   "a1_hash": "3993fa2bb6f9ccfa",
   "a1_events": 228,
   "a2_hash": "fbaa631655e6a074",
   "a2_event_bars": 366,
   "a2_event_days": 27,
   "total_days": 33,
   "eligible_days": 32,
   "a2_event_days_on_ineligible": []
  },
  {
   "window": "window_6_df.csv",
   "rows": 14400,
   "a1_hash": "7954df3f0b62ecdc",
   "a1_events": 246,
   "a2_hash": "16f9f61db504c453",
   "a2_event_bars": 475,
   "a2_event_days": 31,
   "total_days": 32,
   "eligible_days": 31,
   "a2_event_days_on_ineligible": []
  }
 ],
 "a1_nan_test": {
  "no_crash": true,
  "first30_all_hold": true,
  "len_ok": true,
  "hash": "44fc7284074b9231"
 }
}
```
