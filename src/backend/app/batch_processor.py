"""
批量设计并发处理模块
使用 asyncio 并行处理多个设计任务
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Callable
from datetime import datetime
import logging

logger = logging.getLogger("plasmid_designer.batch")


class BatchProcessor:
    """批量任务并发处理器"""
    
    def __init__(
        self,
        max_workers: int = 4,
        chunk_size: int = 10,
        progress_callback: Callable = None
    ):
        """
        初始化批量处理器
        
        Args:
            max_workers: 最大并发工作线程数
            chunk_size: 分块大小（用于大批量任务）
            progress_callback: 进度回调函数
        """
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.progress_callback = progress_callback
    
    async def process_batch(
        self,
        items: List[Any],
        process_func: Callable,
        batch_id: str = None
    ) -> Dict[str, Any]:
        """
        并发处理批量任务
        
        Args:
            items: 待处理项列表
            process_func: 单项处理函数
            batch_id: 批次 ID
        
        Returns:
            处理结果统计
        """
        batch_id = batch_id or f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        total = len(items)
        completed = 0
        failed = 0
        results = []
        errors = []
        
        logger.info(
            f"Batch processing started: {batch_id}",
            extra={"batch_id": batch_id, "total": total}
        )
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 创建任务
            loop = asyncio.get_event_loop()
            tasks = []
            
            for i, item in enumerate(items):
                task = loop.run_in_executor(
                    executor,
                    self._wrap_process_func,
                    process_func,
                    item,
                    i
                )
                tasks.append(task)
            
            # 等待所有任务完成
            for coro in asyncio.as_completed(tasks):
                try:
                    result = await coro
                    completed += 1
                    results.append(result)
                    
                    # 进度回调
                    if self.progress_callback:
                        await self._call_progress_callback(
                            batch_id, total, completed, failed
                        )
                    
                except Exception as e:
                    failed += 1
                    errors.append({
                        "index": len(results) + len(errors),
                        "error": str(e)
                    })
                    
                    logger.error(
                        f"Batch item failed: {batch_id}",
                        extra={"batch_id": batch_id, "error": str(e)},
                        exc_info=True
                    )
        
        # 记录完成
        logger.info(
            f"Batch processing completed: {batch_id}",
            extra={
                "batch_id": batch_id,
                "total": total,
                "completed": completed,
                "failed": failed
            }
        )
        
        return {
            "batch_id": batch_id,
            "total": total,
            "completed": completed,
            "failed": failed,
            "results": results,
            "errors": errors
        }
    
    def _wrap_process_func(self, func: Callable, item: Any, index: int) -> Dict:
        """包装处理函数，添加异常处理"""
        try:
            result = func(item)
            return {
                "index": index,
                "success": True,
                "data": result
            }
        except Exception as e:
            return {
                "index": index,
                "success": False,
                "error": str(e)
            }
    
    async def _call_progress_callback(
        self,
        batch_id: str,
        total: int,
        completed: int,
        failed: int
    ):
        """调用进度回调"""
        if self.progress_callback:
            try:
                await self.progress_callback(batch_id, total, completed, failed)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")


class ChunkedBatchProcessor(BatchProcessor):
    """分块批量处理器（用于超大批次）"""
    
    async def process_batch_chunked(
        self,
        items: List[Any],
        process_func: Callable,
        batch_id: str = None
    ) -> Dict[str, Any]:
        """
        分块处理大批量任务
        
        将大列表分成多个小块，逐块处理，避免内存溢出
        """
        batch_id = batch_id or f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        total = len(items)
        all_results = []
        all_errors = []
        
        # 分块
        chunks = self._chunk_items(items)
        
        logger.info(
            f"Chunked batch processing started: {batch_id}",
            extra={
                "batch_id": batch_id,
                "total": total,
                "chunks": len(chunks)
            }
        )
        
        for chunk_idx, chunk in enumerate(chunks):
            logger.debug(
                f"Processing chunk {chunk_idx + 1}/{len(chunks)}",
                extra={"batch_id": batch_id, "chunk_size": len(chunk)}
            )
            
            result = await super().process_batch(
                chunk,
                process_func,
                f"{batch_id}_chunk_{chunk_idx}"
            )
            
            all_results.extend(result.get("results", []))
            all_errors.extend(result.get("errors", []))
        
        final_completed = len(all_results)
        final_failed = len(all_errors)
        
        logger.info(
            f"Chunked batch processing completed: {batch_id}",
            extra={
                "batch_id": batch_id,
                "total": total,
                "completed": final_completed,
                "failed": final_failed
            }
        )
        
        return {
            "batch_id": batch_id,
            "total": total,
            "completed": final_completed,
            "failed": final_failed,
            "results": all_results,
            "errors": all_errors
        }
    
    def _chunk_items(self, items: List[Any]) -> List[List[Any]]:
        """将列表分块"""
        chunks = []
        for i in range(0, len(items), self.chunk_size):
            chunks.append(items[i:i + self.chunk_size])
        return chunks


async def process_design_batch(
    sequences: List[str],
    design_func: Callable,
    max_workers: int = 4,
    progress_callback: Callable = None
) -> Dict[str, Any]:
    """
    便捷函数：批量处理设计任务
    
    Args:
        sequences: 序列列表
        design_func: 设计处理函数
        max_workers: 最大并发数
        progress_callback: 进度回调
    
    Returns:
        处理结果
    """
    processor = BatchProcessor(
        max_workers=max_workers,
        progress_callback=progress_callback
    )
    
    return await processor.process_batch(sequences, design_func)


# 使用示例
if __name__ == "__main__":
    import asyncio
    
    async def example():
        def process_item(item):
            import time
            time.sleep(0.5)  # 模拟处理
            return f"processed_{item}"
        
        processor = BatchProcessor(max_workers=4)
        items = list(range(10))
        
        result = await processor.process_batch(items, process_item)
        print(f"Completed: {result['completed']}/{result['total']}")
    
    asyncio.run(example())
