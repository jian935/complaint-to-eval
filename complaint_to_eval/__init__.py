"""complaint-to-eval: evidence-backed defect triage for issue-tracker text.

Deterministic, standard-library only, zero API keys. Output is a set of
UNREVIEWED candidate labels with the quote each one came from -- the raw
material for a regression suite, not the suite itself. Nothing here is an
evaluation set until a human accepts the cases.
"""

from .pipeline import analyze, load_records
from .redact import redact
from .taxonomy import find_hits, modes

__version__ = "0.2.0"
__all__ = ["__version__", "analyze", "load_records", "redact", "find_hits", "modes"]
