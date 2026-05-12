"""批量设计路由 — 从 main.py 提取"""

import uuid
import io
import zipfile
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

from app.config import settings, BACKEND_DIR
from app.routes.models import (
    BatchDesignRequest, BatchDesignStatus, BatchProgressResponse,
    DesignResult, PrimerInfo, DesignStatus, SequenceType, CloningMethod
)
from app.routes.design_routes import (
    designs_db, generate_genbank_content, generate_primer_tsv
)

router = APIRouter(prefix="/api/design/batch", tags=["batch"])

# 批量任务内存存储
batch_jobs: Dict[str, BatchDesignStatus] = {}


# ==================== 路由 ====================

@router.post("", response_model=Dict)
async def create_batch_design(
    request: BatchDesignRequest,
    background_tasks: BackgroundTasks
):
    """
    创建批量设计任务

    - 支持 1-100 个序列
    - 返回 batch_id 用于查询进度
    """
    batch_id = f"batch_{uuid.uuid4().hex[:12]}"

    # 处理名称
    names = request.sequence_names or [f"sequence_{i+1}" for i in range(len(request.sequences))]

    # 创建批量任务记录
    batch_jobs[batch_id] = BatchDesignStatus(
        batch_id=batch_id,
        total=len(request.sequences),
        completed=0,
        failed=0,
        status="pending",
        results=[],
        errors=[]
    )

    # 后台执行批量任务
    background_tasks.add_task(
        run_batch_design_task,
        batch_id,
        request,
        names
    )

    return {
        "batch_id": batch_id,
        "total": len(request.sequences),
        "message": "批量设计任务已提交"
    }


@router.get("/{batch_id}", response_model=BatchProgressResponse)
async def get_batch_progress(batch_id: str):
    """查询批量设计进度"""
    if batch_id not in batch_jobs:
        raise HTTPException(status_code=404, detail="Batch job not found")

    job = batch_jobs[batch_id]

    # 获取已完成任务的详细信息
    completed_results = []
    for design_id in job.results:
        if design_id in designs_db:
            result = designs_db[design_id]
            completed_results.append({
                "design_id": design_id,
                "status": result.status.value,
                "cai": result.cai,
                "gc_content": result.gc_content,
                "vector_name": result.vector_name
            })

    return BatchProgressResponse(
        batch_id=batch_id,
        total=job.total,
        completed=job.completed,
        failed=job.failed,
        pending=job.total - job.completed - job.failed,
        status=job.status,
        progress_percent=(job.completed + job.failed) / job.total * 100,
        results=completed_results,
        errors=job.errors
    )


@router.get("/{batch_id}/download")
async def download_batch_results(batch_id: str):
    """下载批量设计结果（ZIP 压缩包）"""
    if batch_id not in batch_jobs:
        raise HTTPException(status_code=404, detail="Batch job not found")

    job = batch_jobs[batch_id]
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Batch job not completed")

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for design_id in job.results:
            if design_id in designs_db:
                result = designs_db[design_id]
                # 添加 GenBank 文件
                gb_content = generate_genbank_content(result)
                zf.writestr(f"{design_id}.gb", gb_content)

                # 添加引物文件
                primer_content = generate_primer_tsv(result.primers)
                zf.writestr(f"{design_id}_primers.tsv", primer_content)

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={batch_id}_results.zip"}
    )


@router.get("/{batch_id}/report")
async def get_batch_report(batch_id: str):
    """获取批量设计汇总报告"""
    if batch_id not in batch_jobs:
        raise HTTPException(status_code=404, detail="Batch job not found")

    job = batch_jobs[batch_id]

    # 汇总统计
    report = {
        "batch_id": batch_id,
        "summary": {
            "total": job.total,
            "completed": job.completed,
            "failed": job.failed,
            "success_rate": job.completed / job.total * 100 if job.total > 0 else 0
        },
        "sequences": []
    }

    for design_id in job.results:
        if design_id in designs_db:
            result = designs_db[design_id]
            report["sequences"].append({
                "design_id": design_id,
                "input_length": len(result.input_sequence),
                "cai": result.cai,
                "gc_content": result.gc_content,
                "final_length": result.final_length,
                "primer_count": len(result.primers),
                "validation_passed": result.validation_passed
            })

    return report


# ==================== 后台任务 ====================

