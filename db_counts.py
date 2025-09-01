from sqlalchemy import text
from src.utils.postgres import get_conn

def main() -> None:
    with get_conn() as conn:
        if conn is None:
            print("no db connection")
            return
        for t in ["instruments", "nifty50_list", "market_holidays"]:
            cnt = int(conn.execute(text(f"SELECT COUNT(*) FROM {t}")).fetchone()[0])
            print(f"{t} {cnt}")

if __name__ == "__main__":
    main()
