"""设计任务路由 — 从 main.py 提取"""

import uuid
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse

from app.config import settings, BACKEND_DIR
from app.routes.models import (
    DesignRequest, DesignResult, PrimerInfo,
    DesignStatus, SequenceType, CloningMethod, PlasmidMapData
)

router = APIRouter(prefix="/api/design", tags=["design"])

# 内存存储引用 — 后续替换为存储层
designs_db: Dict[str, DesignResult] = {}


# ==================== 路由 ====================

@router.post("", response_model=Dict)
async def create_design(
    request: DesignRequest,
    background_tasks: BackgroundTasks
):
    """
    创建新的设计任务

    Returns:
    {design_id: str, status: str}
    """
    # 生成设计ID
    design_id = f"design_{uuid.uuid4().hex[:12]}"

    # 创建初始记录
    result = DesignResult(
        design_id=design_id,
        status=DesignStatus.PENDING,
        input_sequence=request.sequence,
        vector_id=request.vector_id,
        cloning_method=request.cloning_method,
        created_at=datetime.now()
    )
    designs_db[design_id] = result

    # 后台执行设计任务
    background_tasks.add_task(
        run_design_task,
        design_id,
        request
    )

    return {
        "design_id": design_id,
        "status": "pending",
        "message": "设计任务已提交，请轮询查询结果"
    }


@router.get("/{design_id}", response_model=DesignResult)
async def get_design(design_id: str):
    """查询设计任务结果"""
    if design_id not in designs_db:
        raise HTTPException(status_code=404, detail="Design not found")
    return designs_db[design_id]


@router.get("/{design_id}/download/genbank")
async def download_genbank(design_id: str):
    """下载 GenBank 格式文件"""
    if design_id not in designs_db:
        raise HTTPException(status_code=404, detail="Design not found")

    result = designs_db[design_id]
    if result.status != DesignStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Design not completed")

    genbank_content = generate_genbank_content(result)

    return PlainTextResponse(
        content=genbank_content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename={design_id}.gb"
        }
    )


@router.get("/{design_id}/download/primers")
async def download_primers(design_id: str):
    """下载引物订单表 (TSV格式)"""
    if design_id not in designs_db:
        raise HTTPException(status_code=404, detail="Design not found")

    result = designs_db[design_id]
    if result.status != DesignStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Design not completed")

    tsv_content = generate_primer_tsv(result.primers)

    return PlainTextResponse(
        content=tsv_content,
        media_type="text/tab-separated-values",
        headers={
            "Content-Disposition": f"attachment; filename={design_id}_primers.tsv"
        }
    )


@router.get("/{design_id}/map", response_model=PlasmidMapData)
async def get_design_map_data(design_id: str):
    """获取设计结果的图谱数据"""
    if design_id not in designs_db:
        raise HTTPException(status_code=404, detail="Design not found")

    result = designs_db[design_id]

    if result.status != DesignStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Design not completed")

    features = [
        {
            "name": "Insert",
            "type": "CDS",
            "start": 1,
            "end": len(result.optimized_sequence or ""),
            "strand": "+",
            "description": f"Optimized insert ({result.input_sequence[:30]}...)"
        }
    ]

    return PlasmidMapData(
        name=result.vector_name or "Construct",
        length=result.final_length or 0,
        sequence=result.optimized_sequence,
        features=features
    )


# ==================== 后台任务 ====================

