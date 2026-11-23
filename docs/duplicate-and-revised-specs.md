# Duplicate and Revised Cell Specs

Adopted 2026-11-23.

A cell-spec record describes one manufacturer specification document at one revision. It does not describe a trade name. Manufacturers do revise datasheets under an unchanged model name. The 2016 LG INR18650-MJ1 product specification lowers the minimum capacity of the 2014 one from 3,400 to 3,350 mAh, and Samsung's 2019 INR21700-50E specification, marked "Version 2", raises the nominal voltage from 3.6 to 3.63 V. Two records for one model name can therefore both be right, or one can be a copy of the other. This page says how to tell them apart and what to do in each case.

## What a Record States About Its Source

Every curated cell spec names the document it was taken from. The manufacturer's document number goes in `identifier` as a PropertyValue with `property_id` set to `manufacturer_document_number`, the revision label in `datasheet_revision` and the issue year in `year`. A record taken from a catalogue or a paper says so in `provenance.source_type` and cites that source; it does not borrow a datasheet revision it has not seen.

## Copies

Two records are copies when they describe the same document, or when neither names a document and their values agree once obvious errors are set aside. Copies are deprecated.

1. Keep the record that is most complete and most correct. Prefer a primary datasheet source over a catalogue, and a reviewed record over an auto-promoted one.
2. Move any correct fact that only the other record holds into the kept record, as a new version.
3. Mark the other record superseded in the registry, with `replaced_by_iri` pointing at the kept record (admin status endpoint, `scripts/supersede-cell-specs.py`). Its IRI keeps resolving as a tombstone and is never reused.
4. Remove its folder from `records/cell-spec/` in the same change and name the replacement in the commit message. Git history keeps the old record.
5. Records that link to the superseded spec (a dataset's `about`, a cell's spec reference) are re-pointed when they are next published.

## Revisions

Two records for one model name are revisions when they cite different documents or revisions and at least one declared value differs beyond rounding: capacity, voltage limits, mass, dimensions, current limits, impedance, or a cycle-life claim made under the same test conditions. Both stay.

Each revision states its document and revision as above, and its record id carries a disambiguator as described in `versioning-and-revisions.md`. Until the cell-spec schema has a successor field, each record's `notes` name the other revision and which one came first. A cell or dataset links the revision that matches its purchase or test date. When that date is unknown, it links the latest revision and says so in its notes.

## Other Cases

A new model name or suffix is a different product with its own record, even when the manufacturer presents it as an update (APR18650M1 and APR18650M1A, LF280N and LF280K, INR21700-M50 and INR21700-M50T).

A cell sold under an integrator's or reseller's label keeps its own record unless a document shows it is the same cell as another record.

Values that are wrong because extraction failed, such as a diameter of 0.3 mm or a mass of 1 g, are errors to correct. They are never evidence of a revision. Cycle-life claims are compared only when their test conditions match.

## Before a New Spec Is Staged

Search the registry and this repo for the same manufacturer and model name, ignoring spaces, hyphens and case. Either reuse the existing record, or state the new document revision and explain in the review metadata why the new record is not a copy.
