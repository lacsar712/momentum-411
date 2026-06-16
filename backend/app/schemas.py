from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class DateRangeRequest(BaseModel):
    start_date: date
    end_date: date
    symbols: Optional[List[str]] = None
    sync_type: str = Field(default="incremental")

class DailyDataRequest(BaseModel):
    trade_date: date
    symbols: Optional[List[str]] = None

class PriceRangeRequest(BaseModel):
    symbol: str
    start_date: date
    end_date: date
    frequency: str = Field(default="D") # D, W, M

class ScreeningRequest(BaseModel):
    name: Optional[str] = None
    basic_filters: Dict[str, Any] = Field(default_factory=dict)
    technical_filters: Dict[str, Any] = Field(default_factory=dict)
    factor_filters: Dict[str, Any] = Field(default_factory=dict)
    custom_filters: List[Dict[str, Any]] = Field(default_factory=list)

class ScreeningExportRequest(ScreeningRequest):
    file_type: str = Field(default="csv")

class ScreeningResponse(BaseModel):
    total: int
    items: List[Dict[str, Any]]

class PatternScanRequest(BaseModel):
    symbols: Optional[List[str]] = None
    patterns: List[str]
    start_date: date
    end_date: date
    params: Dict[str, Any] = Field(default_factory=dict)

class BacktestRequest(BaseModel):
    strategy_name: str
    symbols: List[str]
    start_date: date
    end_date: date
    parameters: Dict[str, Any] = Field(default_factory=dict)

