# MuniQuant narrated platform walkthrough

Actual platform screenshots with an animated cursor and computer-generated English narration. Recorded in an isolated local training database. All demonstrated industrial facts are fictional. This is an edited instructional walkthrough, not a continuous real-time recording.

The source registration, pasted capture, facility creation, identity evidence, capacity extraction, review rejection, parser replay and JSON export were performed successfully. The real-source access and URL retrieval forms are instructional previews; those forms were not submitted. Existing pilot data was unchanged.

## 00:00:00 — Start here

Welcome to MuniQuant. This walkthrough uses a separate training workspace with fictional industrial data. Follow the animated cursor and pause whenever you need to enter a form. The platform preserves industrial evidence, facility identities and review decisions.

## 00:00:20 — 1 · Enable editing

First, click Workspace access. Enter the write token configured for your own server, then click Enable editing. The masked token shown here belongs only to this disposable local training workspace. Reloading the page clears the token.

## 00:00:37 — 2 · Register the publisher

Open Sources and evidence, then click Register source. Register the publisher before capturing a document. For practice we will create a clearly labelled synthetic source; real work should use the actual publisher and its source URL.

## 00:00:56 — 3 · Keep training data labelled

Enter the source name, publisher and URL. Select Synthetic as the source type and Synthetic fixture as its access status for this exercise. Add a note explaining that the content is fictional. Click Save record.

## 00:01:12 — 4 · Preserve the evidence

Click Paste evidence. Select the training source, enter the document title, original URL and known publication date. Choose text slash HTML and paste this fictional fact sheet. It reports annual capacity of one hundred twenty five kilotonnes, effective January first, twenty twenty five. Save record preserves the exact pasted bytes and their fingerprint.

## 00:01:40 — 5 · Inspect the snapshot

Open the document title to check its publisher, publication date, retrieval time, original URL and SHA two fifty six fingerprint. Download exact snapshot gives you the preserved source bytes. Inspect the source before interpreting any numbers.

## 00:01:59 — 6 · Create a facility identity

Open Industrial assets and click Add asset. Enter Training Smelter as the canonical name, choose Facility, Smelter, Norway and Aluminium. Enter a region and only verified aliases. We leave aliases empty for now. Save the identity once; avoid duplicate records for the same physical facility.

## 00:02:22 — 7 · Prove the identity

Open the facility and click Record identity evidence. Select the fact sheet, give an exact locator such as the heading and first paragraph, and explain how it supports the name, geography and facility class. Click Save record. Identity evidence is separate from a capacity observation.

## 00:02:44 — 8 · Extract a literal value

Back in Sources and evidence, click Extract value beside the fact sheet. Enter Training Smelter and country code N O. Choose Capacity and kilotonnes per year. Use the source supported effective date, January first, twenty twenty five. Enter annual capacity of before the number and kilotonnes after it. Save record runs the extraction; it does not invent a fact.

## 00:03:11 — 9 · Check units and history

Open Training Smelter again. The observation history now shows the reported value of one hundred twenty five kilotonnes per year, normalized to one hundred twenty five thousand tonnes per year, with its effective date. This exact name matched the registered identity automatically. Check the unit and source before proceeding.

## 00:03:35 — 10 · Review uncertain names

Open Resolution and review. Exact names and verified aliases can resolve deterministically. Similar names are only suggestions. This training workspace includes an unresolved Bay aluminium entry. Click Review candidates and compare the suggested identity with the underlying evidence before making a decision.

## 00:04:00 — 11 · Record a defensible decision

Here the available evidence cannot distinguish the candidates, so keep Reject, no suitable match. Enter the reason and click Save record. If evidence supports a candidate, select that identity instead. Decisions are final and attributed to the configured curator. A standalone name review records a decision; accepting an extracted candidate also creates its observation and audited alias.

## 00:04:29 — 12 · Read quality findings

Open Data quality before exporting. Read each finding and its remediation. Our new facility has identity evidence, but the seeded example company still lacks its own locator, producing a warning. Warnings remain visible in the package. Blocking findings prevent export and must be resolved.

## 00:04:52 — 13 · Verify reproducibility

Click Verify frozen replay beside the extraction build. The server reruns the versioned parser against the preserved snapshot and checks equivalent candidates. The confirmation here reports one equivalent candidate. This verifies extraction reproducibility; it does not independently certify that the industrial claim is true.

## 00:05:16 — 14 · Export the evidence package

Click Export version one package. A successful validation downloads commodity evidence package dot JSON. The package carries the source references, fingerprints, dates, exact numeric values and quality findings. Use Download contract schema if another application needs the formal data structure. This training export contains fictional data.

## 00:05:42 — 15 · For real public sources

For real evidence, register the actual publisher and leave access as Review required until you have checked permitted use. Click Review access, enter the approved exact hostnames, access basis and retention policy, then select the justified decision. This form is shown for instruction only; we are not granting a real publisher permission in this training exercise.

## 00:06:09 — 16 · Retrieve approved URLs

After a real source has a permitted policy, click Retrieve URL. Choose that source, paste the exact document URL and title, and enter a publication date only when known. Save record retrieves and preserves the bytes. Our synthetic source is deliberately absent from this permitted source list, so we do not submit this form.

## 00:06:32 — Your repeatable workflow

Your routine is: register the source, preserve the document, register the facility, link identity evidence, extract the value, review uncertain matches, check quality, verify replay and export. Pause this video to copy the demonstrated training entries. For real work, use source supported dates and facts. The accompanying transcript includes the exact practice values.

## Exact practice values

- Source: Walkthrough training source; publisher: MuniQuant training fixture; type: synthetic; access: synthetic; URL: https://example.org/muniquant-training.
- Document: Fictional Training Smelter fact sheet; URL: https://example.org/muniquant-training/fact-sheet; publication date: 2025-01-01; media type: text/html.
- Facility: Training Smelter; kind: facility; type: smelter; country: NO; region: Norway — fictional training site; commodity: aluminium; aliases: empty.
- Identity locator: HTML heading and first paragraph.
- Extraction: raw facility name Training Smelter; country NO; capacity; kt/year; effective date 2025-01-01; prefix annual capacity of; suffix kilotonnes. Expected result: 125 kt/year → 125000 t/year.

```html
<h1>Training Smelter</h1><p>Fictional training facility in Norway; aluminium smelter.</p><p>Effective 2025-01-01: annual capacity of 125 kilotonnes.</p>
```

Export completed with WARN because the seeded example company lacks an explicit identity evidence locator. The warning was not hidden or described as a clean PASS.

The video highlights a next action with an animated pointer and click ring over captured screens. Form typing and network waits have been edited out. External source permission and URL retrieval are explained without pretending they were executed.

Voice replacement: locally generated natural AI narration using [Kokoro ONNX](https://github.com/thewh1teagle/kokoro-onnx), af_heart voice at speed 0.92, with sentence pauses and normalized volume. This is a human-sounding synthesized voice, not a human recording.
