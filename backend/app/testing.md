Here’s what I think about our milestones and result for the contract. Please let me if you have any other opinion after reviewing it closely! Also I’m flexible to talk about details.

1. Phase 1 — Foundation & Core Application: ¥20,000
2. Phase 2 — CV Analysis, Domain Integration & Consultant Finalization: ¥30,000
3. Phase 3 — Production MVP Acceptance & Handover: ¥50,000


Irudi MVP Development Milestones

1. General Scope & Architecture Requirements
The MVP should preserve the existing irudi domain logic and system boundaries. Existing beauty-analysis, recommendation, and scoring logic should not be redesigned unless explicitly approved by 株式会社Mirumi.
1.1 System Responsibilities
The production architecture should maintain the following separation:
1. Google Sheets
Master data
Rules
Approved content
Style data
Versioned survey definitions
2. Production Database
Customers
Orders and order items
Consultations
Survey responses
Customer assets
Consultant decisions
Result series
Result publications
Audit records
3. Consultant Dashboard
Internal analysis review
Consultant adjustments
Consultant finalization
4. Customer Web Application
Authentication
Order/submission flow
My Page
Consultation status
Published result access
5. Result Service
Server-side validation
Immutable result publication
Revision control
Authorization
Private asset delivery
1.2 Canonical Service Types
The platform must support the following canonical service types:

• HAIR.
• MAKEUP.
• INTEGRATED.
The exact service types included in the initial production launch will be confirmed in the MVP Scope Matrix before Phase 3 acceptance.
1.3 Security Boundaries
• Customer-facing applications must not directly expose internal Apps Script or consultant-only endpoints.
• Sensitive customer photos, raw authentication/share tokens, and other restricted customer information must not be written to:
application logs,
access logs,
traces,
or error messages.



2. Phase 1 — Foundation & Core Application
Milestone Bonus: ¥20,000
2.1 Completion Criteria
Phase 1 is complete when all of the following are demonstrated in the staging environment.
A. Authentication
1. A client can securely:
register,
log in,
log out,
and maintain a valid authenticated session.
B. Core Data Model
2. The production-oriented data model supports:
customers,
orders,
order items,
consultations,
submissions,
survey responses,
customer assets,
and the service types HAIR, MAKEUP, and INTEGRATED.
C. Order → Consultation Flow
3. A consultation is created only through the agreed order-routing workflow.
4. Each consultation is correctly linked to:
the authenticated customer,
the relevant order,
and the relevant order item.
5. A staging/test-order mechanism may be used during Phase 1 before production payment integration is available.
6. Order and consultation creation must be idempotent so that retrying the same event does not create duplicate consultations.
D. Photo & Asset Handling
7. A client can upload the required consultation photos to private storage.
8. Raw customer submissions and derived result/analysis assets are treated as separate asset classes.
9. Required customer-consent records can be stored and correctly associated with the relevant customer and consultation.
E. Survey Infrastructure
10. A versioned survey framework exists that can store:

• questionId.
• optionId.
• answer.
• survey version.
This infrastructure must work even if the final Hair or Makeup survey content is still pending.
F. Submission & Status
11. A client can submit the consultation.
12. A client can view the current consultation/analysis status.
G. Persistence & Authorization
13. Customer, order, consultation, submission, survey, and asset data persist correctly after:

• browser refresh,.
• logout,.
• and re-login..
14. One client cannot access another client’s:

• orders,.
• consultations,.
• photos,.
• survey responses,.
• or results..
15. Internal Consultant Dashboard / Apps Script endpoints are not directly exposed to customer-facing users.
H. Acceptance
16. The complete Phase 1 flow is successfully demonstrated and accepted by 株式会社Mirumi in the staging environment.



3. Phase 2 — CV Analysis, Domain Integration & Consultant Finalization
Milestone Bonus: ¥30,000
3.1 Completion Criteria
Phase 2 is complete when all of the following are demonstrated in the staging environment.
A. Consultant Access
1. A consultant can access the correct submitted consultation.
2. The consultant can access only the customer photos authorized for that consultation.
B. CV / Measurement Data
3. Existing CV/measurement-generated analysis data can be retrieved and displayed correctly.
4. The consultant can review and modify only the analysis values permitted by the existing irudi consultant workflow.
C. Provisional vs. Final Results
5. AI/provisional values and consultant-final values remain clearly distinguishable and auditable.
6. If a consultant-final value differs from the provisional value, the required override information must be preserved according to the applicable irudi contract.
D. Recommendation Integration
7. Recommendations must be generated using the 株式会社Mirumi-approved version of the existing irudi:
analysis logic,
recommendation logic,
scoring logic,
and master-data logic.
8. The Contractor must not introduce an independent recommendation model without explicit approval.
9. Any calculation designated as server-authoritative must be recalculated and validated on the server rather than trusting client/browser-calculated values.
E. Versioning & Auditability
10. The following must be stored consistently:

