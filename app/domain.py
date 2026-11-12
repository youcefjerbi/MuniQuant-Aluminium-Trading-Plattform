# Copyright 2026 muniQuant. Licensed under the Apache License, Version 2.0.
"""Name normalization for matching lead text against Core plant names."""
import unicodedata

def canonical(name):
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in unicodedata.normalize('NFKC', name).casefold()).split())
