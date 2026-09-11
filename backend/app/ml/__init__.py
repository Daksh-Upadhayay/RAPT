"""Trained classifiers and text embeddings.

Import xgboost before anything pulls in torch (sentence-transformers). Both ship their own
OpenMP runtime on macOS; when torch's loads first, unpickling an XGBoost model segfaults
the process (e.g. a knowledge-base entry is embedded, then the first ticket is triaged).
Every module under app.ml imports this package first, so this runs before torch.
"""

import xgboost  # noqa: F401
