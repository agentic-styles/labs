# Booking Precheck Documentation and Consistency Standard

Document ID: POL-002
CNSHA to AEJEA / TRAIN-ME1 - version 1.0

Synthetic training policy only. Not a real carrier, port, or regulatory requirement.

## Applicability

- Carrier: TRAINING-LINE
- Route: CNSHA to AEJEA
- Service: TRAIN-ME1
- Effective: 2026-08-01 through 2026-12-31

## 1. Dangerous goods require preliminary DGD

Rule ID: DOC-DGD-REQUIRED
Policy statement: Dangerous-goods bookings must provide a preliminary DGD.
Operational response: REQUIRE_INFORMATION
Responsible queue: DOCUMENT_DESK

## 2. Dangerous goods require SDS Extract

Rule ID: DOC-SDS-REQUIRED
Policy statement: Dangerous-goods bookings must provide an SDS Extract.
Operational response: REQUIRE_INFORMATION
Responsible queue: DOCUMENT_DESK

## 3. preliminary DGD requires UN Number

Rule ID: DOC-DGD-UN-REQUIRED
Policy statement: The preliminary DGD must contain a valid UN Number.
Operational response: REQUIRE_INFORMATION
Responsible queue: DOCUMENT_DESK

## 4. preliminary DGD requires Proper Shipping Name

Rule ID: DOC-DGD-PSN-REQUIRED
Policy statement: The preliminary DGD must contain a Proper Shipping Name.
Operational response: REQUIRE_INFORMATION
Responsible queue: DOCUMENT_DESK

## 5. SDS Extract requires Section 14

Rule ID: DOC-SDS-S14-REQUIRED
Policy statement: The SDS Extract must contain transport information in Section 14.
Operational response: REQUIRE_INFORMATION
Responsible queue: DOCUMENT_DESK

## 6. SDS Extract freshness limit

Rule ID: DOC-SDS-FRESHNESS
Policy statement: The SDS Extract must not be older than 24 months at submission.
Operational response: REQUIRE_INFORMATION
Responsible queue: DOCUMENT_DESK

## 7. Booking requires consignee

Rule ID: DOC-CONSIGNEE-REQUIRED
Policy statement: The Booking Request must identify a consignee.
Operational response: REQUIRE_INFORMATION
Responsible queue: DOCUMENT_DESK

## 8. Booking and preliminary DGD UN Number consistency

Rule ID: CON-BOOKING-DGD-UN
Policy statement: Booking Request and preliminary DGD UN Numbers must match.
Operational response: MANUAL_REVIEW
Responsible queue: DG_DESK

## 9. preliminary DGD and SDS Extract UN Number consistency

Rule ID: CON-DGD-SDS-UN
Policy statement: preliminary DGD and SDS Extract UN Numbers must match.
Operational response: MANUAL_REVIEW
Responsible queue: DG_DESK

## 10. preliminary DGD and SDS Extract IMDG Class consistency

Rule ID: CON-DGD-SDS-CLASS
Policy statement: preliminary DGD and SDS Extract IMDG classes must match.
Operational response: MANUAL_REVIEW
Responsible queue: DG_DESK

## 11. Gross-weight tolerance

Rule ID: CON-GROSS-WEIGHT
Policy statement: Booking and preliminary DGD gross-weight variance must not exceed 2 percent.
Operational response: MANUAL_REVIEW
Responsible queue: DOCUMENT_DESK

## 12. Package-count consistency

Rule ID: CON-PACKAGE-COUNT
Policy statement: Booking and preliminary DGD package counts must match.
Operational response: MANUAL_REVIEW
Responsible queue: DOCUMENT_DESK

## 13. Marine-pollutant consistency

Rule ID: CON-MARINE-POLLUTANT
Policy statement: preliminary DGD and SDS Extract marine-pollutant declarations must match.
Operational response: MANUAL_REVIEW
Responsible queue: DG_DESK

## 14. Class 3 flash point required

Rule ID: CON-FLASH-POINT
Policy statement: Class 3 cargo must have a usable flash point in SDS Extract Section 9.
Operational response: REQUIRE_INFORMATION
Responsible queue: DG_DESK

## 15. Route outside snapshot scope

Rule ID: ROU-SNAPSHOT-SCOPE
Policy statement: The teaching snapshot only covers CNSHA to AEJEA on TRAIN-ME1.
Operational response: MANUAL_REVIEW
Responsible queue: ROUTE_DESK

## 16. Partner vessel operator approval

Rule ID: ROU-PARTNER-OPERATOR
Policy statement: A partner-operated vessel requires manual route approval.
Operational response: MANUAL_REVIEW
Responsible queue: ROUTE_DESK

## 17. Document submission cutoff

Rule ID: TIM-DOCUMENT-CUTOFF
Policy statement: Documents must be submitted at least five working days before ETD.
Operational response: MANUAL_REVIEW
Responsible queue: DOCUMENT_DESK

## 18. Packing Group consistency

Rule ID: CON-PACKING-GROUP
Policy statement: preliminary DGD and SDS Extract Packing Groups must match.
Operational response: MANUAL_REVIEW
Responsible queue: DG_DESK

## 19. preliminary DGD shipper declaration signature

Rule ID: DOC-DGD-SIGNATURE
Policy statement: The preliminary DGD shipper declaration must be signed.
Operational response: REQUIRE_INFORMATION
Responsible queue: DOCUMENT_DESK

## 20. Low-confidence key field

Rule ID: DOC-KEY-FIELD-LOW-CONFIDENCE
Policy statement: A key extracted field below 0.80 confidence requires confirmation.
Operational response: MANUAL_REVIEW
Responsible queue: DOCUMENT_DESK

## 21. Policy snapshot expired

Rule ID: GOV-SNAPSHOT-EXPIRED
Policy statement: A booking with ETD after snapshot expiry requires a current policy snapshot.
Operational response: MANUAL_REVIEW
Responsible queue: POLICY_OWNER

## 22. Equal-priority rule conflict

Rule ID: GOV-RULE-CONFLICT
Policy statement: Conflicting actions from equal-priority applicable rules require policy-owner review.
Operational response: MANUAL_REVIEW
Responsible queue: POLICY_OWNER

