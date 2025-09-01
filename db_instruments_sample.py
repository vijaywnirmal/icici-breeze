from sqlalchemy import text
from src.utils.postgres import get_conn

def main() -> None:
    cols = [
        "token",
        "symbol",
        "short_name",
        "company_name",
        "isin",
        "exchange",
        "exchange_code",
        "scrip_id",
        "scrip_name",
    ]
    with get_conn() as conn:
        rows = conn.execute(text("SELECT " + ",".join(cols) + " FROM instruments ORDER BY exchange, token LIMIT 10")).fetchall()
        for r in rows:
            print(tuple(r))

if __name__ == "__main__":
    main()
