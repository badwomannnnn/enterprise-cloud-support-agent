from __future__ import annotations

import os
import uuid

import httpx
import streamlit as st


API_BASE = os.getenv("SUPPORT_AGENT_API", "http://127.0.0.1:8000")

st.set_page_config(page_title="CloudPilot 智能支持", page_icon="🛠️", layout="wide")
st.title("企业云产品智能支持与工单协同 Agent")
st.caption("演示系统：服务状态、额度和工单数据均为模拟数据，不代表真实腾讯云状态。")

if "session_id" not in st.session_state:
    st.session_state.session_id = f"demo-{uuid.uuid4().hex[:8]}"
if "messages" not in st.session_state:
    st.session_state.messages = []

user_tab, engineer_tab, about_tab = st.tabs(["用户支持", "工程师工作台", "系统说明"])

with user_tab:
    st.subheader("描述问题")
    account_id = st.text_input("演示账户 ID", value="demo-account")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    prompt = st.chat_input("例如：生产环境所有请求都返回 503，刚刚开始")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            try:
                response = httpx.post(
                    f"{API_BASE}/api/v1/chat",
                    json={
                        "session_id": st.session_state.session_id,
                        "message": prompt,
                        "account_id": account_id,
                    },
                    timeout=45,
                )
                response.raise_for_status()
                data = response.json()
                st.markdown(data["answer"])
                cols = st.columns(4)
                cols[0].metric("意图", data["intent"])
                cols[1].metric("置信度", f"{data['confidence']:.0%}")
                cols[2].metric("模型", data["model_provider"])
                cols[3].metric("转人工", "是" if data["need_human"] else "否")
                if data["citations"]:
                    with st.expander("查看引用"):
                        for citation in data["citations"]:
                            st.markdown(f"**{citation['title']}**  `{citation['score']:.2f}`")
                            st.caption(citation["excerpt"])
                if data["tool_calls"]:
                    with st.expander("查看工具调用"):
                        st.json(data["tool_calls"])
                if data.get("ticket_id"):
                    st.success(f"已创建工单：{data['ticket_id']}")
                st.session_state.messages.append({"role": "assistant", "content": data["answer"]})
            except Exception as exc:
                st.error(f"无法连接后端：{exc}")

with engineer_tab:
    st.subheader("工单列表")
    if st.button("刷新工单"):
        st.rerun()
    try:
        tickets = httpx.get(f"{API_BASE}/api/v1/tickets", timeout=10).json()
        if not tickets:
            st.info("暂无工单。可在用户支持页触发人工升级。")
        for ticket in tickets:
            with st.expander(f"{ticket['ticket_id']}  {ticket['priority']}  {ticket['status']}  {ticket['title']}"):
                st.write(ticket["description"])
                st.json(
                    {
                        "问题类型": ticket["problem_type"],
                        "错误码": ticket["error_code"],
                        "影响范围": ticket["impact_scope"],
                        "负责人": ticket["assignee"],
                        "候选知识": ticket["knowledge_candidate"],
                    }
                )
                next_status = st.selectbox(
                    "下一状态",
                    ["NEED_INFO", "AI_PROCESSING", "HUMAN_PROCESSING", "RESOLVED", "CLOSED"],
                    key=f"status-{ticket['ticket_id']}",
                )
                assignee = st.text_input("负责人", value=ticket.get("assignee") or "support-l2", key=f"a-{ticket['ticket_id']}")
                solution = st.text_area("处理说明/解决方案", key=f"s-{ticket['ticket_id']}")
                if st.button("更新工单", key=f"u-{ticket['ticket_id']}"):
                    result = httpx.patch(
                        f"{API_BASE}/api/v1/tickets/{ticket['ticket_id']}/status",
                        json={
                            "status": next_status,
                            "actor": "streamlit-engineer",
                            "note": solution,
                            "assignee": assignee,
                            "solution": solution or None,
                        },
                        timeout=10,
                    )
                    if result.is_success:
                        st.success("工单已更新")
                        st.rerun()
                    else:
                        st.error(result.json().get("detail", result.text))
    except Exception as exc:
        st.error(f"读取工单失败：{exc}")

with about_tab:
    st.markdown(
        """
        ### 这套 Demo 展示什么

        - RAG：基于虚拟产品知识库回答并显示来源。
        - Agent：根据意图和信息完整性选择追问、检索、工具或人工工单。
        - Function Calling：工具由 Python 执行，模型不能伪造查询结果。
        - 可控性：状态机约束工单流转，敏感信息在写入日志前脱敏。
        """
    )

