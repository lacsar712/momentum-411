import math
from datetime import date, datetime

import pytest
from sqlmodel import SQLModel, Session, create_engine

from app.models import Stock, StockSnapshot
from app.services.screening import screen_stocks


@pytest.fixture
def engine():
    e = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(e)
    return e


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


def _add_stock(session, *, symbol, name, market="SH", industry="Tech",
               market_cap=None, pe_ratio=None, pb_ratio=None):
    stock = Stock(symbol=symbol, name=name, market=market, industry=industry,
                  market_cap=market_cap, pe_ratio=pe_ratio, pb_ratio=pb_ratio)
    session.add(stock)
    session.flush()
    return stock


def _add_snapshot(session, stock_id, *, close=10.0, volume=1000.0,
                  latest_date=date(2025, 1, 1),
                  rsi=None, macd_line=None, macd_signal=None, macd_hist=None,
                  kdj_k=None, kdj_d=None, kdj_j=None,
                  momentum=None, volatility=None, liquidity=None):
    snap = StockSnapshot(
        stock_id=stock_id, latest_date=latest_date,
        close=close, volume=volume,
        rsi=rsi, macd_line=macd_line, macd_signal=macd_signal,
        macd_hist=macd_hist, kdj_k=kdj_k, kdj_d=kdj_d, kdj_j=kdj_j,
        momentum=momentum, volatility=volatility, liquidity=liquidity,
    )
    session.add(snap)
    session.flush()
    return snap


class TestEmptyScreening:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="StockA", market_cap=1e9)
        _add_snapshot(session, s1.id, close=5.0, volume=100)
        s2 = _add_stock(session, symbol="600002", name="StockB", market_cap=2e9)
        _add_snapshot(session, s2.id, close=6.0, volume=200)
        session.commit()

    def test_returns_all_when_no_criteria(self, session, data):
        result = screen_stocks(session, {})
        assert len(result) == 2
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001", "600002"}

    def test_result_structure(self, session, data):
        result = screen_stocks(session, {})
        item = result[0]
        expected_keys = {
            "id", "symbol", "name", "market", "industry", "market_cap",
            "pe_ratio", "pb_ratio", "close", "volume", "rsi", "macd_line",
            "macd_signal", "macd_hist", "kdj_k", "kdj_d", "kdj_j",
            "momentum", "volatility", "liquidity", "trade_date",
        }
        assert set(item.keys()) == expected_keys

    def test_trade_date_serialized_as_string(self, session, data):
        result = screen_stocks(session, {})
        for item in result:
            assert isinstance(item["trade_date"], str)


class TestBasicFilterMarketCap:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="Small", market_cap=500e6)
        _add_snapshot(session, s1.id)
        s2 = _add_stock(session, symbol="600002", name="Mid", market_cap=5e9)
        _add_snapshot(session, s2.id)
        s3 = _add_stock(session, symbol="600003", name="Large", market_cap=50e9)
        _add_snapshot(session, s3.id)
        session.commit()

    def test_market_cap_min(self, session, data):
        result = screen_stocks(session, {"basic_filters": {"market_cap_min": 1e9}})
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600002", "600003"}

    def test_market_cap_max(self, session, data):
        result = screen_stocks(session, {"basic_filters": {"market_cap_max": 10e9}})
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001", "600002"}

    def test_market_cap_range(self, session, data):
        result = screen_stocks(session, {
            "basic_filters": {"market_cap_min": 1e9, "market_cap_max": 10e9}
        })
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600002"}


class TestBasicFilterPE:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="LowPE", market_cap=1e9, pe_ratio=8.0)
        _add_snapshot(session, s1.id)
        s2 = _add_stock(session, symbol="600002", name="MidPE", market_cap=2e9, pe_ratio=25.0)
        _add_snapshot(session, s2.id)
        s3 = _add_stock(session, symbol="600003", name="HighPE", market_cap=3e9, pe_ratio=80.0)
        _add_snapshot(session, s3.id)
        session.commit()

    def test_pe_min(self, session, data):
        result = screen_stocks(session, {"basic_filters": {"pe_min": 20}})
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600002", "600003"}

    def test_pe_max(self, session, data):
        result = screen_stocks(session, {"basic_filters": {"pe_max": 30}})
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001", "600002"}

    def test_pe_range(self, session, data):
        result = screen_stocks(session, {
            "basic_filters": {"pe_min": 10, "pe_max": 30}
        })
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600002"}


