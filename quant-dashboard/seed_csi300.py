#!/usr/bin/env python3
"""Manual script to seed CSI 300 data into index_cache.db."""

from src.data_layer.index_fetcher import IndexFetcher

def main():
    fetcher = IndexFetcher()
    
    # Check if data already exists
    df = fetcher.get_csi300()
    if not df.empty:
        print(f"CSI 300 data already exists ({len(df)} rows)")
        return
    
    # Fetch from AkShare
    print("Fetching CSI 300 data from AkShare...")
    try:
        count = fetcher.fetch_and_store(
            symbol="000300",
            period="daily",
            start_date="20251101",
            end_date="20260325",
        )
        print(f"Successfully seeded {count} CSI 300 data points")
    except Exception as e:
        print(f"Failed to fetch CSI 300 data: {e}")
        raise

if __name__ == "__main__":
    main()
