from backend.database import get_connection


def store_snapshot(snapshot):

    conn = get_connection()

    conn.execute(
        """
        INSERT INTO telemetry(pair,price,volume)
        VALUES(?,?,?)
        """,
        (
            snapshot["symbol"],
            snapshot["last"],
            snapshot["volume"]
        )
    )

    conn.commit()
    conn.close()
