#!/usr/bin/env python3
"""Seed mock CSI 300 data for testing when AkShare is unavailable."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

def main():
    db_path = Path(__file__).parent / "data" / "index_cache.db"
    
    # Generate 90 days of mock CSI 300 data
    start_date = datetime(2025, 11, 3)
    data = []
    
    for i in range(90):
        date = start_date + timedelta(days=i)
        # Skip weekends (rough approximation)
        if date.weekday() >= 5:
            continue
        
        data.append({
            "symbol": "000300",
            "date": date.strftime("%Y-%m-%d"),
            "open": 3800.0 + i * 2,
            "high": 3820.0 + i * 2,
            "low": 3790.0 + i * 2,
            "close": 3810.0 + i * 2,
            "volume": 100000000 + i * 100000,
            "amount": 50000000000.0 + i * 10000000,
        })
    
    conn = sqlite3.connect(str(db_path))
    try:
        for row in data:
            conn.execute(
                """
                INSERT INTO index_klines (symbol, date, open, high, low, close, volume, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, volume=excluded.volume, amount=excluded.amount
                """,
                (
                    row["symbol"],
                    row["date"],
                    row["open"],
                    row["high"],
                    row["low"],
                    row["close"],
                    row["volume"],
                    row["amount"],
                ),
            )
        conn.commit()
        print(f"Successfully seeded {len(data)} mock CSI 300 data points")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
