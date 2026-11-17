from __future__ import annotations

import argparse
import json

from .service import BookingPrecheckService, SingleAgentBookingPrecheckService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the booking-precheck teaching agent")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case", help="Golden case ID, for example TC-014")
    group.add_argument("--business-case", help="Business acceptance case ID, for example BA-005")
    group.add_argument("--document-pack", help="Document pack ID, for example DP-003")
    group.add_argument("--agent-document-pack", help="Run a PDF pack through the real single Agent, for example DP-003")
    parser.add_argument("--stage", default="S1", help="Document-pack stage")
    args = parser.parse_args()
    if args.case:
        result = BookingPrecheckService().run_case(args.case)
    elif args.business_case:
        result = BookingPrecheckService().run_business_case(args.business_case)
    elif args.document_pack:
        result = BookingPrecheckService().run_document_pack(args.document_pack, args.stage)
    else:
        result = SingleAgentBookingPrecheckService().run_document_pack(args.agent_document_pack, args.stage)
    print(json.dumps(result, ensure_ascii=False, indent=2))