def run_design_task(design_id: str, request: DesignRequest):
    """后台执行设计任务"""
    from core.codon_optimizer import CodonOptimizer
    from core.primer_designer import PrimerDesigner
    from core.clone_strategy import generate_cloning_strategy, CloningMethod as CM
    from core.sequence_validator import SequenceValidator
    from core.vector_library import VectorLibrary

    try:
        # 更新状态
        designs_db[design_id].status = DesignStatus.RUNNING

        # 1. 处理输入序列
        sequence = request.sequence.upper().replace('\n', '').replace(' ', '')

        if request.sequence_type == SequenceType.DNA:
            optimized_dna = sequence
        else:
            if request.optimize_codons:
                optimizer = CodonOptimizer(species=request.target_species)
                result = optimizer.optimize(
                    sequence,
                    gc_target=(request.gc_min / 100, request.gc_max / 100)
                )
                optimized_dna = result.dna_sequence
                designs_db[design_id].cai = result.cai
                designs_db[design_id].gc_content = result.gc_content
                designs_db[design_id].warnings.extend(result.warnings)
            else:
                optimizer = CodonOptimizer(species=request.target_species)
                result = optimizer.optimize(sequence)
                optimized_dna = result.dna_sequence

        designs_db[design_id].optimized_sequence = optimized_dna

        # 2. 验证序列
        validator = SequenceValidator()
        val_result = validator.validate(optimized_dna, sequence_type="dna")
        designs_db[design_id].validation_passed = val_result.is_valid
        designs_db[design_id].errors.extend(val_result.errors)
        designs_db[design_id].warnings.extend(val_result.warnings)

        # 3. 加载载体信息
        library = VectorLibrary()
        library.load_from_directory(settings.VECTORS_DIR)
        vector = library.get_vector(request.vector_id)

        if vector:
            designs_db[design_id].vector_name = vector.name

        # 4. 设计引物
        designer = PrimerDesigner()

        if request.cloning_method == CloningMethod.GIBSON:
            insert_pos = vector.mcs.start if vector and vector.mcs else 100
            pair, _ = designer.design_gibson_primers(
                optimized_dna,
                vector.sequence if vector else "N" * 5000,
                insert_pos,
                homology_arm=request.homology_arm,
                primer_name=f"{request.sequence_name}"
            )

            primers = [
                PrimerInfo(
                    name=pair.forward.name,
                    sequence=pair.forward.sequence,
                    full_sequence=pair.forward.full_sequence,
                    tm=pair.forward.tm,
                    gc_content=pair.forward.gc_content,
                    length=pair.forward.length,
                    overhang=pair.forward.overhang,
                    notes=pair.forward.notes
                ),
                PrimerInfo(
                    name=pair.reverse.name,
                    sequence=pair.reverse.sequence,
                    full_sequence=pair.reverse.full_sequence,
                    tm=pair.reverse.tm,
                    gc_content=pair.reverse.gc_content,
                    length=pair.reverse.length,
                    overhang=pair.reverse.overhang,
                    notes=pair.reverse.notes
                )
            ]

        elif request.cloning_method == CloningMethod.GOLDEN_GATE:
            pair = designer.design_golden_gate_primers(
                optimized_dna,
                enzyme_name=request.enzyme,
                overhang_seq_5="AATG",
                overhang_seq_3="GCTT",
                primer_name=f"{request.sequence_name}"
            )

            primers = [
                PrimerInfo(
                    name=pair.forward.name,
                    sequence=pair.forward.sequence,
                    full_sequence=pair.forward.full_sequence,
                    tm=pair.forward.tm,
                    gc_content=pair.forward.gc_content,
                    length=pair.forward.length,
                    overhang=pair.forward.overhang,
                    notes=pair.forward.notes
                ),
                PrimerInfo(
                    name=pair.reverse.name,
                    sequence=pair.reverse.sequence,
                    full_sequence=pair.reverse.full_sequence,
                    tm=pair.reverse.tm,
                    gc_content=pair.reverse.gc_content,
                    length=pair.reverse.length,
                    overhang=pair.reverse.overhang,
                    notes=pair.reverse.notes
                )
            ]

        elif request.cloning_method == CloningMethod.GENE_SYNTHESIS:
            oligos = designer.design_synthesis_oligos(
                optimized_dna,
                oligo_length=request.oligo_length,
                overlap_length=request.overlap_length,
                primer_name=request.sequence_name
            )

            primers = [
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
            # 默认PCR引物（限制性酶切等）
            pair = designer.design_pcr_primers(optimized_dna, primer_name=request.sequence_name)
            primers = [
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

        designs_db[design_id].primers = primers

        # 5. 生成克隆方案
        clone_method_map = {
            CloningMethod.GIBSON: CM.GIBSON,
            CloningMethod.GOLDEN_GATE: CM.GOLDEN_GATE,
            CloningMethod.RESTRICTION: CM.RESTRICTION,
            CloningMethod.GENE_SYNTHESIS: CM.GENE_SYNTHESIS,
        }

        strategy = generate_cloning_strategy(
            method=clone_method_map[request.cloning_method],
            insert_seq=optimized_dna,
            insert_name=request.sequence_name,
            vector_seq=vector.sequence if vector else "",
            vector_name=vector.name if vector else request.vector_id
        )

        designs_db[design_id].clone_protocol = strategy.to_protocol(language=request.protocol_language)

        # 6. 计算最终长度
        designs_db[design_id].final_length = len(optimized_dna) + (vector.length if vector else 0)

        # 完成
        designs_db[design_id].status = DesignStatus.COMPLETED
        designs_db[design_id].completed_at = datetime.now()

    except Exception as e:
        designs_db[design_id].status = DesignStatus.FAILED
        designs_db[design_id].errors.append(str(e))


# ==================== 辅助函数 ====================

def generate_genbank_content(result: DesignResult) -> str:
    """生成 GenBank 文件内容"""
    lines = []

    locus_name = result.design_id[:16].replace('-', '_')
    length = result.final_length or len(result.optimized_sequence or "")
    date_str = datetime.now().strftime("%d-%b-%Y").upper()

    lines.append(f"LOCUS {locus_name:<16} {length} bp DNA circular SYN {date_str}")
    lines.append(f"DEFINITION {result.vector_name} with {result.design_id}")
    lines.append(f"ACCESSION {result.design_id}")
    lines.append(f"VERSION {result.design_id}.1")
    lines.append(f"SOURCE synthetic construct")
    lines.append(f" ORGANISM synthetic construct")
    lines.append(f" Artificial sequence.")

    lines.append(f"FEATURES Location/Qualifiers")
    lines.append(f" source 1..{length}")
    lines.append(f' /organism="synthetic construct"')

    if result.optimized_sequence:
        lines.append(f" CDS 1..{len(result.optimized_sequence)}")
        lines.append(f' /label="insert"')

    lines.append(f"ORIGIN")

    seq = (result.optimized_sequence or "").upper()
    for i in range(0, len(seq), 60):
        chunk = seq[i:i + 60]
        groups = ' '.join([chunk[j:j + 10] for j in range(0, len(chunk), 10)])
        lines.append(f"{i + 1:>9} {groups}")

    lines.append("//")

    return '\n'.join(lines)


def generate_primer_tsv(primers: List[PrimerInfo]) -> str:
    """生成引物 TSV 文件"""
    lines = ["Name\tSequence\tFull Sequence\tLength\tTm\tGC%\tNotes"]

    for p in primers:
        lines.append(
            f"{p.name}\t{p.sequence}\t{p.full_sequence}\t"
            f"{p.length}\t{p.tm:.1f}\t{p.gc_content:.1f}\t{p.notes or ''}"
        )

    return '\n'.join(lines)
