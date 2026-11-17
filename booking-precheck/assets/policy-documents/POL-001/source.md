# Dangerous Goods Acceptance Guide

Document ID: POL-001
Fixed-route teaching policy - version 1.0

Synthetic training policy only. Not a real carrier, port, or regulatory requirement.

## Applicability

- Carrier: TRAINING-LINE
- Route: CNSHA to AEJEA
- Service: TRAIN-ME1
- Effective: 2026-08-01 through 2026-12-31

## 1. Class 1 not accepted

Rule ID: CAR-CLASS-1-BLOCK
Policy statement: TRAINING-LINE does not accept IMDG Class 1 on the teaching route.
Operational response: PRECHECK_BLOCKED
Responsible queue: NOT APPLICABLE

## 2. Class 7 not accepted

Rule ID: CAR-CLASS-7-BLOCK
Policy statement: TRAINING-LINE does not accept IMDG Class 7 on the teaching route.
Operational response: PRECHECK_BLOCKED
Responsible queue: NOT APPLICABLE

## 3. Low flash-point Class 3 not accepted

Rule ID: CAR-LOW-FLASH-POINT-BLOCK
Policy statement: TRAINING-LINE does not accept Class 3 cargo below -18°C flash point.
Operational response: PRECHECK_BLOCKED
Responsible queue: NOT APPLICABLE

## 4. Dangerous goods in reefer not accepted

Rule ID: CAR-REEFER-DG-BLOCK
Policy statement: TRAINING-LINE does not accept dangerous goods in reefer equipment on the teaching route.
Operational response: PRECHECK_BLOCKED
Responsible queue: NOT APPLICABLE

## 5. IBC packaging manual approval

Rule ID: CAR-IBC-MANUAL-APPROVAL
Policy statement: IBC packaging requires case-by-case approval from the teaching DG Desk.
Operational response: MANUAL_REVIEW
Responsible queue: DG_DESK

