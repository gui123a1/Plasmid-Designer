"""共享 Pydantic 模型 — 从 main.py 提取"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime


# ==================== 枚举 ====================

class SequenceType(str, Enum):
    AMINO_ACID = "amino_acid"
    DNA = "dna"


class CloningMethod(str, Enum):
    GIBSON = "gibson"
    GOLDEN_GATE = "golden_gate"
    RESTRICTION = "restriction"
    GENE_SYNTHESIS = "gene_synthesis"


class DesignStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== 设计请求/响应 ====================

class DesignRequest(BaseModel):
    """设计请求"""
    sequence: str = Field(..., description="输入序列（氨基酸或DNA）")
    sequence_type: SequenceType = Field(default=SequenceType.AMINO_ACID, description="序列类型")
    sequence_name: str = Field(default="insert", description="序列名称")

    # 载体选择
    vector_id: str = Field(default="pET-28a", description="目标载体ID")

    # 克隆方法
    cloning_method: CloningMethod = Field(default=CloningMethod.GIBSON, description="克隆方法")

    # 密码子优化参数
    optimize_codons: bool = Field(default=True, description="是否进行密码子优化")
    target_species: str = Field(default="ecoli", description="目标物种")
    gc_min: float = Field(default=40.0, ge=20, le=50)
    gc_max: float = Field(default=60.0, ge=50, le=80)

    # 克隆参数
    homology_arm: int = Field(default=20, ge=15, le=40, description="Gibson同源臂长度")
    enzyme: str = Field(default="BsaI", description="Golden Gate酶")

    # 全基因合成参数
    oligo_length: int = Field(default=60, ge=40, le=100, description="寡核苷酸长度(bp)")
    overlap_length: int = Field(default=20, ge=10, le=30, description="重叠区域长度(bp)")
    # 输出选项
    include_report: bool = Field(default=True, description="生成设计报告")
    protocol_language: str = Field(default="zh", description="实验方案语言: zh=中文, en=英文")


class PrimerInfo(BaseModel):
    """引物信息"""
    name: str
    sequence: str
    full_sequence: str
    tm: float
    gc_content: float
    length: int
    overhang: Optional[str] = None
    notes: Optional[str] = None


class DesignResult(BaseModel):
    """设计结果"""
    design_id: str
    status: DesignStatus

    # 序列信息
    input_sequence: str
    optimized_sequence: Optional[str] = None

    # 优化指标
    cai: Optional[float] = None
    gc_content: Optional[float] = None

    # 载体信息
    vector_id: str
    vector_name: str = ""
    final_length: Optional[int] = None

    # 引物
    primers: List[PrimerInfo] = []

    # 克隆信息
    cloning_method: CloningMethod
    clone_protocol: Optional[str] = None

    # 验证结果
    validation_passed: bool = False
    warnings: List[str] = []
    errors: List[str] = []

    # 时间戳
    created_at: datetime
    completed_at: Optional[datetime] = None


# ==================== 载体信息 ====================

class VectorInfo(BaseModel):
    """载体信息"""
    id: str
    name: str
    source: str
    vector_type: str
    host: List[str]
    antibiotic_resistance: List[str]
    copy_number: str
    description: str
    features: List[Dict]
    mcs_enzymes: List[str]


# ==================== 批量设计 ====================

class BatchDesignRequest(BaseModel):
    """批量设计请求"""
    sequences: List[str] = Field(..., min_length=1, max_length=100)
    sequence_names: Optional[List[str]] = None
    sequence_type: SequenceType = SequenceType.AMINO_ACID
    vector_id: str = "pET-28a"
    cloning_method: CloningMethod = CloningMethod.GIBSON
    # 公共参数
    optimize_codons: bool = True
    target_species: str = "ecoli"
    gc_min: float = 40.0
    gc_max: float = 60.0
    homology_arm: int = 20
    enzyme: str = "BsaI"
    oligo_length: int = 60
    overlap_length: int = 20


class BatchDesignStatus(BaseModel):
    """批量设计状态"""
    batch_id: str
    total: int
    completed: int
    failed: int
    status: str  # pending, running, completed
    results: List[str] = []  # design_ids
    errors: List[Dict] = []


class BatchProgressResponse(BaseModel):
    """批量设计进度响应"""
    batch_id: str
    total: int
    completed: int
    failed: int
    pending: int
    status: str
    progress_percent: float
    results: List[Dict] = []
    errors: List[Dict] = []


# ==================== 载体管理 ====================

class VectorUpdateRequest(BaseModel):
    """载体更新请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    vector_type: Optional[str] = None
    host: Optional[List[str]] = None
    antibiotic_resistance: Optional[List[str]] = None
    copy_number: Optional[str] = None


class VectorPreviewResponse(BaseModel):
    """载体预览响应"""
    id: str
    name: str
    source: str
    length: int
    description: str
    gc_content: float
    features_count: int
    warnings: List[str] = []


class BatchImportRequest(BaseModel):
    """批量导入请求"""
    ncbi_ids: List[str] = []
    file_paths: List[str] = []


# ==================== 质粒图谱 ====================

class PlasmidMapData(BaseModel):
    """质粒图谱数据"""
    name: str
    length: int
    sequence: Optional[str] = None
    features: List[Dict] = []