class ExportRequest(BaseModel):
    symbols: Optional[List[str]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    file_type: str = Field(default="csv")

class PresetRequest(BaseModel):
    name: str
    payload: Dict[str, Any]

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    token: str
    role: str

class LogDeleteRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    delete_all: bool = False

class UserInfoResponse(BaseModel):
    id: int
    username: str
    role: str
    avatar_url: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class ActivityLogItem(BaseModel):
    id: int
    action_type: str
    action_detail: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

class ActivityLogResponse(BaseModel):
    total: int
    items: List[ActivityLogItem]

class PreferencesUpdateRequest(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    default_page: Optional[str] = None

class PreferencesResponse(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    default_page: Optional[str] = None

class RoleCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None

class RoleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class UserRoleRequest(BaseModel):
    role_id: int

class RolePermissionRequest(BaseModel):
    permission_id: int

class PermissionGroupResponse(BaseModel):
    module: str
    permissions: List[Dict[str, Any]]

class UserDetailResponse(BaseModel):
    id: int
    username: str
    role: str
    avatar_url: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    roles: List[Dict[str, Any]] = []
    permissions: List[str] = []

class RoleDetailResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_builtin: bool = False
    created_at: datetime
    permissions: List[Dict[str, Any]] = []

class MyPermissionsResponse(BaseModel):
    permissions: List[str]
    roles: List[str]

class NotificationItem(BaseModel):
    id: int
    user_id: int
    type: str
    title: str
    content: Optional[str] = None
    link_url: Optional[str] = None
    severity: str
    is_read: bool
    created_at: datetime

class NotificationListResponse(BaseModel):
    total: int
    items: List[NotificationItem]

class NotificationUnreadResponse(BaseModel):
    unread_count: int

class NotificationMarkReadRequest(BaseModel):
    ids: Optional[List[int]] = None
    mark_all: bool = False

class NotificationDeleteRequest(BaseModel):
    ids: List[int]

class NotificationPreferenceItem(BaseModel):
    id: Optional[int] = None
    notification_type: str
    enabled: bool
    threshold_up: Optional[float] = None
    threshold_down: Optional[float] = None

class NotificationPreferenceUpdateRequest(BaseModel):
    preferences: List[NotificationPreferenceItem]

class NotificationPreferenceResponse(BaseModel):
    preferences: List[NotificationPreferenceItem]
    available_types: List[Dict[str, Any]]

class WatchlistItem(BaseModel):
    id: int
    symbol: str
    name: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    latest_price: Optional[float] = None
    daily_change: Optional[float] = None

class WatchlistAddRequest(BaseModel):
    symbol: str
    notes: Optional[str] = None

class WatchlistRemoveRequest(BaseModel):
    symbol: str

class WatchlistResponse(BaseModel):
    total: int
    items: List[WatchlistItem]

# ==================== 投资组合管理 Schema ====================

class PortfolioHoldingItem(BaseModel):
    id: Optional[int] = None
    symbol: str
    name: Optional[str] = None
    target_weight: float
    current_weight: Optional[float] = None
    weight_deviation: Optional[float] = None
    latest_price: Optional[float] = None
    daily_change: Optional[float] = None

class PortfolioBase(BaseModel):
    name: str
    description: Optional[str] = None
    benchmark_code: Optional[str] = "000300"
    rebalance_frequency: Optional[str] = "monthly"

class PortfolioCreateRequest(PortfolioBase):
    holdings: List[PortfolioHoldingItem] = []

class PortfolioUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    benchmark_code: Optional[str] = None
    rebalance_frequency: Optional[str] = None

class PortfolioCopyRequest(BaseModel):
    new_name: str

class PortfolioResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    benchmark_code: str
    rebalance_frequency: str
    created_at: datetime
    updated_at: datetime
    holdings: List[PortfolioHoldingItem] = []

class PortfolioListResponse(BaseModel):
    total: int
    items: List[PortfolioResponse]

class PortfolioHoldingCreateRequest(BaseModel):
    symbol: str
    target_weight: float

class PortfolioHoldingUpdateRequest(BaseModel):
    target_weight: Optional[float] = None

class PortfolioHoldingsBatchSaveRequest(BaseModel):
    holdings: List[PortfolioHoldingItem]

class PortfolioHoldingsResponse(BaseModel):
    total: int
    items: List[PortfolioHoldingItem]

class PortfolioNavPoint(BaseModel):
    trade_date: date
    portfolio_nav: float
    benchmark_nav: float

class PortfolioNavResponse(BaseModel):
    start_date: date
    end_date: date
    rebalance_frequency: str
    rebalance_count: int
    data: List[PortfolioNavPoint]

class PortfolioMetricsResponse(BaseModel):
    annual_return: float
    benchmark_annual_return: float
    excess_return: float
    max_drawdown: float
    benchmark_max_drawdown: float
    sharpe_ratio: float
    information_ratio: float
    correlation: float
    total_return: float
    benchmark_total_return: float
    volatility: float
    benchmark_volatility: float

class RebalanceSuggestion(BaseModel):
    symbol: str
    name: Optional[str] = None
    target_weight: float
    current_weight: float
    deviation: float
    action: str
    suggested_amount: float
    latest_price: Optional[float] = None

class RebalanceResponse(BaseModel):
    threshold: float
    total_deviation: float
    needs_rebalance: bool
    suggestions: List[RebalanceSuggestion]
    portfolio_value: Optional[float] = None

# ==================== 风险指标 Schema ====================

class RiskBaseRequest(BaseModel):
    symbols: List[str]
    start_date: date
    end_date: date


class RiskVarRequest(RiskBaseRequest):
    confidence_levels: Optional[List[float]] = Field(default_factory=lambda: [0.95, 0.99])
    holding_period: int = Field(default=1, ge=1, le=252)


class RiskBetaRequest(RiskBaseRequest):
    benchmark_code: str = Field(default="000300")


class RiskCorrelationRequest(RiskBaseRequest):
    pass


class RiskMetricsRequest(RiskBaseRequest):
    pass


class RiskRollingBetaRequest(RiskBetaRequest):
    window: int = Field(default=60, ge=20, le=252)


class RiskAllRequest(RiskBaseRequest):
    benchmark_code: str = Field(default="000300")
    confidence_levels: Optional[List[float]] = Field(default_factory=lambda: [0.95, 0.99])
    holding_period: int = Field(default=1, ge=1, le=252)
    rolling_window: int = Field(default=60, ge=20, le=252)
