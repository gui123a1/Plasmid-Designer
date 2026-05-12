---
title: Plasmid Designer
emoji: 🧬
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
license: mit
app_port: 7860
---

# Plasmid Designer

自动化质粒构建设计平台

## 功能

- **密码子优化** — 支持 E.coli / Human / CHO / Yeast，可调 GC 含量范围
- **引物设计** — Gibson Assembly / Golden Gate / 限制性酶切 / 全基因合成
- **载体库管理** — 9 种预置载体 + NCBI 在线搜索导入 + 文件上传
- **克隆策略生成** — 自动生成中英文实验方案
- **质粒图谱** — 可视化质粒环状图谱
- **批量设计** — 一次提交 1-100 个序列
- **序列分析** — 限制性酶切位点 / ORF 预测 / GC 分析 / 克隆兼容性检查
- **多格式导出** — GenBank / SnapGene / Benchling / FASTA / SBOL

## 使用方法

1. 输入氨基酸/DNA序列
2. 选择载体和克隆方法
3. 获取完整设计方案（引物、序列、实验方案、质粒图谱）

## 技术栈

- 前端：Vue 3 + TypeScript + Pinia
- 后端：FastAPI + Pydantic + SQLAlchemy
- 生物信息：BioPython + Primer3-py
