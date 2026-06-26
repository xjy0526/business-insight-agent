from app.db.database import get_connection
from app.db.init_db import initialize_database


def test_init_db_loads_product_ad_tables(tmp_path):
    db_path = tmp_path / "business_insight.db"
    load_counts = initialize_database(db_path=db_path)

    expected_tables = [
        "local_ad_sku_candidates",
        "query_sku_recall",
        "ad_bid_experiments",
        "poi_level_ads_baseline",
    ]

    with get_connection(db_path) as connection:
        for table_name in expected_tables:
            table_exists = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
            row_count = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

            assert table_exists is not None
            assert row_count > 0
            assert load_counts[table_name] == row_count