class TestBasicFilterPB:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="LowPB", market_cap=1e9, pb_ratio=0.8)
        _add_snapshot(session, s1.id)
        s2 = _add_stock(session, symbol="600002", name="MidPB", market_cap=2e9, pb_ratio=3.0)
        _add_snapshot(session, s2.id)
        s3 = _add_stock(session, symbol="600003", name="HighPB", market_cap=3e9, pb_ratio=10.0)
        _add_snapshot(session, s3.id)
        session.commit()

    def test_pb_min(self, session, data):
        result = screen_stocks(session, {"basic_filters": {"pb_min": 2.0}})
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600002", "600003"}

    def test_pb_max(self, session, data):
        result = screen_stocks(session, {"basic_filters": {"pb_max": 5.0}})
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001", "600002"}

    def test_pb_range(self, session, data):
        result = screen_stocks(session, {
            "basic_filters": {"pb_min": 1.0, "pb_max": 5.0}
        })
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600002"}


class TestTechnicalFilterRSI:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="Oversold", market_cap=1e9)
        _add_snapshot(session, s1.id, rsi=20.0)
        s2 = _add_stock(session, symbol="600002", name="Neutral", market_cap=2e9)
        _add_snapshot(session, s2.id, rsi=50.0)
        s3 = _add_stock(session, symbol="600003", name="Overbought", market_cap=3e9)
        _add_snapshot(session, s3.id, rsi=85.0)
        session.commit()

    def test_rsi_min(self, session, data):
        result = screen_stocks(session, {"technical_filters": {"rsi_min": 40}})
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600002", "600003"}

    def test_rsi_max(self, session, data):
        result = screen_stocks(session, {"technical_filters": {"rsi_max": 60}})
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001", "600002"}

    def test_rsi_range(self, session, data):
        result = screen_stocks(session, {
            "technical_filters": {"rsi_min": 30, "rsi_max": 70}
        })
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600002"}


class TestTechnicalFilterMACD:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="Bullish", market_cap=1e9)
        _add_snapshot(session, s1.id, macd_line=1.5, macd_signal=0.8)
        s2 = _add_stock(session, symbol="600002", name="Bearish", market_cap=2e9)
        _add_snapshot(session, s2.id, macd_line=0.3, macd_signal=1.0)
        session.commit()

    def test_macd_positive_filters_bearish(self, session, data):
        result = screen_stocks(session, {"technical_filters": {"macd_positive": True}})
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001"}

    def test_macd_positive_false_no_filter(self, session, data):
        result = screen_stocks(session, {"technical_filters": {"macd_positive": False}})
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001", "600002"}


class TestTechnicalFilterKDJ:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="KAboveD", market_cap=1e9)
        _add_snapshot(session, s1.id, kdj_k=70.0, kdj_d=50.0)
        s2 = _add_stock(session, symbol="600002", name="KBelowD", market_cap=2e9)
        _add_snapshot(session, s2.id, kdj_k=30.0, kdj_d=50.0)
        session.commit()

    def test_kdj_positive_filters(self, session, data):
        result = screen_stocks(session, {"technical_filters": {"kdj_positive": True}})
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001"}

    def test_kdj_positive_false_no_filter(self, session, data):
        result = screen_stocks(session, {"technical_filters": {"kdj_positive": False}})
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001", "600002"}


class TestFactorFilters:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="HighMom", market_cap=1e9)
        _add_snapshot(session, s1.id, momentum=0.8, volatility=0.15, liquidity=0.9)
        s2 = _add_stock(session, symbol="600002", name="LowMom", market_cap=2e9)
        _add_snapshot(session, s2.id, momentum=0.2, volatility=0.5, liquidity=0.3)
        session.commit()

    def test_momentum_range(self, session, data):
        result = screen_stocks(session, {
            "factor_filters": {"momentum_min": 0.5, "momentum_max": 1.0}
        })
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001"}

    def test_volatility_range(self, session, data):
        result = screen_stocks(session, {
            "factor_filters": {"volatility_min": 0.4, "volatility_max": 0.6}
        })
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600002"}

    def test_liquidity_min(self, session, data):
        result = screen_stocks(session, {
            "factor_filters": {"liquidity_min": 0.5}
        })
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001"}

    def test_combined_factors(self, session, data):
        result = screen_stocks(session, {
            "factor_filters": {
                "momentum_min": 0.5,
                "volatility_max": 0.3,
                "liquidity_min": 0.5,
            }
        })
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001"}


