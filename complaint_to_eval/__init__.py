"""complaint-to-eval: turn user complaints into reviewable regression candidates.

Deterministic, standard-library only, zero API keys. Nothing here is an
evaluation set until a human accepts the cases.
"""

from .pipeline import analyze, load_records
from .redact import redact
from .taxonomy import find_hits, modes

__version__ = "0.1.0"
__all__ = ["__version__", "analyze", "load_records", "redact", "find_hits", "modes"]
