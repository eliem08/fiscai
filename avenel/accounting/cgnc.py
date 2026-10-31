"""Standard Moroccan CGNC (Code Général de Normalisation Comptable (CNC, 1989), referenced by Loi 9-88) Chart of Accounts Seed.

All account codes, classes (0 to 8), and labels are loaded dynamically from /jurisdiction/ma/cgnc_seed.yaml.
No accounting account seeds or legal codes are hardcoded in application code (Rule A.1 & Rule A.2).
"""

from __future__ import annotations

from avenel.jurisdiction.loader import get_cgnc_seed_accounts


def get_standard_cgnc_accounts() -> list[dict[str, str]]:
    """Returns standard Moroccan CGNC chart accounts loaded from jurisdiction pack."""
    return get_cgnc_seed_accounts()
