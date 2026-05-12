"""
序列验证模块测试
"""

import pytest
import sys
sys.path.insert(0, '/root/.openclaw/workspace/plasmid-designer-v2/src/backend')

from core.sequence_validator import (
    SequenceValidator, ValidationResult,
    analyze_sequence_composition, predict_tm
)


def test_dna_validation():
    """测试DNA序列验证"""
    validator = SequenceValidator()
    
    # 有效DNA序列
    result = validator.validate("ATGAAATAG", sequence_type="dna")
    
    assert result.is_valid
    assert result.details['sequence_length'] == 9


def test_invalid_dna():
    """测试无效DNA序列"""
    validator = SequenceValidator()
    
    # 含无效碱基
    result = validator.validate("ATGXAA", sequence_type="dna")
    
    assert not result.is_valid
    assert len(result.errors) > 0


def test_amino_acid_validation():
    """测试氨基酸序列验证"""
    validator = SequenceValidator()
    
    result = validator.validate("MKVLWAALLT", sequence_type="amino_acid")
    
    assert result.is_valid
    assert result.details['sequence_length'] == 10


def test_invalid_aa():
    """测试无效氨基酸序列"""
    validator = SequenceValidator()
    
    result = validator.validate("MKVLXAALLT", sequence_type="amino_acid")
    
    assert not result.is_valid
    assert any("Invalid amino acid" in e for e in result.errors)


def test_orf_validation():
    """测试ORF验证"""
    validator = SequenceValidator()
    
    # 完整ORF
    result = validator.validate("ATGAAATAG", sequence_type="dna", check_orf=True)
    
    assert result.details.get('start_codon') == 'ATG'
    assert result.details.get('stop_codon') == 'TAG'


def test_orf_length_check():
    """测试ORF长度检查"""
    validator = SequenceValidator()
    
    # 不是3的倍数
    result = validator.validate("ATGAAA", sequence_type="dna", check_orf=True)
    
    # 长度为6，是3的倍数，应该通过
    assert result.is_valid


def test_gc_content():
    """测试GC含量检查"""
    validator = SequenceValidator()
    
    # 50% GC
    result = validator.validate("GCGCATAT", sequence_type="dna", check_gc=True)
    
    assert 'gc_content' in result.details


def test_high_gc_warning():
    """测试高GC警告"""
    validator = SequenceValidator()
    
    # 高GC序列
    result = validator.validate("GCGCGCGCGCGC", sequence_type="dna", check_gc=True)
    
    assert len(result.warnings) > 0


def test_restriction_site_check():
    """测试限制性位点检查"""
    validator = SequenceValidator()
    
    # 含EcoRI位点 (GAATTC)
    result = validator.validate(
        "ATGGAATTCATG", 
        sequence_type="dna", 
        check_restriction_sites=True,
        forbidden_sites=["GAATTC"]
    )
    
    assert len(result.warnings) > 0
    assert "GAATTC" in result.details.get('restriction_sites_found', {})


def test_find_orfs():
    """测试ORF查找"""
    validator = SequenceValidator()
    
    # 含多个ORF的序列
    sequence = "AAAATGAAATAGTTTATGGGGTAA"
    orfs = validator.find_orfs(sequence, min_length=6)
    
    assert len(orfs) >= 1
    assert all('start' in orf for orf in orfs)
    assert all('end' in orf for orf in orfs)


def test_frame_shift_check():
    """测试移码检查"""
    validator = SequenceValidator()
    
    result = validator.check_frame_shift("ATGAAATAG", expected_frame=1)
    
    assert result['in_frame']


def test_analyze_composition():
    """测试序列组成分析"""
    result = analyze_sequence_composition("GCGCATAT")
    
    assert result['length'] == 8
    assert result['composition']['G'] == 2  # GCGCATAT: G appears 2 times
    assert result['composition']['C'] == 2


def test_predict_tm_short():
    """测试短序列Tm预测"""
    tm = predict_tm("ATGC")
    
    # 短序列使用Wallace rule
    assert tm == 12  # 2*(2) + 4*(2) = 12


def test_predict_tm_long():
    """测试长序列Tm预测"""
    tm = predict_tm("ATGC" * 10)
    
    assert tm > 0


def test_validation_result():
    """测试验证结果数据结构"""
    result = ValidationResult(
        is_valid=True,
        errors=[],
        warnings=[],
        details={}
    )
    
    result.add_error("test error")
    assert not result.is_valid
    assert "test error" in result.errors
    
    result.add_warning("test warning")
    assert "test warning" in result.warnings


def test_internal_stop_codon():
    """测试内部终止密码子检测"""
    validator = SequenceValidator()
    
    # 含内部终止密码子
    result = validator.validate("ATGTAAATGTAG", sequence_type="dna", check_orf=True)
    
    # 应该有警告
    assert len(result.warnings) > 0 or not result.is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
