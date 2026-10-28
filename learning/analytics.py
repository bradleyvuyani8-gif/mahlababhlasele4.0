import sqlite3

conn = sqlite3.connect(
    "data/telemetry.db"
)

rows = conn.execute("""
SELECT price
FROM telemetry
""").fetchall()

conn.close()

values = [r[0] for r in rows]

if values:

    avg = sum(values) / len(values)

    print(
        f"Average Observed Price: {avg}"
    )
else:
    print("No data")
