import json
import sys


for line in sys.stdin:
    request = json.loads(line)
    response = {
        "protocol_version": "booking-precheck-eval/v1",
        "request_id": request["request_id"],
        "technical_status": "COMPLETED",
        "result": {
            "technical_status": "COMPLETED",
            "final_status": "PRECHECK_PASS",
            "reason_codes": [],
            "routing_queues": [],
            "required_facts": [],
            "matched_rules": [],
            "evidence": [],
            "metrics": {
                "duration_ms": 10,
                "model_call_count": 1,
                "input_tokens": 5,
                "output_tokens": 2
            }
        },
        "facts": {"documents": {}},
        "telemetry": {
            "duration_ms": 10,
            "model_call_count": 1,
            "input_tokens": 5,
            "output_tokens": 2,
            "trace_id": "trace-1"
        }
    }
    print(json.dumps(response), flush=True)
