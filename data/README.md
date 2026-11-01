# Dataset schema and provenance

`seed.jsonl` contains 64 authored synthetic examples, 32 positive and 32 legitimate, grouped into 32 families with two related variants each. `build_seed.py` deterministically reconstructs it. None is a real incident, a collected webpage, or a human-reviewed research observation. All records explicitly say `synthetic: true` and `review_status: unreviewed`.

Required fields: `id`, `text` (1–2,000 characters), `label` (`clickfix`/`legitimate`), `scenario`, `template_group`, `source`, `synthetic`. Optional `context` contains strict booleans `inside_dialog`, `has_code`, `has_copy_button`. Provenance fields include `source_type`, `source_family`, `observed_at` (only when genuine), `review_status`, and `review_notes`.

Synthetic context is deliberately illustrative, not extracted from real DOM. It correlates strongly with the authored labels; this and shared author style limit context-ablation conclusions.

For expansion, target 150–250 reviewed examples and at least 30 truly independent source/template families. Collect visible instruction passages from permitted primary reports or legitimate documentation. Retain actual source URLs and observation dates where known; label recreations separately. Never execute samples, fetch payloads, or treat an article quoting an attack as an attack page. Rights to redistribute source text must be verified separately from code licenses; use authored recreations and source references when necessary.

Only non-synthetic records with `review_status: human_reviewed` enter research use. That status requires a real reviewer; no script sets it automatically. Ambiguous/excluded examples are omitted. Review both intent and context, record the rationale, and preserve difficult legitimate cases with copy buttons, terminal references, and quoted attacks.

Related paraphrases, template families, normalized duplicates, and non-synthetic source families form connected groups. A deterministic five-fold stratified group split uses one fold for test, one for validation, and three for training. Both labels must appear in all partitions. Exact duplicate text with conflicting labels is rejected. Grouping depends on correct provenance; the tool cannot discover every semantic paraphrase by itself.

Upstream examples used while writing rules belong to regression/development data. Do not insert them into an allegedly untouched test set. The included seed supports pipeline demonstrations, not a statistically meaningful claim about real browsing.