• recommendation selections,.
• consultant decisions,.
• relevant rule/policy versions,.
• fingerprints,.
• revisions,.
• and required audit information..
F. Consultant Finalization
11. The consultant can finalize the consultation.
12. The finalized consultation can be submitted to the publication-readiness workflow.
13. Consultant finalization must not directly bypass the server-side publication gate.
14. The finalized result can pass into the result-publication workflow without:

• identity mismatch,.
• version mismatch,.
• recommendation mismatch,.
• or asset mismatch..
G. Acceptance
15. The complete Phase 2 workflow is successfully demonstrated and accepted by 株式会社Mirumi in the staging environment.



3.2 Pending Domain Modules
The following modules are currently under 株式会社Mirumi domain QA and may not be production-ready at the beginning of Phase 2:
1. Hair Salon Request
2. Hair Styling Guide
3. Hair survey final logic/content
4. Makeup survey final logic/content
5. Makeup Overlay
6. Other domain features explicitly marked by 株式会社Mirumi as pending or deferred
Rules for Pending Modules
1. 株式会社Mirumi will provide the canonical approved contract/specification once each module is finalized.
2. The Contractor must not independently:
• redesign,
• reinterpret,
• or replace
the underlying beauty/domain logic.
3. Integration interfaces, version boundaries, and feature flags should be prepared so that finalized modules can later be connected without material architectural rework.
4. Modules that remain unapproved by the agreed freeze date may remain disabled behind feature flags.
5. Such modules will not independently block platform acceptance unless they are explicitly marked as Launch Required in the MVP Scope Matrix.
6. Before production publication, the implemented Hair and Makeup result structures must be reconciled with the applicable canonical:
result contract, and result-snapshot schema.



4. Phase 3 — Production MVP Acceptance & Handover
Milestone Bonus: ¥50,000
4.1 Production Deployment
1. The agreed MVP is deployed to a 株式会社Mirumi-controlled production environment.
2. For every service type marked Launch Required in the final MVP Scope Matrix, the complete production flow must operate successfully:
Authenticated Client
→ Paid Order / Valid Production Order
→ Service Routing
→ Required Survey & Photo Submission
→ CV / Analysis Pipeline
→ Consultant Review & Finalization
→ Publication Gate
→ Immutable Result Publication
→ Customer Notification (if enabled)
→ Authenticated Client Result Access



4.2 Order & Service Routing
3. Production orders use the agreed canonical SKU/product mapping.
4. Unpaid or unrecognized orders must not create valid production consultations.



4.3 Result Publication
5. Published customer results are stored as immutable, versioned result snapshots.
6. Changes after publication must create a new revision rather than modifying an existing published result.
7. Result ownership is verified server-side on every protected result request.
8. Possession or modification of a result URL/ID alone must never grant access.
9. Any agreed result-claim or ownership-binding mechanism must operate consistently with the production authentication/order flow.



4.4 Publication Gate
10. Before publication, the server must perform the agreed validation of:

• required result content,.
• recommendation identity/version,.
• private analysis assets,.
• customer consent,.
• and applicable asset/license requirements..



4.5 Customer Asset Security
11. Customer photos and other private customer assets must never be publicly accessible.
12. Private result assets must only be delivered through the agreed:

• authenticated access mechanism,.
• or short-lived signed access mechanism..
13. Raw uploaded customer photos must follow the agreed retention/deletion policy.
14. Raw customer uploads must not automatically become permanent immutable published-result assets.



4.6 Persistence & Feature Control
15. Consultation status and published results persist correctly across:

• refresh,.
• logout/login,.
• and supported devices..
16. Features not approved for launch remain disabled through feature flags.
17. Deferred functionality must not be presented to customers as completed production functionality.



4.7 Customer Notification
18. Customer notification must work through the notification channel included in the final MVP scope.
19. If LINE notification is included, the required 株式会社Mirumi-approved production credentials and configuration must be available.



4.8 Quality & Testing
20. No unresolved:

• Critical security defect,.
• Critical privacy defect,.
• or launch-blocking defect.
may remain in the agreed MVP flow.
21. Agreed contract/regression tests must pass, including where applicable:

• recommendation replay tests,.
• survey replay tests,.
• and production E2E tests..



4.9 Ownership & Handover
22. The following must be controlled by 株式会社Mirumi or fully transferred to 株式会社Mirumi:

• production source code,.
• Git history,.
• deployment configuration,.
• production database,.
• storage,.
• domains/configuration,.
• related production service accounts..
23. The Contractor must provide handover documentation covering:

• architecture overview,.
• setup and deployment instructions,.
• environment-variable documentation,.
• database schema/migrations,.
• API/interface overview,.
• master-data integration overview,.
• major third-party dependencies and licenses,.
• operational/rollback notes,.
• known issues,.
• remaining TODO items..
Final Acceptance
24. The production MVP must pass 株式会社Mirumi’s final acceptance review.

#### 1. What is your "existing irudi domain logic" System Inventory?
Can you provide an inventory of what already exists in irudi and what I am expected to build vs. integrate?

I also need the following items if you have them, or if I need to build it.

