from fastapi import APIRouter

from app.routers.deps import (
    session_dep,
    auth_dep,
    admin_dep,
    require_permission,
    _get_user_permissions,
)

from app.routers.auth import router as auth_router
from app.routers.admin import router as admin_router
from app.routers.sync import router as sync_router
from app.routers.data import router as data_router
from app.routers.screening import router as screening_router
from app.routers.patterns import router as patterns_router
from app.routers.backtest import router as backtest_router
from app.routers.export import router as export_router
from app.routers.logs import router as logs_router
from app.routers.notifications import router as notifications_router
from app.routers.watchlist import router as watchlist_router
from app.routers.portfolio import router as portfolio_router
from app.routers.risk import router as risk_router
from app.routers.recommend import router as recommend_router
from app.routers.leaderboard import router as leaderboard_router
from app.routers.tags_notes import router as tags_notes_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(admin_router)
router.include_router(sync_router)
router.include_router(data_router)
router.include_router(screening_router)
router.include_router(patterns_router)
router.include_router(backtest_router)
router.include_router(export_router)
router.include_router(logs_router)
router.include_router(notifications_router)
router.include_router(watchlist_router)
router.include_router(portfolio_router)
router.include_router(risk_router)
router.include_router(recommend_router)
router.include_router(leaderboard_router)
router.include_router(tags_notes_router)


from app.services.task_manager import task_manager


class _SyncStateProxy(dict):
    def __getitem__(self, key):
        return task_manager.get_state()[key]

    def __setitem__(self, key, value):
        with task_manager._state_lock:
            task_manager._state[key] = value

    def __contains__(self, key):
        return key in task_manager.get_state()

    def __iter__(self):
        return iter(task_manager.get_state())

    def __len__(self):
        return len(task_manager.get_state())

    def update(self, *args, **kwargs):
        with task_manager._state_lock:
            task_manager._state.update(*args, **kwargs)

    def keys(self):
        return task_manager.get_state().keys()

    def values(self):
        return task_manager.get_state().values()

    def items(self):
        return task_manager.get_state().items()

    def copy(self):
        return task_manager.get_state()


SYNC_STATE = _SyncStateProxy()


def update_progress(current, total, message=""):
    task_manager.update_progress(current, total, message)


def _send_task_notification(user_id, task_type, task_name, success, message=""):
    task_manager._send_task_notification(user_id, task_type, task_name, success, message)


def run_sync_stock_list_task(user_id=None):
    task_manager.run_sync_stock_list_task(user_id)


def run_sync_daily_task(symbols, start_date, end_date, sync_type, user_id=None):
    task_manager.run_sync_daily_task(symbols, start_date, end_date, sync_type, user_id)


def run_snapshot_update_task(user_id=None):
    task_manager.run_snapshot_update_task(user_id)


def run_sync_index_list_task(user_id=None):
    task_manager.run_sync_index_list_task(user_id)


def run_sync_index_daily_task(codes, start_date, end_date, sync_type, user_id=None):
    task_manager.run_sync_index_daily_task(codes, start_date, end_date, sync_type, user_id)
