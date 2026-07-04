from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_DOCS = [
    "docs/architecture.md",
    "docs/rag_design.md",
    "docs/agent_router_design.md",
    "docs/tool_calling_design.md",
    "docs/memory_design.md",
    "docs/security_design.md",
    "docs/observability_design.md",
    "docs/deployment_design.md",
    "docs/interview_guide.md",
    "docs/demo_script.md",
    "docs/checklist.md",
]


REQUIRED_SCRIPTS = [
    "scripts/dev_start.sh",
    "scripts/dev_start.ps1",
    "scripts/run_tests.sh",
    "scripts/run_tests.ps1",
    "scripts/run_eval.sh",
    "scripts/run_eval.ps1",
    "scripts/demo_check.sh",
    "scripts/demo_check.ps1",
]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase12_docs_exist_and_are_not_empty():
    for path in REQUIRED_DOCS:
        doc = ROOT / path
        assert doc.exists(), f"{path} 不存在"
        assert doc.stat().st_size > 500, f"{path} 内容过少，难以作为面试交付材料"


def test_readme_is_interview_project_guide():
    content = _read("README.md")
    required_sections = [
        "## 项目定位",
        "## 背景痛点",
        "## 总体架构",
        "## 技术栈",
        "## 目录结构",
        "## 核心链路",
        "## 业务场景",
        "## RAG",
        "## LLM + LCEL",
        "## Intent Router",
        "## Tools + Spring Boot 边界",
        "## Memory",
        "## RBAC + Audit",
        "## Safety",
        "## Events",
        "## Observability + Eval",
        "## Performance + Deployment",
        "## 启动方式",
        "## 验收命令",
        "## Demo 案例",
        "## 面试讲解点",
    ]
    for section in required_sections:
        assert section in content
    assert "不是普通 ChatBot" in content
    assert "mock/fallback" in content


def test_interview_guide_covers_required_talking_points():
    content = _read("docs/interview_guide.md")
    required_topics = [
        "30 秒项目介绍",
        "2 分钟项目介绍",
        "5 分钟详细讲解",
        "项目架构怎么讲",
        "RAG 怎么讲",
        "意图识别与 Router 怎么讲",
        "工具调用怎么讲",
        "多轮记忆怎么讲",
        "权限、安全、审计怎么讲",
        "RocketMQ placeholder 怎么讲",
        "trace/eval 怎么讲",
        "性能优化与部署怎么讲",
        "项目难点怎么讲",
        "面试官追问与参考回答",
    ]
    for topic in required_topics:
        assert topic in content


def test_demo_script_has_five_business_cases_and_verification_points():
    content = _read("docs/demo_script.md")
    required_cases = [
        "用户咨询套餐规则",
        "用户查询当前套餐",
        "用户查询账单异常",
        "用户故障排查并创建工单",
        "客服人员代用户查询账单并记录审计日志",
    ]
    for case in required_cases:
        assert case in content
    assert content.count("curl.exe -X POST") >= 5
    for keyword in ["预期响应关键字段", "经过模块", "验证方式", "面试解释"]:
        assert keyword in content
    for observable in ["trace_id", "logs/audit.log", "logs/events.jsonl", "safety_result"]:
        assert observable in content


def test_mermaid_diagrams_are_present_in_delivery_docs():
    diagram_docs = [
        "docs/architecture.md",
        "docs/rag_design.md",
        "docs/agent_router_design.md",
        "docs/tool_calling_design.md",
        "docs/memory_design.md",
        "docs/security_design.md",
        "docs/observability_design.md",
        "docs/deployment_design.md",
    ]
    for path in diagram_docs:
        assert "```mermaid" in _read(path), f"{path} 缺少 Mermaid 图"


def test_delivery_scripts_exist_and_keep_simple_boundaries():
    for path in REQUIRED_SCRIPTS:
        script = ROOT / path
        assert script.exists(), f"{path} 不存在"
        content = script.read_text(encoding="utf-8")
        assert "uvicorn" in content or "pytest" in content or "run_eval.py" in content or "smoke_test.py" in content
        assert "supervisor" not in content.lower()
        assert "systemctl" not in content.lower()


def test_docs_do_not_overstate_demo_capabilities():
    texts = [_read("README.md")] + [_read(path) for path in REQUIRED_DOCS]
    combined = "\n".join(texts)
    forbidden_phrases = [
        "已支撑真实企业线上流量",
        "生产级高并发能力",
        "已接入真实 RocketMQ",
        "已接入真实 Milvus",
        "完整 Prometheus/Grafana/OTel 已接入",
        "真实 RocketMQ 已接入",
        "真实 Milvus 已接入",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in combined
