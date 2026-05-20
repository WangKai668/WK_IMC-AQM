import re
import argparse
import json
import csv

def parse_args():
    p = argparse.ArgumentParser(description="Parse SwitchMMU PRED / FCS / QLA logs")
    p.add_argument("--log", required=True, help="Path to SwitchMMU log file (with leading timestamps in ns)")
    p.add_argument("--out-dir", default=".", help="Output directory for CSV/JSON files")
    return p.parse_args()


def extract_kv_pairs(s):
    # 捕获 key=value 或 key: value 形式的简单键值对
    kv = dict(re.findall(r"(\b[a-zA-Z_][a-zA-Z0-9_]*)\s*[:=]\s*([-+]?[0-9]*\.?[0-9]+)", s))
    return kv


def extract_numbers(s):
    return re.findall(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?", s)


def categorize_message(msg):
    low = msg.lower()
    if "fcs" in low or "fingerprint" in low:
        return "fcs"
    if "qla" in low or "phase" in low or "utility" in low or "tqla" in low:
        return "qla"
    if "pred" in low or "tfcs" in low or "tqla" in low or "p_pred" in low:
        return "pred"
    return "other"


def main():
    args = parse_args()
    ts_re = re.compile(r"^\s*(\d+)\s+(.*)$")

    buckets = {"pred": [], "fcs": [], "qla": [], "other": []}

    with open(args.log, "r", errors="ignore") as fh:
        for ln in fh:
            m = ts_re.match(ln)
            if not m:
                continue
            ts_ns = int(m.group(1))
            t_ms = ts_ns / 1e6
            msg = m.group(2).strip()

            cat = categorize_message(msg)
            kv = extract_kv_pairs(msg)
            nums = extract_numbers(msg)

            entry = {
                "time_ms": t_ms,
                "msg": msg,
                "kv": kv,
                "numbers": nums
            }
            buckets[cat].append(entry)

    # 输出为 CSV + JSON
    for name, items in buckets.items():
        csv_path = f"{args.out_dir}/parsed_{name}.csv"
        json_path = f"{args.out_dir}/parsed_{name}.json"

        # 写 CSV: time_ms, kv(json), numbers(json), msg
        with open(csv_path, "w", newline="") as cf:
            writer = csv.writer(cf)
            writer.writerow(["time_ms", "kv_json", "numbers_json", "msg"])
            for it in items:
                writer.writerow([it["time_ms"], json.dumps(it["kv"]), json.dumps(it["numbers"]), it["msg"]])

        with open(json_path, "w") as jf:
            json.dump(items, jf, indent=2)

        print(f"Wrote {len(items)} entries to {csv_path} and {json_path}")

    # 简要汇总
    for name in ["pred", "fcs", "qla", "other"]:
        print(f"{name}: {len(buckets[name])} entries")


if __name__ == "__main__":
    main()
