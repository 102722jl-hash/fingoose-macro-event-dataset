# FinGoose v2 CANDIDATE

## &#x72B6;&#x6001;

- &#x7248;&#x672C;&#xFF1A;`fingoose-macro-event-attribution-v2.0`
- &#x53D1;&#x5E03;&#x7EA7;&#x522B;&#xFF1A;`CANDIDATE`
- `candidate_ready=true`
- `formal_ready=false`
- v1 &#x6570;&#x636E;&#x548C;&#x5165;&#x53E3;&#x4FDD;&#x6301;&#x4E0D;&#x53D8;&#x3002;

v2 &#x5305;&#x542B; 10 &#x4E2A;&#x4E8B;&#x4EF6;&#x3001;21 &#x4E2A;&#x8BC1;&#x636E;&#x91CC;&#x7A0B;&#x7891;&#x3001;21 &#x4E2A;&#x4E8B;&#x4EF6;&#x9636;&#x6BB5;&#x3001;10 &#x5F20;&#x52A8;&#x6001;&#x4F20;&#x5BFC;&#x56FE;&#x3001;40 &#x6761;&#x5E02;&#x573A;&#x7A97;&#x53E3;&#x548C; 10 &#x4E2A;&#x4E09;&#x8D5B;&#x9053;&#x57FA;&#x51C6;&#x6848;&#x4F8B;&#x3002;`event-02/03/04` &#x4E3A;&#x5B8C;&#x6574;&#x793A;&#x4F8B;&#xFF1B;&#x5176;&#x4F59;&#x6848;&#x4F8B;&#x5206;&#x4E3A; 3 &#x4E2A;&#x9690;&#x85CF;&#x8BC4;&#x6D4B;&#x548C; 4 &#x4E2A;&#x6311;&#x6218;&#x96C6;&#x4E8B;&#x4EF6;&#x3002;

## &#x6570;&#x636E;&#x4EA7;&#x7269;

`data/market_event_attribution_v2_candidate/` &#x5305;&#x542B;&#xFF1A;

- `event_milestones.jsonl`
- `event_episodes.jsonl`
- `transmission_graphs.jsonl`
- `market_windows.jsonl`
- `benchmark_cases.jsonl`
- `hidden/benchmark_labels.jsonl`
- `source_manifest.jsonl`
- `summary.json`
- `validation_report.json`
- `manifest.json`

&#x6240;&#x6709;&#x4F20;&#x5BFC;&#x8FB9;&#x4FDD;&#x6301; `PROPOSED`&#x3002;&#x672A;&#x7ECF;&#x771F;&#x5B9E;&#x4EBA;&#x5DE5;&#x5BA1;&#x6838;&#x4E0D;&#x4F1A;&#x8F6C;&#x4E3A; `CONFIRMED`&#x3002;`MATERIAL/DOMINANT` &#x6DF7;&#x6742;&#x6837;&#x672C;&#x53EA;&#x8FDB;&#x5165;&#x6311;&#x6218;&#x96C6;&#x3002;&#x4E09;&#x4E2A;&#x8BC4;&#x5206;&#x8D5B;&#x9053;&#x4E0D;&#x751F;&#x6210;&#x7EFC;&#x5408;&#x603B;&#x5206;&#x3002;

## &#x884C;&#x60C5;&#x53E3;&#x5F84;

