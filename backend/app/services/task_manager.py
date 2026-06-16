import threading
from typing import Any, Callable, Dict, Optional
from enum import Enum

from app.db import get_session


class TaskStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    FINISHED = "finished"
    ERROR = "error"


class TaskType(str, Enum):
    STOCK_LIST = "stock_list"
    DAILY = "daily"
    SNAPSHOT = "snapshot"
    INDEX_LIST = "index_list"
    INDEX_DAILY = "index_daily"
    BACKTEST = "backtest"
    PATTERN_SCAN = "pattern_scan"


class TaskManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._state = {
                        "status": TaskStatus.IDLE.value,
                        "type": None,
                        "current": 0,
                        "total": 0,
                        "message": "",
                        "user_id": None,
                    }
                    cls._instance._state_lock = threading.Lock()
        return cls._instance

    def get_state(self) -> Dict[str, Any]:
        with self._state_lock:
            return dict(self._state)

    def is_running(self) -> bool:
        with self._state_lock:
            return self._state["status"] == TaskStatus.RUNNING.value

    def update_progress(self, current: int, total: int, message: str = ""):
        with self._state_lock:
            self._state["current"] = current
            self._state["total"] = total
            if message:
                self._state["message"] = message

    def start_task(self, task_type: str, user_id: Optional[int] = None, message: str = "正在启动..."):
        with self._state_lock:
            self._state.update({
                "status": TaskStatus.RUNNING.value,
                "type": task_type,
                "current": 0,
                "total": 0,
                "message": message,
                "user_id": user_id,
            })

    def finish_task(self, current: int, total: int, message: str):
        with self._state_lock:
            self._state.update({
                "status": TaskStatus.FINISHED.value,
                "current": current,
                "total": total,
                "message": message,
            })

    def error_task(self, message: str):
        with self._state_lock:
            self._state.update({
                "status": TaskStatus.ERROR.value,
                "message": message,
            })

    def _send_task_notification(self, user_id: int, task_type: str, task_name: str, success: bool, message: str = ""):
        if not user_id:
            return
        try:
            from app.services.notification import create_notification
            with get_session() as session:
                severity = "success" if success else "error"
                link_url = {
                    "stock_list": "/data",
                    "daily": "/data",
                    "snapshot": "/data",
                    "backtest": "/backtest",
                    "pattern_scan": "/patterns",
                    "index_list": "/index",
                    "index_daily": "/index",
                }.get(task_type, "/notifications")
                create_notification(
                    session,
                    user_id=user_id,
                    notification_type={
                        "stock_list": "data_sync",
                        "daily": "data_sync",
                        "snapshot": "data_sync",
                        "backtest": "backtest",
                        "pattern_scan": "pattern_scan",
                        "index_list": "data_sync",
                        "index_daily": "data_sync",
                    }.get(task_type, "system"),
                    title=f"{task_name}{'成功' if success else '失败'}",
                    content=message or f"{task_name}已{'成功完成' if success else '执行失败'}",
                    link_url=link_url,
                    severity=severity,
                )
        except Exception as e:
            print(f"[通知] 发送任务通知失败: {e}")

    def progress_callback(self, current: int, total: int, message: str = ""):
        self.update_progress(current, total, message)

    def run_sync_stock_list_task(self, user_id: int = None):
        self.start_task(TaskType.STOCK_LIST.value, user_id=user_id)
        task_name = "股票清单同步"
        try:
            from app.services.data_sync import sync_stock_list
            with get_session() as session:
                count = sync_stock_list(session, progress_callback=self.progress_callback)
                self.update_progress(count, count, f"股票清单同步完成，正在更新快照...")

                from app.services.snapshot_updater import update_stock_snapshots
                snapshot_count = update_stock_snapshots(session, progress_callback=self.progress_callback)

                message = f"任务全部完成。已同步 {count} 只股票，更新 {snapshot_count} 个快照。"
                self.finish_task(count, count, message)
                self._send_task_notification(user_id, TaskType.STOCK_LIST.value, task_name, True, message)
        except Exception as e:
            print(f"Background task failed: {e}")
            error_msg = f"任务执行失败: {str(e)}"
            self.error_task(error_msg)
            self._send_task_notification(user_id, TaskType.STOCK_LIST.value, task_name, False, error_msg)

    def run_sync_daily_task(self, symbols, start_date, end_date, sync_type, user_id: int = None):
        self.start_task(TaskType.DAILY.value, user_id=user_id)
        task_name = "日线数据同步"
        try:
            from app.services.data_sync import sync_daily
            with get_session() as session:
                count = sync_daily(session, symbols, start_date, end_date, sync_type, progress_callback=self.progress_callback)
                self.update_progress(len(symbols), len(symbols), f"日线数据同步完成，正在更新快照...")

                from app.services.snapshot_updater import update_stock_snapshots
                snapshot_count = update_stock_snapshots(session, progress_callback=self.progress_callback)

                message = f"任务全部完成。已同步 {count} 条记录，更新 {snapshot_count} 个快照。"
                self.finish_task(len(symbols), len(symbols), message)
                self._send_task_notification(user_id, TaskType.DAILY.value, task_name, True, message)
        except Exception as e:
            print(f"Background task failed: {e}")
            error_msg = f"任务执行失败: {str(e)}"
            self.error_task(error_msg)
            self._send_task_notification(user_id, TaskType.DAILY.value, task_name, False, error_msg)

    def run_snapshot_update_task(self, user_id: int = None):
        self.start_task(TaskType.SNAPSHOT.value, user_id=user_id, message="更新快照中...")
        task_name = "快照更新"
        try:
            from app.services.snapshot_updater import update_stock_snapshots
            with get_session() as session:
                count = update_stock_snapshots(session, progress_callback=self.progress_callback)
                message = f"快照更新完成，共更新 {count} 只股票"
                self.finish_task(count, count, message)
                self._send_task_notification(user_id, TaskType.SNAPSHOT.value, task_name, True, message)
        except Exception as e:
            print(f"Background task failed: {e}")
            error_msg = f"任务执行失败: {str(e)}"
            self.error_task(error_msg)
            self._send_task_notification(user_id, TaskType.SNAPSHOT.value, task_name, False, error_msg)

    def run_sync_index_list_task(self, user_id: int = None):
        self.start_task(TaskType.INDEX_LIST.value, user_id=user_id, message="正在初始化指数/ETF产品...")
        task_name = "指数/ETF产品同步"
        try:
            from app.services.index_sync import sync_index_list
            with get_session() as session:
                count = sync_index_list(session, progress_callback=self.progress_callback)
                message = f"指数/ETF产品初始化完成，共 {count} 个"
                self.finish_task(count, count, message)
                self._send_task_notification(user_id, TaskType.INDEX_LIST.value, task_name, True, message)
        except Exception as e:
            print(f"Background task failed: {e}")
            error_msg = f"任务执行失败: {str(e)}"
            self.error_task(error_msg)
            self._send_task_notification(user_id, TaskType.INDEX_LIST.value, task_name, False, error_msg)

    def run_sync_index_daily_task(self, codes, start_date, end_date, sync_type, user_id: int = None):
        self.start_task(TaskType.INDEX_DAILY.value, user_id=user_id)
        task_name = "指数/ETF日线同步"
        try:
            from app.services.index_sync import sync_index_daily
            with get_session() as session:
                count = sync_index_daily(session, codes, start_date, end_date, sync_type, progress_callback=self.progress_callback)
                message = f"指数/ETF日线同步完成，共 {count} 条记录"
                self.finish_task(count, max(count, 1), message)
                self._send_task_notification(user_id, TaskType.INDEX_DAILY.value, task_name, True, message)
        except Exception as e:
            print(f"Background task failed: {e}")
            error_msg = f"任务执行失败: {str(e)}"
            self.error_task(error_msg)
            self._send_task_notification(user_id, TaskType.INDEX_DAILY.value, task_name, False, error_msg)


task_manager = TaskManager()
