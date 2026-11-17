Assumptions

- All companies, people, facilities, policies, commodity codes and documents are synthetic training data.
- `VALID-BASELINE` is a complete Class 3 booking using `UN1263`, Packing Group III, flash point `30°C`, `100` drums, `10,000 kg` gross weight, `40HQ`, route `CNSHA/TRAIN-ME1/AEJEA`, and vessel operator `TRAINING-LINE`.
- In `VALID-BASELINE`, Booking Request, preliminary DGD and SDS Extract contain consistent cargo facts, the consignee is present, the SDS Extract is less than 24 months old, and the documents are submitted more than 5 working days before ETD.
- The active snapshot is `TRAINING-LINE-CNSHA-AEJEA-2026-08-01`, valid from `2026-08-01` through `2026-12-31`.
- Gross-weight variance is calculated as `abs(booking weight - DGD weight) / DGD weight`; exactly 2% is accepted and more than 2% requires manual review.
- Working days are Monday through Friday with no holiday calendar in version 0.2.
- `TRAINING-LINE` blocks Class 1, Class 7, Class 3 with flash point below `-18°C`, and dangerous goods in reefer equipment.
- A key extracted field with confidence below `0.80` requires manual confirmation.
- IBC packaging requires case-by-case approval from the teaching DG Desk.
- The destination facility has a synthetic dangerous-goods suspension from `2026-09-10` through `2026-09-12` inclusive.
- If no active rule produces another result, the default result is `PRECHECK_PASS`.
- Final-state precedence is `PRECHECK_BLOCKED` over `MANUAL_REVIEW` over `REQUIRE_INFORMATION` over `PRECHECK_PASS`.
- Every matched rule and reason is returned even when a higher-precedence status determines the final result.
- These 30 cases form a rule and governance test suite; their exception-heavy distribution is intentional and does not represent production booking traffic.