&#x539F;&#x59CB; FRED CSV &#x4F4D;&#x4E8E; `evidence_snapshots/macro_event_attribution_v1/market/fred/`&#xFF0C;9 &#x4E2A;&#x5E8F;&#x5217;&#x5747;&#x5DF2;&#x6309; SHA-256 &#x6838;&#x9A8C;&#x3002;v2 &#x4ECE;&#x539F;&#x59CB;&#x5FEB;&#x7167;&#x91CD;&#x7B97; `T60/T20/T1/D1/D3/D5/D20/M3`&#xFF0C;&#x9010;&#x70B9;&#x4FDD;&#x5B58;&#x65E5;&#x671F;&#x3001;&#x7EDD;&#x5BF9;&#x503C;&#x3001;&#x539F;&#x59CB;&#x53D8;&#x5316;&#x3001;&#x6807;&#x51C6;&#x5316;&#x53D8;&#x5316;&#x3001;&#x76F8;&#x5BF9;&#x53D8;&#x5316;&#x548C;&#x5386;&#x53F2;&#x5B89;&#x6170;&#x5242;&#x5206;&#x4F4D;&#x6570;&#x3002;&#x76F8;&#x5BF9;&#x53D8;&#x5316;&#x53EA;&#x4F7F;&#x7528;&#x9884;&#x5148;&#x6307;&#x5B9A;&#x7684;&#x53EF;&#x6BD4;&#x57FA;&#x51C6;&#xFF1B;&#x6CA1;&#x6709;&#x53EF;&#x9760;&#x57FA;&#x51C6;&#x65F6;&#x4FDD;&#x6301; `null`&#x3002;`calculation_basis` &#x540C;&#x65F6;&#x4FDD;&#x7559;&#x516C;&#x5F0F;&#x53E3;&#x5F84;&#x3001;&#x6765;&#x6E90;&#x8DEF;&#x5F84;&#x548C;&#x54C8;&#x5E0C;&#x3002;

## &#x542F;&#x52A8;&#x9875;&#x9762;

```powershell
.\START_UI_V2.ps1
```

&#x9ED8;&#x8BA4;&#x5730;&#x5740;&#xFF1A;`http://127.0.0.1:8782/`

v2 &#x9875;&#x9762;&#x4E0D;&#x8BFB;&#x53D6; `hidden/benchmark_labels.jsonl`&#x3002;&#x4E09;&#x4E2A;&#x5B8C;&#x6574;&#x793A;&#x4F8B;&#x5C55;&#x793A;&#x53CC;&#x65F6;&#x95F4;&#x3001;&#x9636;&#x6BB5;&#x3001;&#x4F20;&#x5BFC;&#x8FB9;&#x3001;&#x8BC1;&#x636E;&#x3001;&#x53CD;&#x8BC1;&#x3001;&#x5931;&#x6548;&#x6761;&#x4EF6;&#x548C;&#x516B;&#x4E2A;&#x884C;&#x60C5;&#x7A97;&#x53E3;&#xFF1B;&#x9690;&#x85CF;&#x4E0E;&#x6311;&#x6218;&#x4E8B;&#x4EF6;&#x53EA;&#x5C55;&#x793A;&#x8BC1;&#x636E;&#x8F93;&#x5165;&#x65F6;&#x95F4;&#x7EBF;&#x3001;&#x8D44;&#x4EA7;&#x5143;&#x6570;&#x636E;&#x548C; `T60/T20/T1`&#xFF0C;&#x4E0D;&#x8FD4;&#x56DE; gold milestone&#x3001;&#x5B8C;&#x6574;&#x4F20;&#x5BFC;&#x56FE;&#x3001;&#x4E8B;&#x540E;&#x884C;&#x60C5;&#x6216;&#x6DF7;&#x6742;&#x6807;&#x7B7E;&#x3002;

## &#x6784;&#x5EFA;&#x4E0E;&#x9A8C;&#x8BC1;

```powershell
$env:PYTHONPATH=(Resolve-Path 'code').Path
python code/build_fingoose_macro_event_attribution_v2.py
python -m unittest tests.test_fingoose_macro_event_attribution_v2 tests.test_build_fingoose_macro_event_attribution_v2 tests.test_fingoose_macro_event_v2_dashboard -v
```

`manifest.json` &#x8BB0;&#x5F55;&#x6BCF;&#x4E2A; v2 &#x4EA7;&#x7269;&#x7684; SHA-256 &#x548C;&#x8BB0;&#x5F55;&#x6570;&#x3002;`VERIFY_HANDOFF.ps1` &#x4ECD;&#x7528;&#x4E8E;&#x6838;&#x9A8C;&#x539F;&#x59CB; v1 &#x4EA4;&#x63A5;&#x5305;&#xFF0C;v2 &#x4E0D;&#x4FEE;&#x6539; v1 &#x6587;&#x4EF6;&#x3002;
