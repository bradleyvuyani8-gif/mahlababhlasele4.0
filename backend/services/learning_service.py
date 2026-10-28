from backend.database import get_connection


def recent_average_price():

    conn = get_connection()

    rows = conn.execute("""
    SELECT price
    FROM telemetry
    ORDER BY id DESC
    LIMIT 50
    """).fetchall()

    conn.close()

    if not rows:
        return 0

    values = [r["price"] for r in rows]

    return sum(values) / len(values)