class TestCustomFilterAllowedFields:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="Expensive", market_cap=1e9, pe_ratio=50.0)
        _add_snapshot(session, s1.id, close=100.0, volume=5000.0, rsi=60.0)
        s2 = _add_stock(session, symbol="600002", name="Cheap", market_cap=2e9, pe_ratio=8.0)
        _add_snapshot(session, s2.id, close=5.0, volume=200.0, rsi=30.0)
        session.commit()

    def test_custom_filter_stock_field(self, session, data):
        result = screen_stocks(session, {
            "custom_filters": [{"field": "pe_ratio", "max": 20}]
        })
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600002"}

    def test_custom_filter_snapshot_field(self, session, data):
        result = screen_stocks(session, {
            "custom_filters": [{"field": "rsi", "min": 50}]
        })
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001"}

    def test_custom_filter_close_range(self, session, data):
        result = screen_stocks(session, {
            "custom_filters": [{"field": "close", "min": 10, "max": 200}]
        })
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001"}


class TestCustomFilterDisallowedField:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="Normal", market_cap=1e9)
        _add_snapshot(session, s1.id)
        session.commit()

    def test_sql_injection_field_ignored(self, session, data):
        result = screen_stocks(session, {
            "custom_filters": [
                {"field": "1=1; DROP TABLE stock; --", "min": 0}
            ]
        })
        assert len(result) == 1
        assert result[0]["symbol"] == "600001"

    def test_non_whitelisted_field_ignored(self, session, data):
        result = screen_stocks(session, {
            "custom_filters": [
                {"field": "nonexistent_column", "min": 0}
            ]
        })
        assert len(result) == 1
        assert result[0]["symbol"] == "600001"

    def test_id_field_not_in_whitelist(self, session, data):
        result = screen_stocks(session, {
            "custom_filters": [
                {"field": "id", "min": 0}
            ]
        })
        assert len(result) == 1


class TestCustomFilterNoneHandling:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="HasPE", market_cap=1e9, pe_ratio=20.0)
        _add_snapshot(session, s1.id, rsi=55.0)
        session.commit()

    def test_none_min_ignored(self, session, data):
        result = screen_stocks(session, {
            "custom_filters": [{"field": "pe_ratio", "min": None, "max": 30}]
        })
        assert len(result) == 1

    def test_none_max_ignored(self, session, data):
        result = screen_stocks(session, {
            "custom_filters": [{"field": "rsi", "min": 50, "max": None}]
        })
        assert len(result) == 1

    def test_both_none_no_filter(self, session, data):
        result = screen_stocks(session, {
            "custom_filters": [{"field": "pe_ratio", "min": None, "max": None}]
        })
        assert len(result) == 1


class TestSortAndLimit:
    @pytest.fixture
    def data(self, session):
        caps = [3e9, 1e9, 5e9, 2e9, 4e9]
        for i, cap in enumerate(caps, 1):
            s = _add_stock(session, symbol=f"60000{i}", name=f"S{i}", market_cap=cap)
            _add_snapshot(session, s.id)
        session.commit()

    def test_sorted_by_market_cap_desc(self, session, data):
        result = screen_stocks(session, {})
        caps = [r["market_cap"] for r in result]
        assert caps == sorted(caps, reverse=True)

    def test_limit_200(self, engine):
        with Session(engine) as s:
            for i in range(1, 203):
                stock = Stock(symbol=f"S{i:04d}", name=f"Stock{i}",
                              market="SH", market_cap=float(i))
                s.add(stock)
                s.flush()
                snap = StockSnapshot(stock_id=stock.id, latest_date=date(2025, 1, 1),
                                     close=1.0, volume=1.0)
                s.add(snap)
            s.commit()
            result = screen_stocks(s, {})
            assert len(result) == 200


