from __future__ import annotations

import re

from .models import OpportunityCard
from .scoring import calculate


METHOD_LABELS = {
    "spatial transcriptomics": "空间转录组",
    "single-cell": "单细胞分析",
    "foundation model": "基础模型",
    "digital twin": "数字孪生",
    "proteomics": "蛋白质组学",
    "metabolomics": "代谢组学",
    "multimodal": "多模态建模",
    "longitudinal": "纵向轨迹",
    "cell-cell communication": "细胞间通讯推断",
    "perturbation": "扰动实验",
    "aging clock": "衰老时钟",
    "atlas": "图谱/资源",
}


def _sentences(text: str, n: int = 2) -> list[str]:
    parts = [x.strip() for x in re.split(r"(?<=[.!?。！？])\s+", text or "") if len(x.strip()) > 24]
    return parts[:n]


def detect_methods(text: str) -> list[str]:
    low = text.casefold()
    return [term for term in METHOD_LABELS if term in low]


def data_needs(text: str, methods: list[str]) -> list[str]:
    low = text.casefold()
    needs = []
    mapping = {
        "NHANES": ["nhanes"], "UK Biobank": ["uk biobank", "biobank"],
        "hospital DXA": ["dxa", "osteoporosis", "bone density"], "CT": [" ct ", "computed tomography", "imaging"],
        "human tissue": ["tissue", "biopsy", "spatial", "single-cell"],
        "animal experiment": ["mouse", "mice", "rat", "knockout", "perturbation"],
        "omics": ["omics", "proteomics", "metabolomics", "transcriptomics", "single-cell"],
    }
    padded = f" {low} "
    for label, terms in mapping.items():
        if any(term in padded for term in terms):
            needs.append(label)
    if not needs:
        needs = ["hospital DXA", "clinical cohort"]
    return needs


def secondary_queries(methods: list[str], targets: list[str]) -> list[str]:
    method_phrase = " OR ".join(f'"{m}"' for m in methods[:3]) or '"novel method"'
    return [f"({method_phrase}) AND ({target})" for target in targets]


def build_card(article_id: int, article: dict, track: str, hits: list[str], config: dict,
               competition: list[dict], search_failed: bool = False) -> OpportunityCard:
    text = f"{article.get('title', '')}. {article.get('abstract', '')}"
    methods = detect_methods(text)
    snippets = _sentences(article.get("abstract", ""), 2)
    summary = [
        f"这项研究聚焦“{article.get('title', '未命名研究')}”，核心对象来自 {article.get('journal') or article.get('source')}。",
        f"作者主要使用了{('、'.join(METHOD_LABELS[m] for m in methods[:3])) if methods else '队列/实验与统计分析'}来回答研究问题。" + (f" 摘要证据：{snippets[0][:150]}" if snippets else ""),
        "对肌骨研究者而言，价值不只在结论本身，更在于其研究设计、数据组合或分析范式能否被迁移。" + (f" 摘要补充：{snippets[1][:120]}" if len(snippets) > 1 else ""),
    ]
    method_text = "、".join(METHOD_LABELS[m] for m in methods[:4]) if methods else "将既有研究问题转化为可复用的数据与验证流程"
    why_now_bits = []
    low = text.casefold()
    if any(x in low for x in ["single-cell", "spatial", "omics"]):
        why_now_bits.append("高通量分子测量与组织分辨率提高")
    if any(x in low for x in ["foundation model", "deep learning", "multimodal", "digital twin"]):
        why_now_bits.append("算力、预训练模型与多模态数据基础成熟")
    if any(x in low for x in ["biobank", "cohort", "longitudinal", "atlas", "resource"]):
        why_now_bits.append("大样本纵向队列和可复用数据资源出现")
    if not why_now_bits:
        why_now_bits.append("样本规模、测量精度和开放工具链达到可执行阈值")

    queries = secondary_queries(methods or hits[:2], config["transfer_targets"])
    target_matches = [x for x in competition if any(t in x.get("title", "").casefold() for t in config["transfer_targets"])]
    novelty = (
        "Unresolved" if search_failed else
        "Directly studied" if target_matches else
        "Adjacent studies exist" if competition else
        "No direct match found in current search"
    )
    score = calculate(article, track, hits, config, len(competition))
    return OpportunityCard(
        article_id=article_id,
        track=track,
        summary_zh=summary,
        new_paradigm=f"可迁移的新范式是：{method_text}。重点应验证它是否改变了问题定义、测量尺度或因果识别能力。",
        why_now="；".join(why_now_bits) + "。",
        musculoskeletal_link=(
            "该工作已直接涉及肌骨主题；下一步应关注能否扩展到骨—肌互作、疾病分层与干预反应。"
            if track == "A" else
            "可把同一范式迁移到骨重塑、肌少症、骨折风险及骨—肌跨器官网络，并用DXA/CT或组织组学做外部验证。"
        ),
        secondary_queries=queries,
        competition=competition[:8],
        unresolved_questions=[
            "核心信号在独立人群、不同年龄与性别中是否稳定？",
            "观察到的关联能否通过纵向、扰动或遗传工具支持因果解释？",
            "该方法相对现有临床指标是否带来可量化的增益？",
        ],
        transfer_questions=[
            "能否用同一分析框架建立骨—肌联合衰老轨迹，并预测骨折或功能下降？",
            "能否在DXA/CT、临床表型与组织组学之间建立可解释的多模态模型？",
            "哪些细胞、分泌因子或器官网络节点可作为可验证干预靶点？",
        ],
        data_needs=data_needs(text, methods),
        novelty_status=novelty,
        score=score,
    )