```gherkin
Feature: Complete and boundary-value booking precheck

  Scenario: TC-001 Complete and consistent dangerous-goods booking passes precheck
    Given a booking based on VALID-BASELINE
    When the booking is submitted for precheck
    Then the result is PRECHECK_PASS
    And the result references snapshot "TRAINING-LINE-CNSHA-AEJEA-2026-08-01"
    And no blocking, manual-review, or missing-information reason is reported

  Scenario: TC-002 Gross-weight difference at exactly two percent passes
    Given a booking based on VALID-BASELINE
    And the Booking Request gross weight is 10200 kg
    And the DGD gross weight is 10000 kg
    When the booking is submitted for precheck
    Then the result is PRECHECK_PASS
    And rule "CON-GROSS-WEIGHT" is not reported as violated

Feature: Required document and field validation

  Scenario: TC-004 Dangerous-goods declaration is missing
    Given a booking based on VALID-BASELINE
    And the DGD is not provided
    When the booking is submitted for precheck
    Then the result is REQUIRE_INFORMATION
    And reason code "DOC-DGD-REQUIRED" is reported
    And the requested information identifies the missing DGD

  Scenario: TC-005 Safety data sheet is missing
    Given a booking based on VALID-BASELINE
    And the SDS is not provided
    When the booking is submitted for precheck
    Then the result is REQUIRE_INFORMATION
    And reason code "DOC-SDS-REQUIRED" is reported
    And the requested information identifies the missing SDS

  Scenario: TC-006 DGD has no UN Number
    Given a booking based on VALID-BASELINE
    And the DGD UN Number is empty
    When the booking is submitted for precheck
    Then the result is REQUIRE_INFORMATION
    And reason code "DOC-DGD-UN-REQUIRED" is reported
    And the evidence points to the DGD UN Number field

  Scenario: TC-007 DGD has no Proper Shipping Name
    Given a booking based on VALID-BASELINE
    And the DGD Proper Shipping Name is empty
    When the booking is submitted for precheck
    Then the result is REQUIRE_INFORMATION
    And reason code "DOC-DGD-PSN-REQUIRED" is reported
    And the evidence points to the DGD Proper Shipping Name field

  Scenario: TC-008 SDS has no Section 14 transport information
    Given a booking based on VALID-BASELINE
    And the SDS Section 14 transport information is empty
    When the booking is submitted for precheck
    Then the result is REQUIRE_INFORMATION
    And reason code "DOC-SDS-S14-REQUIRED" is reported
    And the requested information identifies Section 14

  Scenario: TC-009 SDS is older than twenty-four months
    Given a booking based on VALID-BASELINE
    And the precheck submission date is 2026-08-10
    And the SDS issue date is 2024-08-09
    When the booking is submitted for precheck
    Then the result is REQUIRE_INFORMATION
    And reason code "DOC-SDS-FRESHNESS" is reported
    And an updated SDS is requested

  Scenario: TC-010 Booking Request has no consignee
    Given a booking based on VALID-BASELINE
    And no party has the role CONSIGNEE
    When the booking is submitted for precheck
    Then the result is REQUIRE_INFORMATION
    And reason code "DOC-CONSIGNEE-REQUIRED" is reported
    And the requested information identifies the missing consignee

Feature: Cross-document consistency checks

  Scenario: TC-011 Booking Request and DGD have different UN Numbers
    Given a booking based on VALID-BASELINE
    And the Booking Request UN Number is "UN1263"
    And the DGD UN Number is "UN1866"
    And the SDS Extract UN Number is "UN1866"
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reason code "CON-BOOKING-DGD-UN" is reported
    And both conflicting UN Numbers are included in the evidence

  Scenario: TC-012 DGD and SDS have different UN Numbers
    Given a booking based on VALID-BASELINE
    And the Booking Request and DGD UN Number is "UN1263"
    And the SDS Extract UN Number is "UN1866"
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reason code "CON-DGD-SDS-UN" is reported
    And both conflicting UN Numbers are included in the evidence

  Scenario: TC-013 DGD and SDS have different IMDG classes
    Given a booking based on VALID-BASELINE
    And the DGD IMDG Class is "3"
    And the SDS IMDG Class is "8"
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reason code "CON-DGD-SDS-CLASS" is reported
    And both conflicting classes are included in the evidence

  Scenario: TC-014 Gross-weight difference exceeds two percent
    Given a booking based on VALID-BASELINE
    And the Booking Request gross weight is 10201 kg
    And the DGD gross weight is 10000 kg
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reason code "CON-GROSS-WEIGHT" is reported
    And the calculated variance is greater than two percent

  Scenario: TC-015 Package counts differ between Booking Request and DGD
    Given a booking based on VALID-BASELINE
    And the Booking Request contains 100 drums
    And the DGD declares 96 drums
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reason code "CON-PACKAGE-COUNT" is reported
    And both package counts are included in the evidence

  Scenario: TC-016 Marine-pollutant declarations conflict
    Given a booking based on VALID-BASELINE
    And the DGD declares the cargo is not a marine pollutant
    And the SDS declares the cargo is a marine pollutant
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reason code "CON-MARINE-POLLUTANT" is reported
    And both declarations are included in the evidence

  Scenario: TC-017 Class 3 cargo has no usable flash point
    Given a booking based on VALID-BASELINE
    And the DGD IMDG Class is "3"
    And the SDS Extract Section 9 flash point is empty
    When the booking is submitted for precheck
    Then the result is REQUIRE_INFORMATION
    And reason code "CON-FLASH-POINT" is reported
    And a flash point value is requested

Feature: Carrier, cargo, route, and timing policy checks

  Scenario: TC-018 Class 1 cargo is blocked by the carrier snapshot
    Given a booking based on VALID-BASELINE
    And all three documents consistently declare IMDG Class "1"
    When the booking is submitted for precheck
    Then the result is PRECHECK_BLOCKED
    And reason code "CAR-CLASS-1-BLOCK" is reported
    And the carrier rule is included in the evidence

  Scenario: TC-019 Class 7 cargo is blocked by the carrier snapshot
    Given a booking based on VALID-BASELINE
    And all three documents consistently declare IMDG Class "7"
    When the booking is submitted for precheck
    Then the result is PRECHECK_BLOCKED
    And reason code "CAR-CLASS-7-BLOCK" is reported
    And the carrier rule is included in the evidence

  Scenario: TC-020 Class 3 cargo is below the allowed flash-point threshold
    Given a booking based on VALID-BASELINE
    And the SDS Extract Section 9 declares a flash point of -18.1°C
    When the booking is submitted for precheck
    Then the result is PRECHECK_BLOCKED
    And reason code "CAR-LOW-FLASH-POINT-BLOCK" is reported
    And the observed flash point and threshold are included in the evidence

  Scenario: TC-021 Dangerous goods are booked in reefer equipment
    Given a booking based on VALID-BASELINE
    And the container type is "40RF"
    And valid reefer settings are provided
    When the booking is submitted for precheck
    Then the result is PRECHECK_BLOCKED
    And reason code "CAR-REEFER-DG-BLOCK" is reported
    And the container type is included in the evidence

  Scenario: TC-022 Booking route is outside the snapshot scope
    Given a booking based on VALID-BASELINE
    And the port of loading is "CNYTN" instead of "CNSHA"
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reason code "ROU-SNAPSHOT-SCOPE" is reported
    And the result states that the snapshot cannot authorize this route

  Scenario: TC-023 Partner vessel operator requires manual approval
    Given a booking based on VALID-BASELINE
    And the vessel operator is "PARTNER-DEMO" instead of "TRAINING-LINE"
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reason code "ROU-PARTNER-OPERATOR" is reported
    And the routing queue is ROUTE_DESK

  Scenario: TC-024 Documents are submitted only four working days before ETD
    Given a booking based on VALID-BASELINE
    And the documents are submitted four working days before ETD
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reason code "TIM-DOCUMENT-CUTOFF" is reported
    And the required and actual lead times are included in the evidence

Feature: Document reliability and operational exceptions

  Scenario: TC-025 DGD and SDS have different Packing Groups
    Given a booking based on VALID-BASELINE
    And the DGD Packing Group is "III"
    And the SDS Packing Group is "II"
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reason code "CON-PACKING-GROUP" is reported
    And both Packing Groups are included in the evidence

  Scenario: TC-026 DGD shipper declaration is not signed
    Given a booking based on VALID-BASELINE
    And the DGD shipper declaration is not signed
    When the booking is submitted for precheck
    Then the result is REQUIRE_INFORMATION
    And reason code "DOC-DGD-SIGNATURE" is reported
    And a signed declaration is requested

  Scenario: TC-027 Key DGD field has low extraction confidence
    Given a booking based on VALID-BASELINE
    And the extracted DGD has confidence 0.62 for the UN Number
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reason code "DOC-KEY-FIELD-LOW-CONFIDENCE" is reported
    And the UN Number and confidence score are included in the evidence

  Scenario: TC-028 IBC packaging requires case-by-case approval
    Given a booking based on VALID-BASELINE
    And the DGD package type is "IBC"
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reason code "CAR-IBC-MANUAL-APPROVAL" is reported
    And the routing queue is DG_DESK

  Scenario: TC-029 Destination facility temporarily suspends dangerous goods
    Given a booking based on VALID-BASELINE
    And the destination facility is "AEJEA-TRAIN-T1"
    And the booking ETA is 2026-09-11
    And the facility suspension covers 2026-09-10 through 2026-09-12
    When the booking is submitted for precheck
    Then the result is PRECHECK_BLOCKED
    And reason code "PORT-TEMPORARY-DG-SUSPENSION" is reported
    And the affected facility and suspension window are included in the evidence

Feature: Policy snapshot governance

  Scenario: TC-003 Equal-priority policy actions conflict
    Given a booking based on VALID-BASELINE
    And two enabled synthetic test rules with the same priority and scope apply to the booking
    And one rule allows the cargo while the other blocks the cargo
    When the rule outcomes are aggregated
    Then the result is MANUAL_REVIEW
    And reason code "GOV-RULE-CONFLICT" is reported
    And both conflicting rule identifiers are included in the evidence

  Scenario: TC-030 ETD falls after the policy snapshot expires
    Given a complete and internally consistent booking
    And the active snapshot expires on 2026-12-31
    And the booking ETD is 2027-01-05
    And the documents meet the submission cutoff
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reason code "GOV-SNAPSHOT-EXPIRED" is reported
    And the result states that a current policy snapshot is required
```
