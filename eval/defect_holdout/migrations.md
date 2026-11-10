# Label migrations

Label files change only for a stated reason, and every change is listed here so the
history stays auditable. Adding a mode silently re-scoring an old set is exactly the
kind of thing this repo is supposed to be transparent about.

## Round 6 — the `logic_or_validation` mode (2026-11-10)

**Why.** Exit-code bugs, type coercion, accepted-invalid-input, duplicate execution
and malformed constructed output had no home, so they were being labelled
`config_or_env` or `data_integrity`. That distorted both modes: `data_integrity`
read "wrong value computed" instead of "data destroyed", and `config_or_env` read
"logic bug" instead of "setting ignored". A tenth mode was added and the boundary
cases moved into it.

**Consequence to be honest about.** Because these sets were in view when the labels
changed, C/D/E are contaminated after this round; re-scoring them gives 0.824 /
0.829 / 0.743, which must **not** be quoted as improvement. Set **F** is the only
clean post-change measurement.

**Effect measured on F:** 0 of 5 logic cases caught. The mode is conceptually right
and, so far, operationally useless.

### Records moved (18)

| Set | Record | Was | Now | Why |
| --- | --- | --- | --- | --- |
| A | `aider-5898` | `data_integrity` | `logic_or_validation` | benchmark leaves tests silently unexecuted — silent false state, not lost data |
| A | `dify-45799` | `data_integrity` | `logic_or_validation` | valid archive rejected — input validation, not corruption |
| B | `aider-5879` | `data_integrity` | `logic_or_validation` | failed write reported as success — silent false state |
| C | `aider-5872` | `config_or_env` | `logic_or_validation` | unreadable `--message-file` still exits 0 — wrong exit status |
| C | `dify-45817` | `data_integrity` | `logic_or_validation` | integer variables compared as text — coercion |
| C | `dify-45929` | `data_integrity` | `logic_or_validation` | schedule trigger runs twice on DST fall-back — duplicate execution |
| D | `aider-5871` | `config_or_env` | `logic_or_validation` | `__main__` drops `main()`'s return value so failures exit 0 |
| D | `dify-45705` | `data_integrity` | `logic_or_validation` | authorization URL built with a double `?` — malformed construction |
| D | `dify-45442` | `data_integrity` | `logic_or_validation` | redo skips the empty-graph snapshot — wrong control flow |
| D | `dify-45611` | `data_integrity` | `logic_or_validation` | `/v1` appended after the query string instead of the path |
| D | `dify-45625` | `data_integrity` | `logic_or_validation` | required Number parameter accepts `true`/`false` — missing validation |
| D | `dify-45443` | `data_integrity` | `logic_or_validation` | `setInputs` cannot remove keys — shallow merge keeps deleted fields |
| D | `dify-45441` | `data_integrity` | `logic_or_validation` | Result panel double-encodes outputs as a JSON string |
| E | `aider-5874` | `config_or_env` | `logic_or_validation` | `/undo` discards the return value; the model is never told |
| E | `aider-5875` | `data_integrity` | `logic_or_validation` | patch `Add File` rejects a valid file and leaves an empty one |
| E | `dify-45557` | `data_integrity` | `logic_or_validation` | reasoning and `ENDTHINKFLAG` leak into the answer text |
| E | `dify-45724` | `data_integrity` | `logic_or_validation` | NULL `retrieval_model` silently returns an empty result |
| E | `dify-45444` | `data_integrity` | `logic_or_validation` | DETAIL tab double-encodes workflow outputs |

Each row's `note` in the label file records `(round 6: was <old modes>)`.

### Deliberately not moved

`dify-45881` and `dify-45789` are uuidv7 value-overflow bugs currently labelled
`data_integrity`. Their surface phrasing is genuine truncation, and a phrase list
cannot distinguish "stored data truncated" from "computed value truncated" without
context. Keeping them in `data_integrity` is the honest choice; the overlap is a
known limitation, not an oversight.

### Signals moved at the same time

`rejects a valid` and `unexecuted` moved from `data_integrity` to
`logic_or_validation`; `silently wraps` stayed in `data_integrity` for the reason
above. The rule set and the labels must always agree — a label migration without a
matching signal migration would manufacture false positives.

## Earlier changes

- Rounds 4 and 5 changed **signals only**; no label file was edited, so C/D/E stayed
  valid for their rounds and were only invalidated by the round-6 migration above.
- Round 2 changed signals only as well.
