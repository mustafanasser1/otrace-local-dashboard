# OTrace-FL — First PhD Presentation (UCM) Visual Direction

Design consultation only. No project files change.

## Concept: "Evidence, not slides"

The deck is framed as a single argument built in four acts: **Problem -> Mechanism -> Evidence -> Validation & Road**. Visual register: high-end technical keynote (dark instrument panels for system/evidence moments) alternating with editorial white pages (for argument and framing). UCM identity appears as a thin red spine and a small logo lockup, never as a template frame.

**Act rhythm (light/dark alternation):** 1-5 light, 6-12 dark technical, 13-17 light editorial with dark insets, 18-22 mixed, 23 dark close.

---

## 5 Design Rules

1. **Typography** — Two families only. Headline: a geometric/grotesk display (e.g. Söhne, Inter Tight, or Neue Haas) at 88-104px, tight tracking (-0.04em), max 6 words. Body 32px, captions 24px, monospace (JetBrains Mono / IBM Plex Mono) reserved *exclusively* for identifiers, event names, field keys and numbers. Never more than 3 type sizes on one slide.
2. **Whitespace** — Every slide reserves a 120px outer margin and keeps at least 35% of the canvas empty. One idea per slide; if a slide needs a second heading, it is two slides. No slide carries more than 4 discrete objects (a diagram counts as one).
3. **Screenshot treatment** — Never a raw full-window capture. Crop to the meaningful region, place on a neutral plinth with a 1px hairline border and a soft long shadow, and add one red callout (thin leader line + 20px label) pointing at the single thing the audience must see. Dark-UI captures sit on dark slides, light captures on light slides — never inverted.
4. **Diagrams** — Built from the same primitives across the whole deck: rounded rectangles, hairline connectors, one accent per role (blue = FL, amber = OTrace, green = verified/evidence). Data flows left-to-right, control/audit flows downward. No clip art, no isometric 3D, no gradient meshes, no drop-shadowed arrows.
5. **Use of red** — UCM red is a scalpel, not a palette: the 4px vertical spine on section dividers, one callout per screenshot, the underline on the active step of the running lifecycle strip, and the logo. Never as a fill for cards, never for body text, never two red elements competing on one slide.

**Logo placement:** UCM logo bottom-left at 32px height on the title slide and section dividers only; elsewhere replaced by a 4px red spine plus small slide number. No footer band, no repeated crest.

**Recurring device:** a persistent 5-node "lifecycle strip" (Partition -> Local Training -> Update Submission -> Aggregation -> Deployment) appears as a 40px-tall header on every technical slide, with the currently discussed node in red. The audience always knows where they are in the pipeline.

---

## Slide-by-slide (23 slides)

**1. Title — GDPR Evidence in Distributed AI**
Message: This thesis asks how GDPR compliance can be modelled and validated in distributed AI systems.
Visual: Full-bleed white, headline left-aligned at optical third, thesis title in Spanish set small in monospace below, UCM logo bottom-left, one red hairline spine on the left edge. No imagery.
Content: Thesis title, research question, author, supervisor, UCM, date.

**2. The Question**
Message: Compliance is asserted in documents but not observable in running distributed systems.
Visual: Single sentence at 104px on white, one supporting line. Nothing else.
Content: The research question verbatim from the project.

**3. Why Federated Learning Makes This Hard**
Message: Federated learning removes the central dataset — and with it the usual audit vantage point.
Visual: Two-panel contrast diagram: centralised (one box, one log) vs federated (three client enclaves, no shared log). Deliberately asymmetric.
Content: FL premise; raw data stays local; the audit gap this creates.

**4. Scope Honesty**
Message: OTrace is one initial experimental strand of the thesis, not the whole thesis.
Visual: Editorial white slide, the framing paragraph set as a pull-quote at 52px with a red opening bracket.
Content: The project's framing statement; explicit non-claim of full GDPR compliance.

**5. Contribution in One Sentence**
Message: FL lifecycle events are enriched with GDPR context and recorded as OTrace attestations, producing an auditable trace.
Visual: The hero four-stage flow, first appearance, large: FL Event -> GDPR Context -> OTrace Attestation -> GDPR Evidence, with field lists beneath each stage.
Content: The stage field lists already defined on the GDPR page.

**6. Section: The System** (divider)
Visual: Dark slide, red spine, act number 01 in monospace, UCM logo.

**7. Data — eICU Partitioned by Hospital**
Message: 186 hospitals are partitioned into three disjoint client groups over real ICU stays.
Visual: Hero partition diagram — 186 small hospital marks clustering into 3 enclaves of 62; stays/features as monospace stats in the margin, not as cards.
Content: 1,627 stays, 74 features, 186 hospitals, 62 per client, sepsis prediction binary task.

**8. Federated Training Loop**
Message: Each round runs three local epochs, then FedAvg aggregates masked updates.
Visual: Circular round diagram with the four lifecycle event types marked where they occur; lifecycle strip active on Local Training.
Content: 3 clients, 10 rounds, 3 local epochs, FedAvg, simple neural network.

