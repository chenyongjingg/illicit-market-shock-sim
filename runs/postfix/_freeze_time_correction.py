
import json, os
ROOT="/root/mdpi3"; M=os.path.join(ROOT,"MANIFEST.artifacts.jsonl")
rows=[json.loads(l) for l in open(M,encoding="utf-8") if l.strip()]
if not any((r.get("extra") or {}).get("tag")=="sealed_20261101_correction" for r in rows):
    row={"name":"freeze_time_correction","path":M,"cmd":"correction to the four rows tagged sealed_20261101",
         "t":"2026-11-01T06:58:35Z","sha256":None,"bytes":None,"inputs":[],
         "extra":{"tag":"sealed_20261101_correction","note":
         "The four rows tagged sealed_20261101 carry t=2026-11-01T07:02:00Z. That value was TYPED, not measured: the pod clock read 06:58:35Z when the freeze ran (date -u, same command block). The sealed sha 353930c3... and bytes 148023 are correct; only the timestamp field is wrong. Measured freeze time = 2026-11-01T06:58:35Z. This row is the correction and it is append-only, per D-109/D-112. Its own sha256 is null because it describes a row, not a file -- and a null sha row is not a version of an artifact (D-102)."}}
    open(M,"a",encoding="utf-8").write(json.dumps(row,ensure_ascii=False)+"\n")
    print("appended correction")
print("lines", sum(1 for _ in open(M,encoding="utf-8")))
