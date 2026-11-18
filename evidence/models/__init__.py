"""
Models of the "evidence" app.

The models are split over several modules to keep each file short. Django
only looks in this package, so every model is imported here.
"""

from .sources import Capture, Source

# The names other code may import from `evidence.models`.
__all__ = ["Capture", "Source"]
