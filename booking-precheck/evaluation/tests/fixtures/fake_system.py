import argparse
import json


parser = argparse.ArgumentParser()
parser.add_argument("--case")
args = parser.parse_args()
print(json.dumps({
    "technical_status": "COMPLETED",
    "final_status": "PRECHECK_PASS",
    "reason_codes": [],
    "routing_queues": [],
    "required_facts": [],
    "matched_rules": [],
    "evidence": [],
    "metrics": {
        "duration_ms": 7,
        "model_call_count": 1,
        "input_tokens": 10,
        "output_tokens": 5
    }
}))
