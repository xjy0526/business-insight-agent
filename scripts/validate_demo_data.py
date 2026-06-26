"""Validate synthetic demo data used by product-level ad tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.init_db import initialize_database
from app.tools.product_ad_tool import validate_product_ad_data


def main() -> int:
    """Run data validation and return process exit code."""

    initialize_database()
    result = validate_product_ad_data()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
