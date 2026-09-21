#!/usr/bin/env python3
"""
Human Approval Gate for ASTRA Project.
Usage: python tools/human_approve.py --stage S0_AUDIT --action approve --reason "Your reason here"
"""

import argparse
import json
import hashlib
import os
from datetime import datetime, timezone

# Determine paths relative to project root (parent of tools/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(PROJECT_ROOT, 'astra', 'GOVERNANCE_REGISTRY.json')
APPROVAL_LOG_PATH = os.path.join(PROJECT_ROOT, 'astra', 'approval_log.jsonl')

def load_registry():
    if not os.path.exists(REGISTRY_PATH):
        return {"stages": {}, "current_stage": "S0_AUDIT"}
    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_registry(reg):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(reg, f, indent=2, ensure_ascii=False)

def log_approval(stage, action, reason, operator="HUMAN"):
    os.makedirs(os.path.dirname(APPROVAL_LOG_PATH), exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "action": action,
        "reason": reason,
        "operator": operator,
        "hash": ""
    }
    # Create a hash of the entry to ensure integrity
    entry_str = json.dumps(entry, sort_keys=True, ensure_ascii=False)
    entry["hash"] = hashlib.sha256(entry_str.encode()).hexdigest()
    
    with open(APPROVAL_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return entry["hash"]

def main():
    parser = argparse.ArgumentParser(description="Human Approval Gate")
    parser.add_argument("--stage", required=True, help="Stage ID (e.g., S0_AUDIT)")
    parser.add_argument("--action", choices=["approve", "reject", "request_changes"], required=True)
    parser.add_argument("--reason", required=True, help="Reason for this action")
    
    args = parser.parse_args()
    
    reg = load_registry()
    
    if args.action == "approve":
        reg["stages"][args.stage] = {
            "status": "PASS",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_by": "HUMAN",
            "reason": args.reason
        }
        h = log_approval(args.stage, "APPROVE", args.reason)
        print(f"✅ Stage {args.stage} APPROVED.")
        print(f"   Hash: {h}")
        print(f"   Reason: {args.reason}")
        
    elif args.action == "reject":
        reg["stages"][args.stage] = {
            "status": "FAIL",
            "rejected_at": datetime.now(timezone.utc).isoformat(),
            "rejected_by": "HUMAN",
            "reason": args.reason
        }
        h = log_approval(args.stage, "REJECT", args.reason)
        print(f"❌ Stage {args.stage} REJECTED.")
        print(f"   Hash: {h}")
        print(f"   Reason: {args.reason}")

    elif args.action == "request_changes":
        reg["stages"][args.stage] = {
            "status": "BLOCKED",
            "blocked_at": datetime.now(timezone.utc).isoformat(),
            "blocked_by": "HUMAN",
            "reason": args.reason
        }
        h = log_approval(args.stage, "REQUEST_CHANGES", args.reason)
        print(f"⚠️ Stage {args.stage} BLOCKED (Changes Requested).")
        print(f"   Hash: {h}")
        print(f"   Reason: {args.reason}")

    save_registry(reg)
    print("\nRegistry updated.")

if __name__ == "__main__":
    main()
