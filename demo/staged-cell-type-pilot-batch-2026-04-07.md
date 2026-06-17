# Staged Cell-Type Pilot Batch 2026-04-07

Purpose: pick a small low-ambiguity batch of staged cell types to exercise the full editorial workflow:

1. review
2. validate
3. promote into curated `record.json`
4. publish to the registry
5. verify downstream reuse

This is a process-learning batch, not an attempt to clear the staging backlog.

## Recommended Pilot Batch

### 1. A123 APR18650M1A

- staging file:
  - `records/_staging/cell-type/a123--apr18650m1a--2009.json`
- suggested curated id:
  - `a123--apr18650m1a--2009`
- why this is a good pilot:
  - datasheet-backed
  - identity is clear
  - year-based id is already stable
  - BattINFO strict staging validation passes
  - simple cylindrical commercial cell with a small, easy-to-review spec set
- expected review focus:
  - confirm whether the sparse spec set is sufficient for initial curation
  - decide whether additional provenance fields should be added beyond the current datasheet file hash and retrieval timestamp

### 2. Panasonic NCR18650PF

- staging file:
  - `records/_staging/cell-type/panasonic--ncr18650pf--2016.json`
- suggested curated id:
  - `panasonic--ncr18650pf--2016`
- why this is a good pilot:
  - datasheet-backed
  - identity is clear
  - year-based id is already stable
  - BattINFO strict staging validation passes
  - well-known cylindrical commercial cell, likely useful as a reusable reference point
- expected review focus:
  - the record currently validates but keeps `chemistry = unknown`
  - decide whether that should remain unknown for now or be editorially normalized before promotion

### 3. CALB L173F125A

- staging file:
  - `records/_staging/cell-type/calb--l173f125a--2020.json`
- suggested curated id:
  - `calb--l173f125a--2020`
- why this is a good pilot:
  - datasheet-backed
  - identity is clear
  - year-based id is already stable
  - BattINFO strict staging validation passes
  - adds a prismatic LFP example so the pilot is not only small cylindrical cells
- expected review focus:
  - sanity-check the voltage and charging fields for this larger-format cell
  - decide whether size or dimensional metadata should be added before promotion if easily supported by the datasheet

## Optional Stretch Candidate

### Samsung INR21700-50E

- staging file:
  - `records/_staging/cell-type/samsung--inr21700-50e--2017.json`
- suggested curated id:
  - `samsung--inr21700-50e--2017`
- why it is useful:
  - good high-visibility 21700 cylindrical example
  - strict validation passes
  - includes richer specs than the main three
- why it is not in the first three:
  - the record already contains notes saying datasheet supplementation found conflicting values but the existing values were kept
  - that makes it a good second-wave review candidate, not the cleanest first process rehearsal

## Records To Defer For This First Pass

These are valid enough to inspect later, but they are not ideal for the first process-learning batch.

### `records/_staging/cell-type/amprius-wuxi-lead--e485795ch.json`

- `width.unit` is currently `m.`
- this should be triaged as a content cleanup case before using it as a pilot promotion example

### `records/_staging/cell-type/a123--20ah.json`

- the model identity is weak compared with more standard commercial model names
- better to postpone until the team is comfortable deciding how to represent these larger-format A123 variants

### `records/_staging/cell-type/bmz-terrae--inr-21700-50-e.json`

- plausible and likely workable, but it comes from catalog-style import rather than the cleaner datasheet-intake path used by the main pilot set
- better as a follow-up once the first promotion/publication pass is familiar again

### `records/_staging/cell-type/lithiumwerks--ifpr26650-p--2025.json`

- strict validation passes, but the current `diameter` value appears numerically suspect
- keep it out of the first pilot batch until dimensional extraction is checked

### `records/_staging/cell-type/bak--n18650ck--2017.json`

- strict validation passes, but the current `diameter` value appears numerically suspect
- same reason to defer as above

## Proposed Execution Order

Use this order:

1. `a123--apr18650m1a--2009.json`
2. `panasonic--ncr18650pf--2016.json`
3. `calb--l173f125a--2020.json`

Reason:

- first record is simple and clean
- second adds another clear cylindrical commercial example
- third adds a different form factor and higher-capacity profile

## Minimal Workflow For Each Record

### 1. Review the staging JSON

Check:

- id basis
- provenance completeness
- obvious unit or plausibility issues
- whether notes explain editorial judgment

### 2. Validate with BattINFO

```powershell
.\..\BattINFO\.venv\Scripts\battinfo.exe editorial validate-staging-cell-type `
  --input <staging-json> `
  --validation-policy strict `
  --format json
```

### 3. Promote into curated

```powershell
.\scripts\promote-staging-cell-type.ps1 -Input <staging-json>
```

### 4. Review the curated output

Check:

- `records/cell-type/<record-id>/record.json`
- `product.id`
- `short_id`
- normalized field names and units

### 5. Publish to registry

```powershell
.\scripts\publish-curated-cell-type.ps1 `
  -Input <record-id> `
  -ProjectId <project-id> `
  -PublisherId <publisher-id> `
  -SourceVersion <source-version> `
  -RegistryUrl <registry-url> `
  -ApiKey <api-key>
```

### 6. Verify reuse

Check:

- registry resource response
- registry page-model response
- Battery Genome route if available in the local environment

## Success Criteria For The Pilot Batch

This pilot is successful if all three recommended records:

- are understandable and reviewable as staged drafts
- can be promoted without identifier surprises
- produce acceptable curated `record.json` outputs
- can be published without manual registry surgery
- can be resolved downstream by canonical id

## Follow-Up After The Pilot

If the pilot succeeds, the next useful wave is:

1. `samsung--inr21700-50e--2017.json`
2. one cleaned-up coin-cell example
3. one cleaned-up imported catalog record such as `bmz-terrae--inr-21700-50-e.json`

