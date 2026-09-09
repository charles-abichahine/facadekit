"""FacadeKit -- a text brief becomes a legalised, fabricable facade.

Pipeline:  brief -> image -> panel masks -> catalogue parts -> sheets -> files

The thesis contribution is the *legaliser* (`facadekit.legalise`), the labelled
dataset it produces as a side effect, and the three-arm comparison. Everything
else in this package exists to feed it or to write its output to disk.
"""

__version__ = "0.1.0"

from facadekit.catalogue import Catalogue, CatalogueError, Part, Sheet, load_catalogue

__all__ = ["Catalogue", "CatalogueError", "Part", "Sheet", "load_catalogue", "__version__"]
