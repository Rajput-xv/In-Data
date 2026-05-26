"""Static lookup tables shipped with the repo.

These are deliberately *not* DB rows. They don't change per-client and
they want to live next to the code that uses them so the parser/normalizer
stays self-contained. If lookups ever become tenant-specific, this is the
file to refactor - promote to a model and load it once per request.
"""
from .loader import airport, all_airports, all_plants, plant
