"""Tests for backtesting_adapter module."""

from __future__ import annotations

import pandas as pd
import pytest

from src.adapters.backtesting_adapter import ashare_commission, prepare_backtesting_data
from src.data_layer.market_reader import MarketReader


class TestPrepareBacktestingData:
    """Tests for prepare_backtesting_data function."""

    @pytest.fixture
    def reader(self):
        """Create MarketReader instance."""
        return MarketReader()

    def test_column_renaming(self, reader):
        """Test that columns are renamed to title-case."""
        df = prepare_backtesting_data(
            symbol="000001",
            start_date="2026-01-01",
            end_date="2026-03-01",
            reader=reader,
        )

        assert not df.empty, "DataFrame should contain data"

        # Check required title-case columns exist
        required_columns = ["Open", "High", "Low", "Close", "Volume"]
        for col in required_columns:
            assert col in df.columns, f"Column {col} should exist"

        # Check lowercase variants don't exist
        lowercase_columns = ["open", "high", "low", "close", "volume"]
        for col in lowercase_columns:
            assert col not in df.columns, f"Lowercase column {col} should not exist"

    def test_datetimeindex_conversion(self, reader):
        """Test that date is converted to DatetimeIndex."""
        df = prepare_backtesting_data(
            symbol="000001",
            start_date="2026-01-01",
            end_date="2026-03-01",
            reader=reader,
        )

        assert not df.empty, "DataFrame should contain data"

        # Check index is DatetimeIndex
        assert isinstance(
            df.index, pd.DatetimeIndex
        ), "Index should be DatetimeIndex"

        # Check no NaT values
        assert not df.index.isna().any(), "Index should not contain NaT values"

        # Check monotonically increasing
        assert df.index.is_monotonic_increasing, "Index should be monotonically increasing"

    def test_indicator_columns_preserved(self, reader):
        """Test that indicator columns (Dif, Dea, Macd) are preserved."""
        df = prepare_backtesting_data(
            symbol="000001",
            start_date="2026-01-01",
            end_date="2026-03-01",
            reader=reader,
        )

        assert not df.empty, "DataFrame should contain data"

        # Check indicator columns exist
        indicator_columns = ["Dif", "Dea", "Macd"]
        for col in indicator_columns:
            assert col in df.columns, f"Indicator column {col} should exist"

    def test_amount_column_dropped(self, reader):
        """Test that the 'amount' column is dropped."""
        df = prepare_backtesting_data(
            symbol="000001",
            start_date="2026-01-01",
            end_date="2026-03-01",
            reader=reader,
        )

        assert not df.empty, "DataFrame should contain data"

        # Check amount column is dropped
        assert "amount" not in df.columns, "Amount column should be dropped"
        assert "Amount" not in df.columns, "Amount column should be dropped"

    def test_empty_dataframe_edge_case(self, reader):
        """Test handling of empty DataFrame (nonexistent symbol)."""
        df = prepare_backtesting_data(
            symbol="NONEXISTENT",
            start_date="2026-01-01",
            end_date="2026-03-01",
            reader=reader,
        )

        # Should return empty DataFrame with correct schema
        assert df.empty, "DataFrame should be empty for nonexistent symbol"

        # Check correct columns exist even when empty
        expected_columns = ["Open", "High", "Low", "Close", "Volume", "Dif", "Dea", "Macd"]
        assert list(df.columns) == expected_columns, "Empty DataFrame should have correct columns"

        # Check index is DatetimeIndex
        assert isinstance(df.index, pd.DatetimeIndex), "Index should be DatetimeIndex even when empty"


class TestAshareCommission:
    """Tests for ashare_commission function."""

    def test_buy_commission_minimum(self):
        """Test buy commission with minimum fee applied."""
        # Trade: 100 shares at 10.0 = 1000 total
        # Commission: 1000 * 0.0003 = 0.30
        # Minimum is 5.0, so result should be 5.0
        commission = ashare_commission(size=100, price=10.0, is_buy=True)
        assert commission == 5.0, "Buy commission should apply minimum fee of 5.0"

    def test_buy_commission_above_minimum(self):
        """Test buy commission when calculated fee exceeds minimum."""
        # Trade: 10000 shares at 50.0 = 500000 total
        # Commission: 500000 * 0.0003 = 150.0
        # Above minimum, so result should be 150.0
        commission = ashare_commission(size=10000, price=50.0, is_buy=True)
        assert commission == 150.0, "Buy commission should be calculated fee when above minimum"

    def test_sell_commission_with_stamp_tax(self):
        """Test sell commission includes stamp tax."""
        # Trade: 100 shares at 10.0 = 1000 total
        # Base commission: max(5.0, 1000 * 0.0003) = 5.0
        # Stamp tax: 1000 * 0.001 = 1.0
        # Total: 5.0 + 1.0 = 6.0
        commission = ashare_commission(size=100, price=10.0, is_buy=False)
        assert commission == 6.0, "Sell commission should include stamp tax"

    def test_large_sell_commission(self):
        """Test large sell commission calculation."""
        # Trade: 10000 shares at 50.0 = 500000 total
        # Base commission: max(5.0, 500000 * 0.0003) = 150.0
        # Stamp tax: 500000 * 0.001 = 500.0
        # Total: 150.0 + 500.0 = 650.0
        commission = ashare_commission(size=10000, price=50.0, is_buy=False)
        assert commission == 650.0, "Large sell commission should calculate correctly"

    def test_zero_size(self):
        """Test commission with zero size."""
        commission = ashare_commission(size=0, price=10.0, is_buy=True)
        assert commission == 5.0, "Zero size should return minimum commission"

    def test_negative_size_absolute_value(self):
        """Test that negative size is handled with abs()."""
        # Sell trades might pass negative size
        commission = ashare_commission(size=-100, price=10.0, is_buy=False)
        expected = 6.0  # Same as positive 100
        assert commission == expected, "Negative size should be handled with abs()"

    def test_two_arg_callback_positive_size(self):
        """Test 2-arg callback with positive size (inferred as buy)."""
        # backtesting.py calls commission(size, price) with only 2 args
        # Positive size should be inferred as buy
        commission = ashare_commission(100, 10.0)
        assert commission == 5.0, "Positive size should be inferred as buy (no stamp tax)"

    def test_two_arg_callback_negative_size(self):
        """Test 2-arg callback with negative size (inferred as sell)."""
        # backtesting.py calls commission(size, price) with only 2 args
        # Negative size should be inferred as sell
        commission = ashare_commission(-100, 10.0)
        assert commission == 6.0, "Negative size should be inferred as sell (with stamp tax)"

    def test_two_arg_callback_large_trade(self):
        """Test 2-arg callback with larger trade sizes."""
        # Buy trade (positive size)
        buy_commission = ashare_commission(10000, 50.0)
        assert buy_commission == 150.0, "Large buy should calculate correctly"

        # Sell trade (negative size)
        sell_commission = ashare_commission(-10000, 50.0)
        assert sell_commission == 650.0, "Large sell should calculate correctly with stamp tax"
