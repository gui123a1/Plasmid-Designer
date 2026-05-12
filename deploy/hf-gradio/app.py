# Plasmid Designer - HF Spaces 完整功能体验版
# 集成所有核心功能：设计、批量、分析、导出、载体库
# 不依赖数据库/Redis/Celery，纯内存 + 文件下载

import gradio as gr
import sys
import os
import tempfile
import zipfile
import io
import uuid
from datetime import datetime

# 添加后端核心路径
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, BACKEND_DIR)

from core.codon_optimizer import CodonOptimizer
from core.primer_designer import PrimerDesigner
from core.primer_designer import PrimerType
from core.vector_library import VectorLibrary
from core.clone_strategy import generate_cloning_strategy, CloningMethod
from core.sequence_validator import SequenceValidator
from core.sequence_analysis import (
    SequenceAnalyzer, RestrictionSiteAnalyzer, ORFPredictor, GCAnalyzer,
    RESTRICTION_ENZYMES
)
from core.export_formats import ExportManager, ExportData, SequenceFeature
from core.output_generator import (
    GenBankGenerator, PrimerOrderGenerator, DesignReportGenerator, PlasmidDesign
)

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
VECTORS_DIR = os.path.join(DATA_DIR, "vectors")
CODON_TABLES_DIR = os.path.join(DATA_DIR, "codon_tables")


# ==================== 工具函数 ====================

def get_available_vectors():
    library = VectorLibrary()
    library.load_from_directory(VECTORS_DIR)
    vectors = library.list_vectors()
    return [v.id for v in vectors] if vectors else ["pET-28a", "pcDNA3.1", "pGEX-4T-1"]


def get_available_species():
    species = []
    if os.path.isdir(CODON_TABLES_DIR):
        for f in os.listdir(CODON_TABLES_DIR):
            if f.endswith(".yaml"):
                name = f.replace(".yaml", "").lower()
                species.append(name)
    return species if species else ["ecoli", "human", "cho", "yeast"]


def _load_vector_sequence(vector_id: str) -> str:
    try:
        library = VectorLibrary()
        library.load_from_directory(VECTORS_DIR)
        vector = library.get_vector(vector_id)
        if vector and vector.sequence:
            return vector.sequence
    except Exception:
        pass
    return "N" * 5000


def _get_mcs_start(vector_id: str) -> int:
    try:
        library = VectorLibrary()
        library.load_from_directory(VECTORS_DIR)
        vector = library.get_vector(vector_id)
        if vector and vector.mcs:
            return vector.mcs.start
    except Exception:
        pass
    return 100


def _get_vector_obj(vector_id: str):
    try:
        library = VectorLibrary()
        library.load_from_directory(VECTORS_DIR)
        return library.get_vector(vector_id)
    except Exception:
        return None


# ==================== Tab 1: 单序列设计 ====================