**9. Secure Aggregation**
Message: The server sees only the sum of masked updates, never an individual client's contribution.
Visual: Three masked-update lanes converging into one; masks cancelling shown as paired +m / -m glyphs.
Content: Secure aggregation enabled by configuration; mechanism-level protection sits in the FL layer, not in OTrace.

**10. Differential Privacy on Released Metrics**
Message: Metrics leaving the system carry calibrated noise.
Visual: Split panel — clean value vs released value, epsilon set large in monospace.
Content: DP on released metrics enabled; epsilon 5.0; state clearly that DP applies to released metrics, not to training.

**11. Section: The Evidence Layer** (divider)

**12. What OTrace Records**
Message: One real attestation shows exactly what is captured at each lifecycle step.
Visual: The single strongest slide — one real attestation from the live trace, split into FL Information (event type, actor, round, timestamp) and GDPR Context (purpose, legal basis, consent reference, GDPR role, retention), on a dark plinth with a red callout on the trace ID.
Content: A real captured attestation from the running backend; no fabricated fields.

**13. GDPR Context as a First-Class Field**
Message: GDPR context is attached at event time, not reconstructed afterwards.
Visual: Field-anatomy diagram: one event object exploded into its GDPR keys, each key annotated with the question it answers.
Content: Purpose, legal basis, consent reference, GDPR role, retention.

**14. Trace Completeness**
Message: In the recorded run, every expected lifecycle event produced an attestation.
Visual: Single large ring (71/71) with the event breakdown as a thin stacked bar beneath. No card grid.
Content: 30 local training + 30 update submission + 10 aggregation + 1 deployment = 71 expected and recorded; 100% completeness for that run. State that this is one recorded run, not a cumulative store count.

**15. Cost of Traceability**
Message: Full lifecycle attestation added roughly eight percent runtime.
Visual: Two horizontal bars, before/after, difference annotated in red; per-attestation cost in the margin.
Content: 5.73s without tracing, 6.19s with, +0.46s / +8.0%, ~6.5 ms per attestation.

**16. Live Prototype** (screenshot slide)
Message: This is not a mock-up — the dashboard reads the running FastAPI/OTrace backend.
Visual: Cropped dashboard capture on a plinth, one red callout on the live-backend indicator.
Content: Real screenshot; note the trace store is queried live via the trace search endpoint.

**17. GDPR Areas Supported**
Message: The trace supports four areas — it does not certify compliance in any of them.
Visual: Four quadrants, equal weight, one line each, hairline dividers instead of cards.
Content: Accountability & traceability, lawful processing & consent, data protection (raw data local + secure aggregation), evidence for evaluation.

**18. Articles Relevant to the Prototype**
Message: Six articles map onto concrete implemented mechanisms.
Visual: Compact two-column list, article number in monospace red, one factual sentence each. No badges, no status colours.
Content: Art. 5, 6, 7, 25, 30, 32 with the factual one-liners already written for the prototype.

**19. Example: Consent Reference in the Trace**
Message: Consent appears as a referenced field inside attestations, linking processing back to a recorded consent state.
Visual: One attestation excerpt with the consent reference highlighted, connected by a hairline to the consent record it resolves to.
Content: Real consent reference behaviour; keep secondary and short; no patient narrative.

**20. Section: Validation** (divider)

**21. Metamorphic Relations Defined**
Message: Six metamorphic relations are defined as the planned validation strategy for the trace and aggregate.
Visual: Six compact rows, relation ID in monospace, one line each; a clear "Defined — not yet executed" status line at the top.
Content: MR1-MR6 as written in the project. Explicitly no pass/fail claims.

**22. Architecture & Codebase**
Message: The prototype is a real, inspectable system, not a notebook.
Visual: Layered architecture diagram — FL layer, OTrace service, FastAPI + SQLite, dashboard — with the key modules named in monospace under each layer.
Content: Partitioning, local training, federated training, secure aggregation, DP metrics, event logger, consent manager, OTrace service and routers, tests, dashboard.

**23. What Comes Next**
Message: Execute the defined validation, broaden the GDPR modelling, and generalise beyond one dataset.
Visual: Three-lane horizontal roadmap, no dates unless Mustafa supplies them; closing red spine and UCM logo.
Content: Run the defined metamorphic relations; extend article coverage; assess scalability and other domains.

---

## Cuts if time runs short
Drop 10 (DP), 19 (consent reference) and 13 (field anatomy) first — they compress into 12 and 17 without losing the argument. That yields 20 slides.

## Notes on integrity
Every number above comes from the recorded run already in the project. Nothing new is asserted. The deck never says "compliant", "certified", or "tests passed"; metamorphic relations are labelled **Defined**, and completeness/overhead figures are attributed to the single recorded run rather than to the cumulative trace store.