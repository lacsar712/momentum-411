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