def process_design(
    sequence, sequence_type, sequence_name, vector_id, cloning_method,
    optimize_codons, target_species, gc_min, gc_max, homology_arm, enzyme
):
    if not sequence or not sequence.strip():
        return "请输入序列", None, None, None

    try:
        sequence = sequence.upper().replace("\n", "").replace(" ", "").replace("\r", "")
        results = []

        # 1. 密码子优化
        if sequence_type == "氨基酸序列" and optimize_codons:
            optimizer = CodonOptimizer(species=target_species.lower())
            result = optimizer.optimize(sequence, gc_target=(gc_min / 100, gc_max / 100))
            optimized_seq = result.dna_sequence
            results.append("## 密码子优化结果\n")
            results.append(f"- CAI 值: {result.cai:.3f}")
            results.append(f"- GC 含量: {result.gc_content:.1f}%")
            results.append(f"- 优化后序列长度: {len(optimized_seq)} bp\n")
            if result.warnings:
                results.append("**警告:**")
                for w in result.warnings:
                    results.append(f"- {w}")
                results.append("")
        elif sequence_type == "氨基酸序列":
            optimizer = CodonOptimizer(species=target_species.lower())
            result = optimizer.optimize(sequence)
            optimized_seq = result.dna_sequence
            results.append("## 反向翻译结果\n")
            results.append(f"- 序列长度: {len(optimized_seq)} bp\n")
        else:
            optimized_seq = sequence
            results.append("## 序列信息\n")
            results.append(f"- 输入序列长度: {len(sequence)} bp\n")

        # 2. 引物设计
        primers_data = []
        if optimized_seq:
            designer = PrimerDesigner()
                if cloning_method == "Gibson Assembly":
                vector_seq = _load_vector_sequence(vector_id)
                insert_pos = _get_mcs_start(vector_id)
                pair, _ = designer.design_gibson_primers(
                    optimized_seq, vector_seq, insert_pos,
                    homology_arm=homology_arm, primer_name=sequence_name,
                )
            elif cloning_method == "Golden Gate":
                pair = designer.design_golden_gate_primers(
                    optimized_seq, enzyme_name=enzyme,
                    overhang_seq_5="AATG", overhang_seq_3="GCTT",
                    primer_name=sequence_name,
                )
            elif cloning_method == "全基因合成":
                oligos = designer.design_synthesis_oligos(
                    optimized_seq, primer_name=sequence_name,
                )
            else:
                pair = designer.design_pcr_primers(optimized_seq, primer_name=sequence_name)

            if cloning_method == "全基因合成":
                primers_data = [
                    {
                        "name": o.name, "sequence": o.sequence,
                        "full_sequence": o.full_sequence, "length": o.length,
                        "tm": o.tm, "gc": o.gc_content,
                        "overhang": o.overhang, "notes": o.notes or "",
                    }
                    for o in oligos
                ]

                results.append("## 基因合成寡核苷酸设计结果\n")
                results.append(f"- 寡核苷酸数量: {len(oligos)} 条\n")
                results.append("| # | 名称 | 序列 | 长度 | Tm | GC% | 方向 |")
                results.append("|---|------|------|------|----|-----|------|")
                for idx, o in enumerate(oligos):
                    direction = "Forward" if idx % 2 == 0 else "Reverse"
                    seq_display = o.sequence if len(o.sequence) <= 50 else o.sequence[:47] + "..."
                    results.append(f"| {idx+1} | {o.name} | `{seq_display}` | {o.length} | {o.tm:.1f}°C | {o.gc_content:.1f}% | {direction} |")
                results.append("")
            else:
                primers_data = [
                    {
                        "name": pair.forward.name, "sequence": pair.forward.sequence,
                        "full_sequence": pair.forward.full_sequence, "length": pair.forward.length,
                        "tm": pair.forward.tm, "gc": pair.forward.gc_content,
                        "overhang": pair.forward.overhang, "notes": pair.forward.notes or "",
                    },
                    {
                        "name": pair.reverse.name, "sequence": pair.reverse.sequence,
                        "full_sequence": pair.reverse.full_sequence, "length": pair.reverse.length,
                        "tm": pair.reverse.tm, "gc": pair.reverse.gc_content,
                        "overhang": pair.reverse.overhang, "notes": pair.reverse.notes or "",
                    },
                ]

                results.append("## 引物设计结果\n")
                results.append("### 正向引物")
                results.append(f"- 名称: {pair.forward.name}")
                results.append(f"- 退火区序列: `{pair.forward.sequence}`")
                if pair.forward.overhang:
                    results.append(f"- 完整序列: `{pair.forward.full_sequence}`")
                    results.append(f"- 突出端: `{pair.forward.overhang}`")
                results.append(f"- Tm: {pair.forward.tm:.1f}°C")
                results.append(f"- GC: {pair.forward.gc_content:.1f}%")
                results.append(f"- 长度: {pair.forward.length} bp\n")

                results.append("### 反向引物")
                results.append(f"- 名称: {pair.reverse.name}")
                results.append(f"- 退火区序列: `{pair.reverse.sequence}`")
                if pair.reverse.overhang:
                    results.append(f"- 完整序列: `{pair.reverse.full_sequence}`")
                    results.append(f"- 突出端: `{pair.reverse.overhang}`")
                results.append(f"- Tm: {pair.reverse.tm:.1f}°C")
                results.append(f"- GC: {pair.reverse.gc_content:.1f}%")
                results.append(f"- 长度: {pair.reverse.length} bp\n")

                results.append("### 扩增信息")
                results.append(f"- 产物大小: {pair.product_size} bp")
                results.append(f"- 推荐退火温度: {pair.annealing_temp:.1f}°C\n")

        # 3. 序列验证
        if optimized_seq:
            validator = SequenceValidator()
            val_result = validator.validate(optimized_seq, sequence_type="dna")
            results.append("## 序列验证\n")
            if val_result.is_valid:
                results.append("验证通过\n")
            else:
                results.append("存在问题:")
                for err in val_result.errors:
                    results.append(f"- {err}")
            if val_result.warnings:
                results.append("\n**警告:**")
                for warn in val_result.warnings:
                    results.append(f"- {warn}")
            if val_result.details:
                results.append(f"\n- 序列长度: {val_result.details.get('sequence_length', 'N/A')} bp")
                if "gc_content" in val_result.details:
                    results.append(f"- GC 含量: {val_result.details['gc_content']:.1f}%")

        # 4. 克隆策略
        if optimized_seq:
            vector_name = vector_id
            vector_seq = _load_vector_sequence(vector_id)
            try:
                method_map = {
                    "Gibson Assembly": CloningMethod.GIBSON,
                    "Golden Gate": CloningMethod.GOLDEN_GATE,
                    "限制性酶切": CloningMethod.RESTRICTION,
                "全基因合成": CloningMethod.GENE_SYNTHESIS,
                }
                strategy = generate_cloning_strategy(
                    method=method_map.get(cloning_method, CloningMethod.GIBSON),
                    insert_seq=optimized_seq, insert_name=sequence_name,
                    vector_seq=vector_seq, vector_name=vector_name,
                    homology_arm=homology_arm, enzyme=enzyme,
                )
                results.append("\n## 克隆方案\n")
                results.append(strategy.to_protocol())
            except Exception as e:
                results.append(f"\n## 克隆方案\n生成失败: {e}")

        result_text = "\n".join(results)

        # 5. 生成下载文件
        genbank_path = _write_genbank(sequence_name, optimized_seq, primers_data, vector_id)
        primer_path = _write_primer_tsv(primers_data)
        report_path = _write_report(sequence_name, sequence, optimized_seq, primers_data, vector_id, cloning_method)

        return result_text, genbank_path, primer_path, report_path

    except Exception as e:
        return f"错误: {str(e)}", None, None, None


