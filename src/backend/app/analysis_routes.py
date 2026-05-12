"""
序列分析和导出 API 路由
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse, StreamingResponse
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
import io

from core.sequence_analysis import (
    SequenceAnalyzer,
    RestrictionSiteAnalyzer,
    ORFPredictor,
    GCAnalyzer
)
from core.export_formats import (
    ExportManager,
    ExportData,
    SequenceFeature,
    create_export_data_from_design,
    create_export_data_from_vector
)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


# ==================== 请求模型 ====================

class SequenceAnalysisRequest(BaseModel):
    """序列分析请求"""
    sequence: str = Field(..., description="DNA 序列")
    check_restriction: bool = Field(default=True, description="是否检测限制性位点")
    check_orf: bool = Field(default=True, description="是否预测 ORF")
    check_gc: bool = Field(default=True, description="是否分析 GC 含量")
    enzymes: Optional[List[str]] = Field(default=None, description="要检测的酶列表")


class ExportRequest(BaseModel):
    """导出请求"""
    name: str = Field(..., description="序列名称")
    sequence: str = Field(..., description="DNA 序列")
    features: List[Dict] = Field(default=[], description="序列特征")
    description: str = Field(default="", description="描述")
    is_circular: bool = Field(default=True, description="是否环状")
    format: str = Field(default="genbank", description="导出格式")


# ==================== 序列分析 API ====================

@router.post("/analyze")
async def analyze_sequence(request: SequenceAnalysisRequest) -> Dict:
    """
    综合序列分析
    
    包括：
    - 限制性酶切位点
    - ORF 预测
    - GC 含量分析
    """
    analyzer = SequenceAnalyzer()
    result = analyzer.analyze(
        sequence=request.sequence,
        check_restriction=request.check_restriction,
        check_orf=request.check_orf,
        check_gc=request.check_gc,
        enzymes=request.enzymes
    )
    
    return {
        "sequence_length": result.sequence_length,
        "gc_content": result.gc_content,
        "coding_potential": result.coding_potential,
        "restriction_sites": [
            {
                "enzyme": site.enzyme,
                "site": site.site,
                "position": site.recognition_start,
                "strand": site.strand,
                "overhang": site.overhang
            }
            for site in result.restriction_sites
        ],
        "orfs": [
            {
                "start": orf.start,
                "end": orf.end,
                "strand": orf.strand,
                "length": orf.length,
                "frame": orf.frame,
                "protein_length": len(orf.protein_sequence),
                "start_codon": orf.start_codon,
                "stop_codon": orf.stop_codon,
                "gc_content": orf.gc_content,
                "is_complete": orf.is_complete
            }
            for orf in result.orfs[:10]  # 返回前 10 个最长 ORF
        ],
        "gc_distribution": [
            {
                "start": r.start,
                "end": r.end,
                "gc_content": r.gc_content,
                "is_extreme": r.is_extreme
            }
            for r in result.gc_distribution[:50]  # 限制返回数量
        ],
        "warnings": result.warnings
    }


@router.post("/restriction-sites")
async def find_restriction_sites(
    sequence: str,
    enzymes: Optional[List[str]] = Query(None)
) -> Dict:
    """
    查找限制性酶切位点
    
    Args:
        sequence: DNA 序列
        enzymes: 要检测的酶列表（可选，默认检测所有常用酶）
    
    Returns:
        发现的限制性位点列表
    """
    analyzer = RestrictionSiteAnalyzer()
    sites = analyzer.find_sites(sequence, enzymes)
    
    return {
        "total": len(sites),
        "sites": [
            {
                "enzyme": site.enzyme,
                "recognition_sequence": site.site,
                "position": site.recognition_start,
                "end": site.recognition_end,
                "cut_position": site.cut_position,
                "strand": site.strand,
                "overhang_type": site.overhang
            }
            for site in sites
        ],
        "unique_sites": list(analyzer.find_unique_sites(sequence).keys())
    }


@router.post("/orfs")
async def find_orfs(
    sequence: str,
    min_length: int = Query(150, description="最小 ORF 长度")
) -> Dict:
    """
    预测开放阅读框 (ORF)
    
    Args:
        sequence: DNA 序列
        min_length: 最小 ORF 长度（碱基数）
    
    Returns:
        ORF 列表（按长度排序）
    """
    predictor = ORFPredictor(min_length=min_length)
    orfs = predictor.find_orfs(sequence)
    
    return {
        "total": len(orfs),
        "orfs": [
            {
                "start": orf.start,
                "end": orf.end,
                "strand": orf.strand,
                "length": orf.length,
                "frame": orf.frame,
                "protein_sequence": orf.protein_sequence,
                "start_codon": orf.start_codon,
                "stop_codon": orf.stop_codon,
                "gc_content": round(orf.gc_content, 2),
                "is_complete": orf.is_complete
            }
            for orf in orfs
        ]
    }


@router.post("/gc-analysis")
async def analyze_gc(
    sequence: str,
    window_size: int = Query(100, description="窗口大小"),
    step_size: int = Query(50, description="步长")
) -> Dict:
    """
    GC 含量分析
    
    Args:
        sequence: DNA 序列
        window_size: 滑动窗口大小
        step_size: 步长
    
    Returns:
        GC 含量分布
    """
    analyzer = GCAnalyzer(window_size=window_size, step_size=step_size)
    total_gc, regions = analyzer.analyze(sequence)
    
    extremes = [r for r in regions if r.is_extreme]
    
    return {
        "total_gc_content": round(total_gc, 2),
        "total_regions": len(regions),
        "extreme_regions": len(extremes),
        "distribution": [
            {
                "start": r.start,
                "end": r.end,
                "gc_content": round(r.gc_content, 2),
                "is_extreme": r.is_extreme
            }
            for r in regions
        ],
        "extremes": [
            {
                "start": r.start,
                "end": r.end,
                "gc_content": round(r.gc_content, 2)
            }
            for r in extremes
        ]
    }


# ==================== 导出 API ====================

@router.get("/export/formats")
async def get_export_formats() -> List[Dict]:
    """获取支持的导出格式列表"""
    return ExportManager.get_supported_formats()


@router.post("/export")
async def export_sequence(request: ExportRequest):
    """
    导出序列到指定格式
    
    支持格式：
    - genbank: GenBank 格式 (.gb)
    - snapgene: SnapGene 格式 (.dna)
    - benchling: Benchling JSON 格式
    - fasta: FASTA 格式
    - sbol: SBOL 格式
    """
    # 构建导出数据
    features = [
        SequenceFeature(
            name=f.get("name", "feature"),
            feature_type=f.get("type", "misc_feature"),
            start=f.get("start", 1),
            end=f.get("end", 100),
            strand=f.get("strand", "+"),
            color=f.get("color", "#4A90D9"),
            description=f.get("description", "")
        )
        for f in request.features
    ]
    
    export_data = ExportData(
        name=request.name,
        sequence=request.sequence,
        features=features,
        description=request.description,
        is_circular=request.is_circular
    )
    
    try:
        content, mime_type = ExportManager.export(export_data, request.format)
        
        # 确定文件扩展名
        extensions = {
            "genbank": ".gb",
            "snapgene": ".dna",
            "benchling": ".json",
            "fasta": ".fasta",
            "sbol": ".json"
        }
        ext = extensions.get(request.format, ".txt")
        
        if isinstance(content, bytes):
            return StreamingResponse(
                io.BytesIO(content),
                media_type=mime_type,
                headers={
                    "Content-Disposition": f"attachment; filename={request.name}{ext}"
                }
            )
        else:
            return PlainTextResponse(
                content=content,
                media_type=mime_type,
                headers={
                    "Content-Disposition": f"attachment; filename={request.name}{ext}"
                }
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/export/all")
async def export_all_formats(request: ExportRequest):
    """
    导出所有格式为 ZIP 文件
    """
    features = [
        SequenceFeature(
            name=f.get("name", "feature"),
            feature_type=f.get("type", "misc_feature"),
            start=f.get("start", 1),
            end=f.get("end", 100),
            strand=f.get("strand", "+"),
            color=f.get("color", "#4A90D9"),
            description=f.get("description", "")
        )
        for f in request.features
    ]
    
    export_data = ExportData(
        name=request.name,
        sequence=request.sequence,
        features=features,
        description=request.description,
        is_circular=request.is_circular
    )
    
    zip_content = ExportManager.export_all(export_data)
    
    return StreamingResponse(
        io.BytesIO(zip_content),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={request.name}_exports.zip"
        }
    )


@router.get("/design/{design_id}/export")
async def export_design(design_id: str, format: str = "genbank"):
    """
    导出设计结果
    
    Args:
        design_id: 设计任务 ID
        format: 导出格式
    """
    # 这里需要从数据库获取设计结果
    # 简化实现，返回示例
    raise HTTPException(status_code=501, detail="请使用 /api/export 端点")


@router.get("/vector/{vector_id}/export")
async def export_vector(vector_id: str, format: str = "genbank"):
    """
    导出载体序列
    
    Args:
        vector_id: 载体 ID
        format: 导出格式
    """
    # 这里需要从数据库获取载体数据
    # 简化实现，返回示例
    raise HTTPException(status_code=501, detail="请使用 /api/export 端点")


# ==================== 克隆兼容性检查 ====================

@router.post("/compatibility")
async def check_cloning_compatibility(
    insert_sequence: str,
    vector_sequence: str,
    enzymes: List[str]
) -> Dict:
    """
    检查克隆兼容性
    
    Args:
        insert_sequence: 插入片段序列
        vector_sequence: 载体序列
        enzymes: 计划使用的酶列表
    
    Returns:
        兼容性分析结果
    """
    analyzer = SequenceAnalyzer()
    result = analyzer.check_cloning_compatibility(
        insert_sequence,
        vector_sequence,
        enzymes
    )
    
    return result


@router.get("/enzymes")
async def list_enzymes() -> Dict:
    """获取支持的酶列表"""
    from core.sequence_analysis import RESTRICTION_ENZYMES
    
    enzymes_info = {}
    for name, (seq, cut, overhang) in RESTRICTION_ENZYMES.items():
        overhang_names = {'5': "5' 粘性末端", '3': "3' 粘性末端", 'b': '平末端'}
        enzymes_info[name] = {
            "recognition_sequence": seq,
            "cut_type": overhang_names.get(overhang, '未知'),
            "is_type_iis": name in ['BsaI', 'BsmBI', 'BbsI']
        }
    
    return {
        "total": len(enzymes_info),
        "enzymes": enzymes_info
    }
