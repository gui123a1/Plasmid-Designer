"""
任务队列模块
持久化任务队列，支持任务优先级和重试
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum
import heapq
import logging
import json

logger = logging.getLogger("plasmid_designer.queue")


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class TaskPriority(int, Enum):
    """任务优先级"""
    LOW = 10
    NORMAL = 5
    HIGH = 1
    URGENT = 0


@dataclass(order=True)
class Task:
    """任务定义"""
    priority: int
    task_id: str = field(compare=False)
    task_type: str = field(compare=False)
    payload: Dict[str, Any] = field(compare=False)
    created_at: datetime = field(default_factory=datetime.utcnow, compare=False)
    started_at: Optional[datetime] = field(default=None, compare=False)
    completed_at: Optional[datetime] = field(default=None, compare=False)
    status: TaskStatus = field(default=TaskStatus.PENDING, compare=False)
    retry_count: int = field(default=0, compare=False)
    max_retries: int = field(default=3, compare=False)
    error: Optional[str] = field(default=None, compare=False)
    result: Optional[Any] = field(default=None, compare=False)


class TaskQueue:
    """持久化任务队列"""
    
    def __init__(self, max_size: int = 1000):
        self._queue: List[Task] = []
        self._tasks: Dict[str, Task] = {}
        self._max_size = max_size
        self._handlers: Dict[str, Callable] = {}
        self._lock = asyncio.Lock()
    
    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._handlers[task_type] = handler
        logger.info(f"Handler registered for task type: {task_type}")
    
    async def enqueue(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: int = TaskPriority.NORMAL,
        max_retries: int = 3
    ) -> Task:
        """添加任务到队列"""
        async with self._lock:
            if len(self._queue) >= self._max_size:
                raise RuntimeError("Task queue is full")
            
            task = Task(
                priority=priority,
                task_id=f"task_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{len(self._tasks)}",
                task_type=task_type,
                payload=payload,
                max_retries=max_retries,
                status=TaskStatus.QUEUED
            )
            
            heapq.heappush(self._queue, task)
            self._tasks[task.task_id] = task
            
            logger.info(
                f"Task enqueued: {task.task_id}",
                extra={"task_type": task_type, "priority": priority}
            )
            
            return task
    
    async def dequeue(self) -> Optional[Task]:
        """从队列取出任务"""
        async with self._lock:
            if not self._queue:
                return None
            
            task = heapq.heappop(self._queue)
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            
            logger.debug(f"Task dequeued: {task.task_id}")
            return task
    
    async def complete(self, task_id: str, result: Any = None):
        """标记任务完成"""
        async with self._lock:
            if task_id not in self._tasks:
                logger.warning(f"Task not found: {task_id}")
                return
            
            task = self._tasks[task_id]
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.result = result
            
            logger.info(
                f"Task completed: {task_id}",
                extra={
                    "duration_ms": (task.completed_at - task.started_at).total_seconds() * 1000
                    if task.started_at else 0
                }
            )
    
    async def fail(self, task_id: str, error: str):
        """标记任务失败"""
        async with self._lock:
            if task_id not in self._tasks:
                return
            
            task = self._tasks[task_id]
            
            if task.retry_count < task.max_retries:
                # 重试
                task.retry_count += 1
                task.status = TaskStatus.RETRYING
                task.error = error
                heapq.heappush(self._queue, task)
                
                logger.warning(
                    f"Task failed, retrying ({task.retry_count}/{task.max_retries}): {task_id}",
                    extra={"error": error}
                )
            else:
                # 最终失败
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.utcnow()
                task.error = error
                
                logger.error(
                    f"Task failed permanently: {task_id}",
                    extra={"error": error, "retries": task.retry_count}
                )
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务状态"""
        return self._tasks.get(task_id)
    
    async def get_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        async with self._lock:
            status_counts = {s.value: 0 for s in TaskStatus}
            for task in self._tasks.values():
                status_counts[task.status.value] += 1
            
            return {
                "queue_size": len(self._queue),
                "total_tasks": len(self._tasks),
                "status_counts": status_counts,
                "max_size": self._max_size
            }
    
    async def process_task(self, task: Task) -> Any:
        """处理单个任务"""
        handler = self._handlers.get(task.task_type)
        
        if not handler:
            raise ValueError(f"No handler for task type: {task.task_type}")
        
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(task.payload)
            else:
                result = handler(task.payload)
            
            await self.complete(task.task_id, result)
            return result
            
        except Exception as e:
            await self.fail(task.task_id, str(e))
            raise


class TaskWorker:
    """任务工作者"""
    
    def __init__(
        self,
        queue: TaskQueue,
        worker_id: str = "worker_1",
        poll_interval: float = 1.0
    ):
        self.queue = queue
        self.worker_id = worker_id
        self.poll_interval = poll_interval
        self._running = False
    
    async def start(self):
        """启动工作者"""
        self._running = True
        logger.info(f"Worker started: {self.worker_id}")
        
        while self._running:
            try:
                task = await self.queue.dequeue()
                
                if task:
                    logger.debug(
                        f"Worker {self.worker_id} processing: {task.task_id}"
                    )
                    await self.queue.process_task(task)
                else:
                    await asyncio.sleep(self.poll_interval)
                    
            except Exception as e:
                logger.error(
                    f"Worker error: {self.worker_id}",
                    exc_info=True,
                    extra={"error": str(e)}
                )
                await asyncio.sleep(self.poll_interval)
    
    async def stop(self):
        """停止工作者"""
        self._running = False
        logger.info(f"Worker stopped: {self.worker_id}")


class TaskManager:
    """任务管理器"""
    
    def __init__(self, num_workers: int = 2):
        self.queue = TaskQueue()
        self.workers = [
            TaskWorker(self.queue, f"worker_{i}")
            for i in range(num_workers)
        ]
        self._tasks: List[asyncio.Task] = []
    
    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self.queue.register_handler(task_type, handler)
    
    async def start(self):
        """启动所有工作者"""
        for worker in self.workers:
            self._tasks.append(asyncio.create_task(worker.start()))
        
        logger.info(f"Task manager started with {len(self.workers)} workers")
    
    async def stop(self):
        """停止所有工作者"""
        for worker in self.workers:
            await worker.stop()
        
        for task in self._tasks:
            task.cancel()
        
        logger.info("Task manager stopped")
    
    async def submit(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: int = TaskPriority.NORMAL
    ) -> Task:
        """提交任务"""
        return await self.queue.enqueue(task_type, payload, priority)
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return await self.queue.get_task(task_id)
    
    async def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return await self.queue.get_status()


# 全局任务管理器
task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """获取任务管理器"""
    global task_manager
    if task_manager is None:
        task_manager = TaskManager()
    return task_manager