def _write_genbank(name, seq, primers, vector_id):
    if not seq:
        return None
    design = PlasmidDesign(
        design_id=f"PD_{uuid.uuid4().hex[:8]}", design_name=name,
        insert_sequence=seq, insert_name=name, vector_id=vector_id,
        vector_name=vector_id, final_sequence=seq, primers=primers,
        cloning_method="", design_date=datetime.now().strftime("%Y-%m-%d"),
    )
    gen = GenBankGenerator()
    content = gen.generate(design, organism="synthetic construct")
    path = os.path.join(tempfile.gettempdir(), f"{name}.gb")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _write_primer_tsv(primers):
    if not primers:
        return None
    gen = PrimerOrderGenerator()
    content = gen.generate_excel(primers, "")
    path = os.path.join(tempfile.gettempdir(), "primers.tsv")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _write_report(name, input_seq, optimized_seq, primers, vector_id, method):
    design = PlasmidDesign(
        design_id=f"PD_{uuid.uuid4().hex[:8]}", design_name=name,
        insert_sequence=input_seq, insert_name=name, vector_id=vector_id,
        vector_name=vector_id, final_sequence=optimized_seq or "", primers=primers,
        cloning_method=method, design_date=datetime.now().strftime("%Y-%m-%d"),
    )
    gen = DesignReportGenerator()
    content = gen.generate(design)
    path = os.path.join(tempfile.gettempdir(), f"{name}_report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ==================== Tab 2: 批量设计 ====================

def process_batch(sequences_text, sequence_type, vector_id, cloning_method,
                  target_species, gc_min, gc_max, homology_arm, enzyme):
    if not sequences_text or not sequences_text.strip():
        return "请输入序列（每行一个）", None

    lines = [l.strip() for l in sequences_text.strip().split("\n") if l.strip()]
    if not lines:
        return "未检测到有效序列", None

    all_results = []
    zip_path = os.path.join(tempfile.gettempdir(), f"batch_{uuid.uuid4().hex[:8]}.zip")

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, sequence in enumerate(lines):
                seq_name = f"sequence_{i+1}"
                try:
                    sequence = sequence.upper().replace(" ", "")
                    if sequence_type == "氨基酸序列":
                        optimizer = CodonOptimizer(species=target_species.lower())
                        opt = optimizer.optimize(sequence, gc_target=(gc_min/100, gc_max/100))
                        optimized = opt.dna_sequence
                        info = f"CAI={opt.cai:.3f}, GC={opt.gc_content:.1f}%"
                    else:
                        optimized = sequence
                        info = f"长度={len(sequence)}bp"

                    # 引物设计
                    designer = PrimerDesigner()
                    if cloning_method == "Gibson Assembly":
                        pair, _ = designer.design_gibson_primers(
                            optimized, _load_vector_sequence(vector_id),
                            _get_mcs_start(vector_id), homology_arm=homology_arm,
                            primer_name=seq_name,
                        )
                    elif cloning_method == "Golden Gate":
                        pair = designer.design_golden_gate_primers(
                            optimized, enzyme_name=enzyme,
                            overhang_seq_5="AATG", overhang_seq_3="GCTT",
                            primer_name=seq_name,
                        )
                elif cloning_method == "全基因合成":
                    oligos = designer.design_synthesis_oligos(
                        optimized, primer_name=seq_name,
                    )
                    pair = None
                else:
                    pair = designer.design_pcr_primers(optimized, primer_name=seq_name)

                if cloning_method == "全基因合成":
                    primers_data = [
                        {"name": o.name, "sequence": o.sequence,
                         "full_sequence": o.full_sequence, "length": o.length,
                         "tm": o.tm, "gc": o.gc_content,
                         "overhang": o.overhang, "notes": o.notes or ""}
                        for o in oligos
                    ]
                    all_results.append(f"| {i+1} | {seq_name} | {info} | {len(oligos)} oligos | OK |")
                else:
                    primers_data = [
                        {"name": pair.forward.name, "sequence": pair.forward.sequence,
                         "full_sequence": pair.forward.full_sequence, "length": pair.forward.length,
                         "tm": pair.forward.tm, "gc": pair.forward.gc_content,
                         "overhang": pair.forward.overhang, "notes": pair.forward.notes or ""},
                        {"name": pair.reverse.name, "sequence": pair.reverse.sequence,
                         "full_sequence": pair.reverse.full_sequence, "length": pair.reverse.length,
                         "tm": pair.reverse.tm, "gc": pair.reverse.gc_content,
                         "overhang": pair.reverse.overhang, "notes": pair.reverse.notes or ""},
                    ]
                    all_results.append(f"| {i+1} | {seq_name} | {info} | {pair.forward.tm:.1f}°C | OK |")
                    gb_path = _write_genbank(seq_name, optimized, primers_data, vector_id)
                    if gb_path:
                        zf.write(gb_path, f"{seq_name}.gb")
                    primer_path = _write_primer_tsv(primers_data)
                    if primer_path:
                        zf.write(primer_path, f"{seq_name}_primers.tsv")

                except Exception as e:
                    all_results.append(f"| {i+1} | sequence_{i+1} | - | - | FAIL: {e} |")

        summary = f"## 批量设计结果 ({len(lines)} 个序列)\n\n"
        summary += "| # | 名称 | 信息 | 正向Tm | 状态 |\n|---|------|------|--------|------|\n"
        summary += "\n".join(all_results)

        return summary, zip_path

    except Exception as e:
        return f"批量设计错误: {str(e)}", None


# ==================== Tab 3: 序列分析 ====================

def process_analysis(sequence, check_restriction, check_orf, check_gc):
    if not sequence or not sequence.strip():
        return "请输入DNA序列", None

    sequence = sequence.upper().replace("\n", "").replace(" ", "")
    results = []
    gc_plot_path = None

    try:
        analyzer = SequenceAnalyzer()
        result = analyzer.analyze(
            sequence,
            check_restriction=check_restriction,
            check_orf=check_orf,
            check_gc=check_gc,
        )

        results.append(f"## 序列分析结果\n")
        results.append(f"- 序列长度: {result.sequence_length} bp")
        results.append(f"- GC 含量: {result.gc_content:.1f}%")
        results.append(f"- 编码潜力: {result.coding_potential:.1f}%\n")

        if check_restriction and result.restriction_sites:
            results.append("### 限制性酶切位点\n")
            results.append("| 酶 | 识别序列 | 位置 | 链 | 末端类型 |")
            results.append("|----|---------|------|-----|---------|")
            for site in result.restriction_sites:
                overhang_map = {"5": "5'粘端", "3": "3'粘端", "b": "平端", "blunt": "平端"}
                oh = overhang_map.get(site.overhang, site.overhang)
                results.append(f"| {site.enzyme} | {site.site} | {site.recognition_start} | {site.strand} | {oh} |")
            results.append("")

        if check_orf and result.orfs:
            results.append(f"### ORF 预测 (共 {len(result.orfs)} 个，显示前10)\n")
            results.append("| # | 起始 | 终止 | 链 | 长度 | 阅读框 | 起始密码子 | 终止密码子 | GC% |")
            results.append("|---|------|------|-----|------|--------|-----------|-----------|-----|")
            for idx, orf in enumerate(result.orfs[:10]):
                results.append(
                    f"| {idx+1} | {orf.start} | {orf.end} | {orf.strand} | "
                    f"{orf.length} | {orf.frame} | {orf.start_codon} | {orf.stop_codon or '-'} | "
                    f"{orf.gc_content:.1f}% |"
                )
            results.append("")

        if check_gc and result.gc_distribution:
            extremes = [r for r in result.gc_distribution if r.is_extreme]
            results.append(f"### GC 分布分析\n")
            results.append(f"- 滑动窗口数: {len(result.gc_distribution)}")
            results.append(f"- 极端区域 (<30% or >70%): {len(extremes)}\n")
            if extremes:
                results.append("| 起始 | 终止 | GC% |")
                results.append("|------|------|-----|")
                for r in extremes[:20]:
                    results.append(f"| {r.start} | {r.end} | {r.gc_content:.1f}% |")

            # 生成 GC 分布图
            try:
                import matplotlib
                matplotlib.use("Agg")
                import matplotlib.pyplot as plt
                positions = [r.start for r in result.gc_distribution]
                gc_values = [r.gc_content for r in result.gc_distribution]
                fig, ax = plt.subplots(figsize=(8, 3))
                ax.plot(positions, gc_values, "b-", linewidth=0.8)
                ax.axhline(y=30, color="r", linestyle="--", linewidth=0.5, label="30%")
                ax.axhline(y=70, color="r", linestyle="--", linewidth=0.5, label="70%")
                ax.axhline(y=result.gc_content, color="g", linestyle="-", linewidth=0.5, label=f"均值 {result.gc_content:.1f}%")
                ax.set_xlabel("Position (bp)")
                ax.set_ylabel("GC %")
                ax.set_title("GC Content Distribution")
                ax.legend(fontsize=8)
                fig.tight_layout()
                gc_plot_path = os.path.join(tempfile.gettempdir(), "gc_distribution.png")
                fig.savefig(gc_plot_path, dpi=100)
                plt.close(fig)
            except ImportError:
                pass

        if result.warnings:
            results.append("\n### 警告\n")
            for w in result.warnings:
                results.append(f"- {w}")

        return "\n".join(results), gc_plot_path

    except Exception as e:
        return f"分析错误: {str(e)}", None


def check_compatibility(insert_seq, vector_id, enzymes_text):
    if not insert_seq or not insert_seq.strip():
        return "请输入插入片段序列"
    if not enzymes_text or not enzymes_text.strip():
        return "请输入要检查的酶（逗号分隔）"

    try:
        insert_seq = insert_seq.upper().replace("\n", "").replace(" ", "")
        enzymes = [e.strip() for e in enzymes_text.split(",") if e.strip()]
        vector_seq = _load_vector_sequence(vector_id)

        analyzer = SequenceAnalyzer()
        result = analyzer.check_cloning_compatibility(insert_seq, vector_seq, enzymes)

        lines = [f"## 克隆兼容性检查\n"]
        lines.append(f"**兼容性: {'通过' if result['compatible'] else '不通过'}**\n")
        if result["issues"]:
            lines.append("### 问题")
            for issue in result["issues"]:
                lines.append(f"- {issue}")
        if result["recommendations"]:
            lines.append("### 建议")
            for rec in result["recommendations"]:
                lines.append(f"- {rec}")
        if not result["issues"] and not result["recommendations"]:
            lines.append("未发现问题，克隆方案可行。")

        return "\n".join(lines)
    except Exception as e:
        return f"检查错误: {str(e)}"


# ==================== Tab 4: 多格式导出 ====================

def process_export(name, sequence, format_choice):
    if not sequence or not sequence.strip():
        return None

    sequence = sequence.upper().replace("\n", "").replace(" ", "")
    features = [
        SequenceFeature(name="Full sequence", feature_type="source",
                        start=1, end=len(sequence), strand="+")
    ]
    export_data = ExportData(
        name=name or "sequence", sequence=sequence, features=features,
        description=f"Exported from Plasmid Designer", is_circular=True,
    )

    try:
        content, mime_type = ExportManager.export(export_data, format_choice)
        extensions = {
            "genbank": ".gb", "snapgene": ".dna", "benchling": ".json",
            "fasta": ".fasta", "sbol": ".json",
        }
        ext = extensions.get(format_choice, ".txt")
        filename = f"{name or 'sequence'}{ext}"
        path = os.path.join(tempfile.gettempdir(), filename)

        if isinstance(content, bytes):
            with open(path, "wb") as f:
                f.write(content)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        return path
    except Exception as e:
        raise gr.Error(f"导出失败: {str(e)}")


def process_export_all(name, sequence):
    if not sequence or not sequence.strip():
        return None

    sequence = sequence.upper().replace("\n", "").replace(" ", "")
    features = [
        SequenceFeature(name="Full sequence", feature_type="source",
                        start=1, end=len(sequence), strand="+")
    ]
    export_data = ExportData(
        name=name or "sequence", sequence=sequence, features=features,
        description=f"Exported from Plasmid Designer", is_circular=True,
    )

    try:
        zip_content = ExportManager.export_all(export_data)
        path = os.path.join(tempfile.gettempdir(), f"{name or 'sequence'}_exports.zip")
        with open(path, "wb") as f:
            f.write(zip_content)
        return path
    except Exception as e:
        raise gr.Error(f"导出失败: {str(e)}")


# ==================== Tab 5: 载体库 ====================

def get_vector_list():
    library = VectorLibrary()
    library.load_from_directory(VECTORS_DIR)
    vectors = library.list_vectors()
    if not vectors:
        return "载体库为空", gr.update(choices=[], value=None)

    rows = []
    id_list = []
    for v in vectors:
        id_list.append(v.id)
        host_str = ", ".join(v.host) if v.host else "N/A"
        ab_str = ", ".join(v.antibiotic_resistance) if v.antibiotic_resistance else "N/A"
        rows.append(f"| `{v.id}` | {v.name} | {v.vector_type} | {host_str} | {ab_str} | {v.length} bp |")

    table = "## 载体库\n\n| ID | 名称 | 类型 | 宿主 | 抗性 | 长度 |\n|----|------|------|------|------|------|\n"
    table += "\n".join(rows)
    return table, gr.update(choices=id_list, value=id_list[0] if id_list else None)


def get_vector_detail(vector_id):
    vector = _get_vector_obj(vector_id)
    if not vector:
        return "未找到载体", None, None

    lines = [f"## {vector.name}\n"]
    lines.append(f"- **ID**: `{vector.id}`")
    lines.append(f"- **来源**: {vector.source}")
    lines.append(f"- **类型**: {vector.vector_type}")
    lines.append(f"- **宿主**: {', '.join(vector.host) if vector.host else 'N/A'}")
    lines.append(f"- **抗性**: {', '.join(vector.antibiotic_resistance) if vector.antibiotic_resistance else 'N/A'}")
    lines.append(f"- **拷贝数**: {vector.copy_number}")
    lines.append(f"- **长度**: {vector.length} bp")
    lines.append(f"- **描述**: {vector.description}\n")

    if vector.elements:
        lines.append("### 序列特征\n")
        lines.append("| 名称 | 类型 | 起始 | 终止 | 链 |")
        lines.append("|------|------|------|------|-----|")
        for elem in vector.elements:
            lines.append(f"| {elem.name} | {elem.element_type.value} | {elem.start} | {elem.end} | {elem.strand} |")

    if vector.mcs:
        lines.append(f"\n### MCS (多克隆位点)\n")
        lines.append(f"- 位置: {vector.mcs.start}..{vector.mcs.end}")
        mcs_enzymes = vector.mcs.get_unique_enzymes() if vector.mcs else []
        if mcs_enzymes:
            lines.append(f"- 酶: {', '.join(mcs_enzymes)}")

    # 载体序列下载
    fasta_path = os.path.join(tempfile.gettempdir(), f"{vector_id}.fasta")
    with open(fasta_path, "w") as f:
        f.write(f">{vector_id} {vector.name}\n{vector.sequence.upper()}")

    gb_path = os.path.join(tempfile.gettempdir(), f"{vector_id}.gb")
    from core.export_formats import GenBankExporter
    from core.output_generator import create_default_features
    export_data = ExportData(
        name=vector.name, sequence=vector.sequence, features=[],
        description=vector.description, is_circular=True,
    )
    gb_content = GenBankExporter.export(export_data)
    with open(gb_path, "w") as f:
        f.write(gb_content)

    return "\n".join(lines), fasta_path, gb_path


# ==================== 构建 Gradio UI ====================

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;600;700&display=swap');
:root, body, .gradio-container {
    font-family: 'Noto Sans', 'Helvetica Neue', Arial, sans-serif !important;
}
code, pre, .monospace, textarea {
    font-family: 'Noto Sans Mono', 'Courier New', monospace !important;
}
"""

with gr.Blocks(
    title="Plasmid Designer",
    theme=gr.themes.Soft(),
    css=CUSTOM_CSS,
) as demo:
    gr.Markdown("""
# Plasmid Designer
### 自动化质粒构建设计平台 — 完整功能体验版

密码子优化 | 引物设计 | 克隆策略 | 序列分析 | 多格式导出
""")

    with gr.Tabs():
        # ---- Tab 1: 单序列设计 ----
        with gr.Tab("单序列设计"):
            with gr.Row():
                with gr.Column(scale=2):
                    gr.Markdown("## 序列输入")
                    sequence_input = gr.Textbox(
                        label="输入序列",
                        placeholder="请输入氨基酸序列（单字母代码）或DNA序列",
                        lines=6,
                    )
                    with gr.Row():
                        sequence_type = gr.Radio(
                            ["氨基酸序列", "DNA序列"], label="序列类型", value="氨基酸序列",
                        )
                        sequence_name = gr.Textbox(
                            label="序列名称", value="target_gene", placeholder="例如: GFP",
                        )
                    with gr.Row():
                        vector_id = gr.Dropdown(
                            choices=get_available_vectors(), label="目标载体", value="pET-28a",
                        )
                        cloning_method = gr.Dropdown(
                            ["Gibson Assembly", "Golden Gate", "限制性酶切", "全基因合成"],
                            label="克隆方法", value="Gibson Assembly",
                        )
                    with gr.Row():
                        optimize_codons = gr.Checkbox(label="启用密码子优化", value=True)
                        target_species = gr.Dropdown(
                            choices=get_available_species(), label="目标物种", value="ecoli",
                        )
                    with gr.Accordion("高级参数", open=False):
                        with gr.Row():
                            gc_min = gr.Slider(minimum=20, maximum=50, value=40, step=1, label="GC 最小 %")
                            gc_max = gr.Slider(minimum=50, maximum=80, value=60, step=1, label="GC 最大 %")
                        with gr.Row():
                            homology_arm = gr.Slider(minimum=15, maximum=40, value=20, step=1, label="Gibson 同源臂 (bp)")
                            enzyme = gr.Dropdown(choices=["BsaI", "BsmBI", "BbsI"], label="Golden Gate 酶", value="BsaI")

                    submit_btn = gr.Button("开始设计", variant="primary", size="lg")

                with gr.Column(scale=3):
                    output = gr.Markdown(label="设计结果")
                    with gr.Row():
                        genbank_file = gr.DownloadButton(label="下载 GenBank", variant="secondary")
                        primer_file = gr.DownloadButton(label="下载引物 TSV", variant="secondary")
                        report_file = gr.DownloadButton(label="下载设计报告", variant="secondary")

            gr.Examples(
                examples=[
                    ["MKTLLILAVVATAIATLAVGGVALAAG", "氨基酸序列", "example_protein", "pET-28a", "Gibson Assembly", True, "ecoli", 40, 60, 20, "BsaI"],
                    ["MKVLWAALLTFLGCAATSGSQAPDRRNRLALASLLRLQGVSSVQIRCRD", "氨基酸序列", "GFP", "pET-28a", "Golden Gate", True, "ecoli", 40, 60, 20, "BsaI"],
                    ["ATGGCTAGCATTGAAGGTGACGTTGACGATGGTTGG", "DNA序列", "synthetic_gene", "pET-28a", "限制性酶切", False, "ecoli", 40, 60, 20, "BsaI"],
                ["MKVLWAALLTFLGCAATSGSQAPDRRNRLALASLLRLQGVSSVQIRCRD", "氨基酸序列", "synth_gene", "pET-28a", "全基因合成", True, "ecoli", 40, 60, 20, "BsaI"],
                ],
                inputs=[sequence_input, sequence_type, sequence_name, vector_id,
                        cloning_method, optimize_codons, target_species,
                        gc_min, gc_max, homology_arm, enzyme],
            )

            submit_btn.click(
                fn=process_design,
                inputs=[sequence_input, sequence_type, sequence_name, vector_id,
                        cloning_method, optimize_codons, target_species,
                        gc_min, gc_max, homology_arm, enzyme],
                outputs=[output, genbank_file, primer_file, report_file],
            )

        # ---- Tab 2: 批量设计 ----
        with gr.Tab("批量设计"):
            gr.Markdown("## 批量序列设计\n输入多个序列（每行一个），使用相同参数批量设计。")
            with gr.Row():
                with gr.Column(scale=1):
                    batch_input = gr.Textbox(
                        label="批量输入序列（每行一个）",
                        placeholder="MKTLLILAVVATAIATLAVGGVALAAG\nMKVLWAALLTFLGCAATSGSQAPDRRNRLALASLLRLQGVSSVQIRCRD\nATGGCTAGCATTGAAGGTGACGTTGACGATGGTTGG",
                        lines=8,
                    )
                    batch_type = gr.Radio(["氨基酸序列", "DNA序列"], label="序列类型", value="氨基酸序列")
                    with gr.Row():
                        batch_vector = gr.Dropdown(choices=get_available_vectors(), label="目标载体", value="pET-28a")
                        batch_method = gr.Dropdown(["Gibson Assembly", "Golden Gate", "限制性酶切", "全基因合成"], label="克隆方法", value="Gibson Assembly")
                    batch_species = gr.Dropdown(choices=get_available_species(), label="目标物种", value="ecoli")
                    with gr.Row():
                        batch_gc_min = gr.Slider(minimum=20, maximum=50, value=40, step=1, label="GC 最小 %")
                        batch_gc_max = gr.Slider(minimum=50, maximum=80, value=60, step=1, label="GC 最大 %")
                    batch_submit = gr.Button("开始批量设计", variant="primary")

                with gr.Column(scale=2):
                    batch_output = gr.Markdown(label="批量设计结果")
                    batch_zip = gr.DownloadButton(label="下载全部结果 ZIP", variant="secondary")

            batch_submit.click(
                fn=process_batch,
                inputs=[batch_input, batch_type, batch_vector, batch_method,
                        batch_species, batch_gc_min, batch_gc_max,
                        gr.Slider(minimum=15, maximum=40, value=20, step=1, label="同源臂", visible=False),
                        gr.Dropdown(choices=["BsaI"], visible=False)],
                outputs=[batch_output, batch_zip],
            )

        # ---- Tab 3: 序列分析 ----
        with gr.Tab("序列分析"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("## 序列分析")
                    analysis_input = gr.Textbox(
                        label="DNA 序列", placeholder="请输入DNA序列", lines=6,
                    )
                    with gr.Row():
                        chk_restriction = gr.Checkbox(label="限制性位点", value=True)
                        chk_orf = gr.Checkbox(label="ORF 预测", value=True)
                        chk_gc = gr.Checkbox(label="GC 分析", value=True)
                    analysis_submit = gr.Button("开始分析", variant="primary")

                    gr.Markdown("### 克隆兼容性检查")
                    compat_insert = gr.Textbox(label="插入片段序列", placeholder="DNA序列", lines=3)
                    compat_vector = gr.Dropdown(choices=get_available_vectors(), label="载体", value="pET-28a")
                    compat_enzymes = gr.Textbox(label="酶列表（逗号分隔）", placeholder="EcoRI, BamHI, XhoI")
                    compat_submit = gr.Button("检查兼容性", variant="secondary")

                with gr.Column(scale=2):
                    analysis_output = gr.Markdown(label="分析结果")
                    gc_plot = gr.Image(label="GC 分布图", visible=True)
                    compat_output = gr.Markdown(label="兼容性检查结果")

            analysis_submit.click(
                fn=process_analysis,
                inputs=[analysis_input, chk_restriction, chk_orf, chk_gc],
                outputs=[analysis_output, gc_plot],
            )
            compat_submit.click(
                fn=check_compatibility,
                inputs=[compat_insert, compat_vector, compat_enzymes],
                outputs=compat_output,
            )

        # ---- Tab 4: 多格式导出 ----
        with gr.Tab("多格式导出"):
            gr.Markdown("## 多格式序列导出\n支持 GenBank / FASTA / SnapGene / Benchling / SBOL 格式。")
            with gr.Row():
                with gr.Column(scale=1):
                    export_name = gr.Textbox(label="序列名称", value="my_sequence")
                    export_seq = gr.Textbox(label="DNA 序列", placeholder="请输入DNA序列", lines=6)
                    export_format = gr.Dropdown(
                        choices=["genbank", "fasta", "snapgene", "benchling", "sbol"],
                        label="导出格式", value="genbank",
                    )
                    with gr.Row():
                        export_submit = gr.Button("导出", variant="primary")
                        export_all_submit = gr.Button("导出全部格式 ZIP", variant="secondary")

                with gr.Column(scale=1):
                    export_file = gr.DownloadButton(label="下载文件", variant="secondary")
                    export_zip = gr.DownloadButton(label="下载 ZIP", variant="secondary")

            export_submit.click(fn=process_export, inputs=[export_name, export_seq, export_format], outputs=export_file)
            export_all_submit.click(fn=process_export_all, inputs=[export_name, export_seq], outputs=export_zip)

        # ---- Tab 5: 载体库 ----
        with gr.Tab("载体库"):
            gr.Markdown("## 载体库浏览")
            with gr.Row():
                with gr.Column(scale=2):
                    vector_table, vector_select_init = get_vector_list()
                    vector_list_md = gr.Markdown(vector_table)
                with gr.Column(scale=1):
                    vector_select = gr.Dropdown(
                        choices=get_available_vectors(), label="选择载体查看详情", value="pET-28a",
                    )
                    vector_detail_btn = gr.Button("查看详情", variant="primary")
                    with gr.Row():
                        vector_fasta_btn = gr.DownloadButton(label="下载 FASTA", variant="secondary")
                        vector_gb_btn = gr.DownloadButton(label="下载 GenBank", variant="secondary")

            vector_detail_md = gr.Markdown()
            vector_detail_btn.click(
                fn=get_vector_detail, inputs=vector_select,
                outputs=[vector_detail_md, vector_fasta_btn, vector_gb_btn],
            )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