class TestNaNInfCleaning:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="NaNStock", market_cap=1e9)
        _add_snapshot(session, s1.id, rsi=float("nan"), macd_line=1.0,
                      kdj_k=float("inf"), momentum=float("-inf"), volatility=0.5)
        s2 = _add_stock(session, symbol="600002", name="NormalStock", market_cap=2e9)
        _add_snapshot(session, s2.id, rsi=50.0, macd_line=0.5, volatility=0.3)
        session.commit()

    def test_nan_replaced_with_none(self, session, data):
        result = screen_stocks(session, {})
        nan_stock = next(r for r in result if r["symbol"] == "600001")
        assert nan_stock["rsi"] is None

    def test_inf_replaced_with_none(self, session, data):
        result = screen_stocks(session, {})
        inf_stock = next(r for r in result if r["symbol"] == "600001")
        assert inf_stock["kdj_k"] is None
        assert inf_stock["momentum"] is None

    def test_normal_floats_preserved(self, session, data):
        result = screen_stocks(session, {})
        nan_stock = next(r for r in result if r["symbol"] == "600001")
        assert nan_stock["macd_line"] == 1.0
        assert nan_stock["volatility"] == 0.5

    def test_clean_stock_unaffected(self, session, data):
        result = screen_stocks(session, {})
        normal = next(r for r in result if r["symbol"] == "600002")
        assert normal["rsi"] == 50.0
        assert normal["macd_line"] == 0.5


class TestStockWithoutSnapshot:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="WithSnap", market_cap=1e9)
        _add_snapshot(session, s1.id, close=10.0, rsi=50.0)
        s2 = _add_stock(session, symbol="600002", name="NoSnap", market_cap=2e9)
        session.commit()

    def test_left_join_includes_stock_without_snapshot(self, session, data):
        result = screen_stocks(session, {})
        assert len(result) == 2

    def test_snapshot_fields_none_when_missing(self, session, data):
        result = screen_stocks(session, {})
        no_snap = next(r for r in result if r["symbol"] == "600002")
        assert no_snap["close"] is None
        assert no_snap["rsi"] is None
        assert no_snap["trade_date"] is None

    def test_snapshot_fields_populated_when_present(self, session, data):
        result = screen_stocks(session, {})
        with_snap = next(r for r in result if r["symbol"] == "600001")
        assert with_snap["close"] == 10.0
        assert with_snap["rsi"] == 50.0


class TestNullMarketCapSort:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="HasCap", market_cap=1e9)
        _add_snapshot(session, s1.id)
        s2 = _add_stock(session, symbol="600002", name="NoCap", market_cap=None)
        _add_snapshot(session, s2.id)
        s3 = _add_stock(session, symbol="600003", name="BigCap", market_cap=5e9)
        _add_snapshot(session, s3.id)
        session.commit()

    def test_null_market_cap_sorted_last(self, session, data):
        result = screen_stocks(session, {})
        symbols = [r["symbol"] for r in result]
        assert symbols.index("600002") > symbols.index("600001")
        assert symbols.index("600002") > symbols.index("600003")


class TestCombinedFilters:
    @pytest.fixture
    def data(self, session):
        s1 = _add_stock(session, symbol="600001", name="MatchAll", market_cap=10e9, pe_ratio=20.0, pb_ratio=2.0)
        _add_snapshot(session, s1.id, rsi=55.0, macd_line=1.0, macd_signal=0.5,
                      kdj_k=60.0, kdj_d=40.0, momentum=0.7, volatility=0.2, liquidity=0.8)
        s2 = _add_stock(session, symbol="600002", name="FailBasic", market_cap=0.5e9, pe_ratio=20.0, pb_ratio=2.0)
        _add_snapshot(session, s2.id, rsi=55.0, macd_line=1.0, macd_signal=0.5,
                      kdj_k=60.0, kdj_d=40.0, momentum=0.7, volatility=0.2, liquidity=0.8)
        s3 = _add_stock(session, symbol="600003", name="FailTech", market_cap=10e9, pe_ratio=20.0, pb_ratio=2.0)
        _add_snapshot(session, s3.id, rsi=20.0, macd_line=0.3, macd_signal=1.0,
                      kdj_k=30.0, kdj_d=50.0, momentum=0.7, volatility=0.2, liquidity=0.8)
        s4 = _add_stock(session, symbol="600004", name="FailFactor", market_cap=10e9, pe_ratio=20.0, pb_ratio=2.0)
        _add_snapshot(session, s4.id, rsi=55.0, macd_line=1.0, macd_signal=0.5,
                      kdj_k=60.0, kdj_d=40.0, momentum=0.1, volatility=0.2, liquidity=0.8)
        session.commit()

    def test_combined_basic_tech_factor(self, session, data):
        result = screen_stocks(session, {
            "basic_filters": {"market_cap_min": 1e9},
            "technical_filters": {"rsi_min": 40, "macd_positive": True, "kdj_positive": True},
            "factor_filters": {"momentum_min": 0.5},
        })
        symbols = {r["symbol"] for r in result}
        assert symbols == {"600001"}