existing repositories
existing Google Sheets
Apps Script
existing APIs
existing CV code/models
existing database/schema
existing consultant UI/workflow
existing result examples
existing sample customer cases
existing recommendation rules
existing output JSON
existing documentation

#### 1.2 Canonical Service Types
HAIR
MAKEUP
INTEGRATED

Is the "Integrated" type just the combanation of the Hair and Makeup? A client can order just a hair only or makeup only consultation or both together "integrated" ? or what exactly is the "integrated" type?

#### For the Google Sheets data, should the production app read the Sheets directly whenever it needs the beauty rules/recommendations, or should Google Sheets be used to manage the data and then have the approved data synced into our production database? I want to make sure I understand which system should be the source of truth.

I suggest:

          ┌───────────────────┐
          │   Google Sheets   │
          │ Business editing  │
          └─────────┬─────────┘
                    │
                 approved
                    │
                    ▼
          ┌───────────────────┐
          │ Sync / Import Job │
          └─────────┬─────────┘
                    │
                    ▼
          ┌───────────────────┐
          │    PostgreSQL     │
          │ Production data   │
          └─────────┬─────────┘
                    │
                    ▼
             Your application

#### For Phase 2, am I expected to build the CV/measurement pipeline itself, or only integrate an existing CV service/output that you have made?

if I am expected to build it, I need these questions answered before we start phase 2:

What model?
What landmarks are all required?
What measurements?
What accuracy threshold?
What constitutes a successful analysis?
What happens when a photo fails?
Who defines the required measurements?
Who owns the model?
Where does inference run?
What are the supported photo orientations?
Are front + left + right face photos all required?
Is image-quality validation part of Phase 2?

#### Phase 2 - E: 
I noticed the specification mentions versioning and fingerprints for rules, policies, and master data. Does the existing irudi system already have a defined fingerprint/versioning system that I should preserve? If so, which data objects are fingerprinted, what hashing algorithm/format is currently used, and how are fingerprint mismatches handled? If this doesn't already exist, we can do a simple SHA-256-based approach for the MVP.

#### Phase 2 - 8: 
Can you provide the canonical recommendation engine specification, including inputs, outputs, scoring rules, and expected examples before Phase 2 begins?

#### Phase 3: 
Can we agree that the final MVP Scope Matrix becomes a signed/frozen acceptance baseline before Phase 3 begins, and that no feature added afterward becomes a Phase 3 acceptance requirement unless both parties agree in writing?

What is the agreed freeze date for each pending domain module?

If a pending module is delivered after the freeze date, is integration automatically deferred to post-MVP unless both parties agree otherwise?

Pending domain modules will be implemented behind
defined interfaces and feature flags where practical.

Changes that can be accommodated through the agreed
interfaces without redesigning core application
architecture are included.

Requirements introduced after the relevant specification
freeze that require substantial changes to core:

- database architecture
- API contracts
- authentication/authorization
- CV/AI processing architecture
- storage architecture
- external integrations
- or deployment infrastructure

will be reviewed as potential scope changes before
implementation.

#### Phase 3 - 2 What payment provider will we use? (You can let me know later.)

#### What customer information is the Korean consultant permitted to access, and what information must be anonymized or hidden?

Has access to:

consultation ID
photos
survey
analysis

Doesn't have access to:

name
email
phone
LINE ID
order information

#### 株式会社Mirumi to provide the approved privacy policy, consent language, data-retention policy, overseas-processing requirements, and legal guidance for the Japan/Korea data flow.

What are the required retention periods for raw photos, analysis data, and published results?

#### Need canonical consent matrix

For example:
consultation processing consent?
photo processing?
overseas consultant access?
AI processing?
marketing?
future ML training?
retention?
LINE messaging?

#### Is collecting consultant corrections for future AI/ML improvement part of the MVP scope, or should the MVP only persist them for auditability and future use?

I'd recommend:

MVP

Store structured corrections for future ML training piple.

Later

Build ML training pipeline.

That keeps the launch scope manageable for now.

#### Phase 3 - 4.4:

What is the publication gate required validation checklist?
Example:

✓ correct customer
✓ correct consultation
✓ correct order
✓ survey complete
✓ photos valid
✓ CV analysis exists
✓ recommendation version exists
✓ consultant finalized
✓ required result sections exist
✓ assets exist
✓ consent exists
✓ licenses valid

#### Phase 3 - 4.3 6: Changes after publication
Who can create a new revision?
Can a consultant revise?
Can an admin revise?
Does the customer see revision history?
Does the old version remain accessible?
Does the notification fire again?
Is a revision considered a new publication?

#### Phase 3 Makeup overlay

What exactly qualifies as acceptance for Makeup Overlay: static image assets, landmark-based SVG/canvas overlay, or photorealistic virtual try-on?

For the MVP I recommend we start with the 2D landmark-based visual overlay.

#### How should requests that are outside the agreed MVP Scope Matrix be handled?

Bug
→ included

Specified scope matrix requirement not working
→ included

New feature add
→ change request, can take more time and cost more

Changed business rule
→ change request, can take more time and cost more

New third-party integration
→ change request, can take more time and cost more


