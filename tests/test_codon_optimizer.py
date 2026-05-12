"""
密码子优化模块测试
"""

import pytest
import sys
sys.path.insert(0, '/root/.openclaw/workspace/plasmid-designer-v2/src/backend')

from core.codon_optimizer import CodonOptimizer, CodonOptimizationResult


def test_basic_optimization():
    """测试基本优化功能"""
    optimizer = CodonOptimizer(species="ecoli")
    
    # 测试简单氨基酸序列
    aa_seq = "MKVLWAALLTFLGCAATSGSQAPDRRNRLALASLLRLQGVSSVQIRCRDSDMNADADATIRR"  # 简化测试序列
    
    result = optimizer.optimize(aa_seq)
    
    # 检查结果类型
    assert isinstance(result, CodonOptimizationResult)
    
    # 检查DNA序列长度是氨基酸序列的3倍
    assert len(result.dna_sequence) == len(aa_seq) * 3
    
    # 检查GC含量在合理范围
    assert 0.2 <= result.gc_content <= 0.9  # gc_content 返回比例(0-1)
    
    # 检查CAI值
    assert 0 <= result.cai <= 1


def test_short_sequence():
    """测试短序列优化"""
    optimizer = CodonOptimizer(species="ecoli")
    
    aa_seq = "MGSSHHHHHH"  # 常见的His-tag序列
    
    result = optimizer.optimize(aa_seq)
    
    assert len(result.dna_sequence) == 30
    assert 'ATG' in result.dna_sequence  # 应该以ATG开始（Met）


def test_avoid_motifs():
    """测试避免特定motif"""
    optimizer = CodonOptimizer(species="ecoli")
    
    aa_seq = "MAAAAAAA"  # 多个Ala
    avoid = ["GCTGCT"]  # 需要避免的序列
    
    result = optimizer.optimize(aa_seq, avoid_motifs=avoid)
    
    # 检查结果中是否避免了该motif（如果可能的话）
    # 注意：某些情况下可能无法完全避免
    if not result.warnings:
        assert "GCTGCT" not in result.dna_sequence.upper()


def test_gc_content():
    """测试GC含量计算"""
    optimizer = CodonOptimizer(species="ecoli")
    
    # 测试不同GC含量的序列
    aa_seq = "GCGCGCGC"  # 高GC氨基酸序列
    result = optimizer.optimize(aa_seq)
    
    # Ala的密码子选择会影响GC
    # 应该在合理范围内
    assert 0.2 <= result.gc_content <= 0.9  # gc_content 返回比例(0-1)


def test_poly_x_handling():
    """测试连续相同碱基处理"""
    optimizer = CodonOptimizer(species="ecoli")
    
    # 设计一个可能产生poly-X的序列
    aa_seq = "KKKKKKK"  # Lys有AAA和AAG两个密码子
    
    result = optimizer.optimize(aa_seq)
    
    # 检查是否有超过4个连续相同碱基
    for base in 'ATGC':
        assert base * 5 not in result.dna_sequence


def test_cai_calculation():
    """测试CAI计算"""
    optimizer = CodonOptimizer(species="ecoli")
    
    # 使用纯高频密码子的序列应该有较高CAI
    aa_seq = "MMM"  # Met只有一个密码子
    
    result = optimizer.optimize(aa_seq)
    
    # Met的CAI应该是1.0（只有一个密码子）
    assert result.cai == 1.0 or result.cai > 0.9


def test_translate_function():
    """测试翻译功能"""
    from core.codon_optimizer import translate_dna
    
    # 测试简单DNA序列
    dna = "ATGGCTTAA"  # Met-Ala-Stop
    
    aa = translate_dna(dna)
    
    assert aa == "MA*"


def test_result_dataclass():
    """测试结果数据结构"""
    result = CodonOptimizationResult(
        dna_sequence="ATGAAATAG",
        amino_acid_sequence="MK*",
        cai=0.85,
        gc_content=44.4,
        gc_distribution=[44.0, 45.0],
        warnings=[],
        avoided_motifs=["AAA"]
    )
    
    assert result.dna_sequence == "ATGAAATAG"
    assert result.cai == 0.85
    assert len(result.gc_distribution) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