def run_batch_design_task(
    batch_id: str,
    request: BatchDesignRequest,
    names: List[str]
):
    """后台执行批量设计任务"""
    from core.codon_optimizer import CodonOptimizer
    from core.primer_designer import PrimerDesigner
    from core.clone_strategy import generate_cloning_strategy, CloningMethod as CM
    from core.sequence_validator import SequenceValidator
    from core.vector_library import VectorLibrary

    batch_jobs[batch_id].status = "running"

    for i, sequence in enumerate(request.sequences):
        try:
            design_id = f"design_{uuid.uuid4().hex[:12]}"
            sequence_name = names[i] if i < len(names) else f"sequence_{i+1}"

            # 创建设计记录
            result = DesignResult(
                design_id=design_id,
                status=DesignStatus.RUNNING,
                input_sequence=sequence,
                vector_id=request.vector_id,
                cloning_method=request.cloning_method,
                created_at=datetime.now()
            )
            designs_db[design_id] = result

            # 处理序列
            seq = sequence.upper().replace('\n', '').replace(' ', '')

            if request.sequence_type == SequenceType.DNA:
                optimized_dna = seq
            else:
                if request.optimize_codons:
                    optimizer = CodonOptimizer(species=request.target_species)
                    opt_result = optimizer.optimize(seq, gc_target=(request.gc_min / 100, request.gc_max / 100))
                    optimized_dna = opt_result.dna_sequence
                    result.cai = opt_result.cai
                    result.gc_content = opt_result.gc_content
                else:
                    optimizer = CodonOptimizer(species=request.target_species)
                    optimized_dna = optimizer.translate_back(seq)

            result.optimized_sequence = optimized_dna

            # 验证
            validator = SequenceValidator()
            val_result = validator.validate(optimized_dna, sequence_type="dna")
            result.validation_passed = val_result.is_valid

            # 设计引物
            designer = PrimerDesigner()
            if request.cloning_method == CloningMethod.GIBSON:
                pair, _ = designer.design_gibson_primers(
                    optimized_dna, "N" * 5000, 100,
                    homology_arm=request.homology_arm,
                    primer_name=sequence_name
                )
            elif request.cloning_method == CloningMethod.GOLDEN_GATE:
                pair = designer.design_golden_gate_primers(
                    optimized_dna,
                    enzyme_name=request.enzyme,
                    overhang_seq_5="AATG",
                    overhang_seq_3="GCTT",
                    primer_name=sequence_name
                )
            elif request.cloning_method == CloningMethod.GENE_SYNTHESIS:
                oligos = designer.design_synthesis_oligos(
                    optimized_dna,
                    oligo_length=request.oligo_length,
                    overlap_length=request.overlap_length,
                    primer_name=sequence_name
                )

                result.primers = [
                    PrimerInfo(
                        name=oligo.name,
                        sequence=oligo.sequence,
                        full_sequence=oligo.full_sequence if oligo.full_sequence else oligo.sequence,
                        tm=oligo.tm,
                        gc_content=oligo.gc_content,
                        length=oligo.length,
                        notes=oligo.notes
                    )
                    for oligo in oligos
                ]

            else:
                pair = designer.design_pcr_primers(optimized_dna, primer_name=sequence_name)

            # 对于非基因合成方法，设置引物对
            if request.cloning_method != CloningMethod.GENE_SYNTHESIS:
                result.primers = [
                    PrimerInfo(
                        name=pair.forward.name,
                        sequence=pair.forward.sequence,
                        full_sequence=pair.forward.full_sequence,
                        tm=pair.forward.tm,
                        gc_content=pair.forward.gc_content,
                        length=pair.forward.length
                    ),
                    PrimerInfo(
                        name=pair.reverse.name,
                        sequence=pair.reverse.sequence,
                        full_sequence=pair.reverse.full_sequence,
                        tm=pair.reverse.tm,
                        gc_content=pair.reverse.gc_content,
                        length=pair.reverse.length
                    )
                ]

            result.final_length = len(optimized_dna)
            result.status = DesignStatus.COMPLETED
            result.completed_at = datetime.now()

            batch_jobs[batch_id].results.append(design_id)
            batch_jobs[batch_id].completed += 1

        except Exception as e:
            batch_jobs[batch_id].errors.append({
                "index": i,
                "sequence_name": names[i] if i < len(names) else f"sequence_{i+1}",
                "error": str(e)
            })
            batch_jobs[batch_id].failed += 1

    batch_jobs[batch_id].status = "completed"
