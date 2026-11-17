Assumptions

- All names, documents, facilities and policies are synthetic training data.
- VALID-BASELINE is the complete and consistent UN1263 PAINT, Class 3, Packing Group III booking defined in TEST_CASES.md.
- These scenarios describe observable business behavior rather than individual rule implementation.
- Every result returns all matched reason codes and evidence, while final status follows PRECHECK_BLOCKED > MANUAL_REVIEW > REQUIRE_INFORMATION > PRECHECK_PASS.
- A resubmission identifies the latest document version and retains the earlier precheck result in the audit history.
- Human confirmation replaces only the confirmed extracted fact; it does not modify a policy rule.

Feature: Business acceptance of complete dangerous-goods bookings

  Scenario: BA-001 A complete baseline booking proceeds to DG Desk
    Given a booking based on VALID-BASELINE
    When the booking is submitted for precheck
    Then the result is PRECHECK_PASS
    And the next step is formal DG Desk approval
    And the result states that precheck is not a booking confirmation

  Scenario: BA-002 An accepted weight boundary proceeds without escalation
    Given a booking based on VALID-BASELINE
    And the Booking Request gross weight is exactly 2% above the preliminary DGD gross weight
    When the booking is submitted for precheck
    Then the result is PRECHECK_PASS
    And no weight-variance reason is reported

  Scenario: BA-003 An alternative dry container size proceeds
    Given a booking based on VALID-BASELINE
    And the requested equipment is one 20GP
    When the booking is submitted for precheck
    Then the result is PRECHECK_PASS
    And no equipment restriction is reported

  Scenario: BA-004 A corrected missing DGD completes the precheck
    Given an earlier precheck requested a preliminary DGD
    And the customer resubmits the booking with a complete preliminary DGD
    When the resubmission is prechecked
    Then the new result is PRECHECK_PASS
    And the earlier REQUIRE_INFORMATION result remains in the audit history
    And the evidence references the newly provided preliminary DGD

  Scenario: BA-005 A corrected weight conflict completes the precheck
    Given an earlier precheck reported a Booking and DGD weight conflict
    And the customer submits Booking Request version 2 with a matching gross weight
    When the resubmission is prechecked
    Then the new result is PRECHECK_PASS
    And the evidence references Booking Request version 2

Feature: Business acceptance of compound findings

  Scenario: BA-006 Multiple missing items are requested together
    Given a dangerous-goods Booking Request has no consignee
    And no SDS Extract is provided
    When the booking is submitted for precheck
    Then the result is REQUIRE_INFORMATION
    And reasons "DOC-CONSIGNEE-REQUIRED" and "DOC-SDS-REQUIRED" are both reported
    And one response requests both missing items

  Scenario: BA-007 A clear block is retained together with a missing declaration signature
    Given all available documents consistently declare IMDG Class "7"
    And the preliminary DGD shipper declaration is not signed
    When the booking is submitted for precheck
    Then the result is PRECHECK_BLOCKED
    And reasons "CAR-CLASS-7-BLOCK" and "DOC-DGD-SIGNATURE" are both reported
    And the result states that the block is a precheck outcome rather than final rejection

  Scenario: BA-008 Two independent manual-review issues are routed with complete evidence
    Given a booking based on VALID-BASELINE
    And the Booking Request gross weight differs from the preliminary DGD by more than 2%
    And the vessel operator is "PARTNER-TRAINING"
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reasons "CON-GROSS-WEIGHT" and "ROU-PARTNER-OPERATOR" are both reported
    And DOCUMENT_DESK and ROUTE_DESK are both identified

  Scenario: BA-009 A facility suspension is retained together with stale supporting information
    Given a booking will arrive at "AEJEA-TRAIN-T1" during the teaching suspension window
    And the SDS Extract is older than 24 months
    When the booking is submitted for precheck
    Then the result is PRECHECK_BLOCKED
    And reasons "PORT-TEMPORARY-DG-SUSPENSION" and "DOC-SDS-FRESHNESS" are both reported
    And the ETA is included in the facility-rule evidence

  Scenario: BA-010 An out-of-scope route cannot be authorized by an expired snapshot
    Given a complete booking has port of loading "CNYTN"
    And its ETD is after the active snapshot expires
    When the booking is submitted for precheck
    Then the result is MANUAL_REVIEW
    And reasons "ROU-SNAPSHOT-SCOPE" and "GOV-SNAPSHOT-EXPIRED" are both reported
    And the booking is routed to ROUTE_DESK and POLICY_OWNER

Feature: Recovery, document versions, and rule versions

  Scenario: BA-011 A human-confirmed extraction replaces a low-confidence fact
    Given an earlier precheck sent a low-confidence DGD UN Number to DOCUMENT_DESK
    And an authorized reviewer confirms the UN Number from the source document
    When the same booking is resumed with the confirmed fact and evidence
    Then the result is PRECHECK_PASS
    And the human confirmation is recorded in the audit history
    And the policy snapshot remains unchanged

  Scenario: BA-012 Replaying a booking under an authorized policy variant identifies the version used
    Given an IBC booking resulted in MANUAL_REVIEW under snapshot version 0.2
    And authorized Policy Variant "PV-001" creates snapshot version 0.3
    And the variant changes rule "CAR-IBC-MANUAL-APPROVAL" to PRECHECK_BLOCKED
    When an authorized policy owner explicitly replays the booking under the later snapshot
    Then the new result is PRECHECK_BLOCKED
    And the new result references snapshot version 0.3
    And the earlier result remains unchanged in the audit history
    And the result difference identifies rule "CAR-IBC-MANUAL-APPROVAL"
