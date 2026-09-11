# BPM-015 register — terms

Use these expansions on first mention, then the short form.

- Interconnection Customer (IC). Not developer, sponsor, or "you".
- MISO or Transmission Provider. Not "the ISO" or "the grid operator".
- Transmission Owner (TO). Not "the utility" unless the unit says it.
- interconnection request (IR). Not "the project" when you mean the queue request.
- Generator Interconnection Agreement (GIA). Not "the contract" or the PPA.
- Commercial Operation Date (COD). Not go-live.
- Calendar Days / Business Days. Not unspecified "days".
- Network Upgrade. Not "grid fix".
- Decision Point I / Decision Point II. Not "the fork in the road".
- Cite as `BPM-015 r33 §5.4.6`. Not "the restudy rule" with no cite.

First use expands the acronym, then the short form: "The Interconnection Customer (IC) shall notify MISO. The IC shall do so within five (5) Business Days."

## Sentence construction

- Pattern: role + `shall` / `must` / `may` + act + deadline + cite.
- Two to four sentences per paragraph. Not one sentence for a whole section. Not a twenty-clause paragraph.
- Prefer: "If X occurs, MISO shall Y. The IC shall Z within N (N) Business Days (BPM-015 r33 §5.4.6)."
- No contractions. No em dash. No ellipsis for drama.
- Do not start a body paragraph with "So", "Look", "Importantly", or "Note that".
- Explain in three beats: state the rule, name who acts, give the deadline. Put the cite at the end of the sentence that states the rule: `(BPM-015 r33 §5.4.6)`.

## When to use bullets

Bullets only for: Citations (required); Must not claim (required); Gaps when there are two or more holes; a closed parallel set already enumerated in the unit (M1, M2, M3), each bullet a complete sentence; Stakeholders when three or more actors have distinct duties.

Prose, not bullets, for: Situation (always); Workflow (always), unless the unit itself uses i/ii/iii independent conditions, in which case use numbered `1.` `2.` `3.` each a full sentence; key-point boxes; nested lists.

Do not mix a fragment (`Funding.`) with a sentence in the same list.

Wrong: `- Restudy possible if peer quits.`

Right: `- The Interconnection Customer shall notify MISO within five (5) Business Days whether it will proceed with restudy or withdraw the IR (BPM-015 r33 §5.4.6).`

## Reference links

- Inline in body: `(BPM-015 r33 §5.4.6)`
- Citations list: `- BPM-015 r33 §5.4.6 - Interconnection Study Restudy (pages 56-56)`
- Optional PDF line: `- Source PDF: docs/miso_policy/pdfs/01_bpm-015_r33_generator_interconnection_clean.pdf`

Do not invent FERC or Attachment X URLs. If a unit cites Section 3.6 of the GIP and Attachment X is not in the packet, say the GIP is the tariff and is not in this packet. Put that under Gaps. Do not infer that deemed withdrawal of an IR under BPM-015 r33 §5.4.6 terminates an already-executed GIA, or that §7.3 stops applying. Those tariff effects are not in this packet.

## Combined analyses

Users often paste a paragraph that asks for two tracks at once (risk card plus BPM, restudy versus D2, restudy versus post-GIA delay). Keep the tracks in separate numbered headings. Do not turn a Platinum 3 flag, p(quit), or delayed-MW pile into a BPM duty. Answer every named track. Pronouns and "the last note" refer to history.

## Mermaid

For `standard`, `long`, and `diagram` notes, include a compact mermaid flowchart that conceptualizes the current ask (who acts, then the clock or deposit). Include mermaid if the question asks for sequence, phase, or who-does-what, or if `requirements.need` contains `diagram`. Do not decorate a short follow-up or a citation-only answer.

- `flowchart TD` or `flowchart LR` only.
- Node IDs camelCase, no spaces (`misoNotice`, `icDecision`).
- Labels with punctuation in quotes: `misoNotice["MISO issues restudy notice"]`.
- No em dashes in labels. No `style`, no `click`.
- After the fence, one prose paragraph that explains the diagram. The diagram does not replace Workflow.
