import streamlit as st
import pandas as pd
from datetime import date
from data_processor import (
    parse_activities,
    parse_checkins,
    parse_tasks,
    parse_feedbacks,
    filter_data,
    build_period_report,
)
from report_generator import generate_html_report
from risk_analyzer import analyze_risks, build_followup_list


def _render_admin_page():
    st.title("管理员 — 上传活动与签到记录")

    st.markdown("#### 上传活动记录")
    st.markdown(
        "CSV 必需列: `activity_id`, `activity_name`, `responsible_person`, "
        "`start_date`, `end_date`, `location`"
    )
    act_file = st.file_uploader("选择活动记录 CSV", type="csv", key="act_upload")
    if act_file:
        try:
            df = pd.read_csv(act_file)
            parsed = parse_activities(df)
            st.session_state.activities = parsed
            st.success(f"活动记录上传成功，共 {len(parsed)} 条")
            with st.expander("预览数据"):
                st.dataframe(parsed, use_container_width=True)
        except Exception as e:
            st.error(f"解析失败: {e}")

    st.markdown("---")
    st.markdown("#### 上传签到记录")
    st.markdown(
        "CSV 必需列: `checkin_id`, `activity_id`, `volunteer_name`, "
        "`checkin_time`, `status`（已签到/未签到）"
    )
    ci_file = st.file_uploader("选择签到记录 CSV", type="csv", key="ci_upload")
    if ci_file:
        try:
            df = pd.read_csv(ci_file)
            parsed = parse_checkins(df)
            st.session_state.checkins = parsed
            st.success(f"签到记录上传成功，共 {len(parsed)} 条")
            with st.expander("预览数据"):
                st.dataframe(parsed, use_container_width=True)
        except Exception as e:
            st.error(f"解析失败: {e}")

    if not st.session_state.activities.empty and not st.session_state.checkins.empty:
        st.markdown("---")
        st.markdown("#### 当前数据概览")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("活动总数", len(st.session_state.activities))
        with col2:
            st.metric("报名人次", st.session_state.checkins["volunteer_name"].count())
        with col3:
            checked = st.session_state.checkins[st.session_state.checkins["status"] == "已签到"]
            rate = len(checked) / len(st.session_state.checkins) * 100 if len(st.session_state.checkins) > 0 else 0
            st.metric("整体签到率", f"{rate:.1f}%")


def _render_assistant_page():
    st.title("助理 — 补充任务完成状态")

    st.markdown("#### 上传任务记录")
    st.markdown(
        "CSV 必需列: `task_id`, `activity_id`, `volunteer_name`, "
        "`task_name`, `completion_status`（已完成/未完成/进行中）"
    )
    task_file = st.file_uploader("选择任务记录 CSV", type="csv", key="task_upload")
    if task_file:
        try:
            df = pd.read_csv(task_file)
            parsed = parse_tasks(df)
            st.session_state.tasks = parsed
            st.success(f"任务记录上传成功，共 {len(parsed)} 条")
            with st.expander("预览数据"):
                st.dataframe(parsed, use_container_width=True)
        except Exception as e:
            st.error(f"解析失败: {e}")

    st.markdown("---")
    st.markdown("#### 上传反馈记录")
    st.markdown(
        "CSV 必需列: `feedback_id`, `activity_id`, `volunteer_name`, "
        "`score`（1-5）, `comment`, `feedback_date`"
    )
    fb_file = st.file_uploader("选择反馈记录 CSV", type="csv", key="fb_upload")
    if fb_file:
        try:
            df = pd.read_csv(fb_file)
            parsed = parse_feedbacks(df)
            st.session_state.feedbacks = parsed
            st.success(f"反馈记录上传成功，共 {len(parsed)} 条")
            with st.expander("预览数据"):
                st.dataframe(parsed, use_container_width=True)
        except Exception as e:
            st.error(f"解析失败: {e}")

    if not st.session_state.tasks.empty:
        st.markdown("---")
        st.markdown("#### 任务完成概况")
        status_counts = st.session_state.tasks["completion_status"].value_counts()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("已完成", status_counts.get("已完成", 0))
        with col2:
            st.metric("进行中", status_counts.get("进行中", 0))
        with col3:
            st.metric("未完成", status_counts.get("未完成", 0))

    if not st.session_state.feedbacks.empty:
        st.markdown("#### 反馈评分分布")
        score_dist = st.session_state.feedbacks["score"].value_counts().sort_index()
        st.bar_chart(score_dist)


def _render_supervisor_page():
    st.title("主管 — 周期报告与风险清单")

    if st.session_state.activities.empty:
        st.warning("请先由管理员上传活动记录。")
        return

    if st.session_state.checkins.empty:
        st.warning("请先由管理员上传签到记录，否则报表数据将全部为 0。")
        return

    st.markdown("#### 筛选条件")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)

    with col_f1:
        activity_names = st.session_state.activities["activity_name"].unique().tolist()
        selected_activity = st.selectbox("活动名称", ["全部"] + activity_names)

    with col_f2:
        responsibles = st.session_state.activities["responsible_person"].unique().tolist()
        selected_responsible = st.selectbox("负责人", ["全部"] + responsibles)

    with col_f3:
        min_d = (
            st.session_state.activities["start_date"].min().date()
            if not st.session_state.activities["start_date"].isna().all()
            else date(2024, 1, 1)
        )
        max_d = (
            st.session_state.activities["end_date"].max().date()
            if not st.session_state.activities["end_date"].isna().all()
            else date(2026, 12, 31)
        )
        date_range = st.date_input("日期范围", value=(), min_value=min_d, max_value=max_d)

    with col_f4:
        mode = st.selectbox("报表周期", ["周报", "月报"])

    act_name_filter = None if selected_activity == "全部" else selected_activity
    resp_filter = None if selected_responsible == "全部" else selected_responsible
    dr = list(date_range) if len(date_range) == 2 else None
    mode_key = "week" if mode == "周报" else "month"

    act, ci, tk, fb = filter_data(
        st.session_state.activities,
        st.session_state.checkins,
        st.session_state.tasks,
        st.session_state.feedbacks,
        activity_name=act_name_filter,
        responsible=resp_filter,
        date_range=dr,
    )

    st.markdown("---")
    st.markdown(f"#### {mode} — 周期汇总")

    report_df, trends = build_period_report(act, ci, tk, fb, mode_key, date_range=dr)

    if report_df.empty:
        st.info("当前筛选条件下无数据。")
        return

    st.dataframe(report_df.drop(columns=["周期键"]), use_container_width=True, hide_index=True)

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    latest = report_df.iloc[-1]
    with col_m1:
        st.metric("报名人数", int(latest["报名人数"]))
    with col_m2:
        st.metric("签到率", f"{latest['签到率(%)']}%")
    with col_m3:
        st.metric("任务完成率", f"{latest['任务完成率(%)']}%")
    with col_m4:
        st.metric("平均反馈评分", latest["平均反馈评分"])

    if trends:
        st.markdown("#### 环比变化趋势")
        trend_df = pd.DataFrame(trends)
        st.dataframe(trend_df, use_container_width=True, hide_index=True)

        import plotly.graph_objects as go

        fig = go.Figure()
        periods = [t["周期"] for t in trends]
        fig.add_trace(go.Bar(x=periods, y=[t["签到率变化(%)"] for t in trends], name="签到率变化(%)"))
        fig.add_trace(go.Bar(x=periods, y=[t["任务完成率变化(%)"] for t in trends], name="任务完成率变化(%)"))
        fig.add_trace(go.Scatter(x=periods, y=[t["评分变化"] for t in trends], name="评分变化", mode="lines+markers"))
        fig.update_layout(barmode="group", title="环比变化趋势图", height=400)
        st.plotly_chart(fig, use_container_width=True)

    risk_df = analyze_risks(act, ci, tk, fb)
    followup_df = build_followup_list(act, ci, tk)

    st.markdown("---")
    st.markdown("#### 生成与下载报告")

    html, detail_df, _, _, _ = generate_html_report(act, ci, tk, fb, mode_key, date_range=dr)

    st.download_button(
        "下载 HTML 报告",
        data=html,
        file_name=f"志愿服务{mode}_{date.today()}.html",
        mime="text/html",
    )

    if not detail_df.empty:
        csv_data = detail_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "下载明细表格 (CSV)",
            data=csv_data,
            file_name=f"志愿服务{mode}_明细_{date.today()}.csv",
            mime="text/csv",
        )

    st.markdown("---")
    st.markdown("#### 风险提醒")
    if risk_df.empty:
        st.success("当前无风险项 🎉")
    else:
        st.warning(f"共发现 {len(risk_df)} 项风险")
        st.dataframe(risk_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### 待跟进清单")
    if followup_df.empty:
        st.success("当前无待跟进事项 🎉")
    else:
        st.info(f"共 {len(followup_df)} 条待跟进事项")
        st.dataframe(followup_df, use_container_width=True, hide_index=True)
        fu_csv = followup_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "下载待跟进清单 (CSV)",
            data=fu_csv,
            file_name=f"待跟进清单_{date.today()}.csv",
            mime="text/csv",
        )


st.set_page_config(page_title="志愿服务报表系统", page_icon="📊", layout="wide")

if "activities" not in st.session_state:
    st.session_state.activities = pd.DataFrame()
if "checkins" not in st.session_state:
    st.session_state.checkins = pd.DataFrame()
if "tasks" not in st.session_state:
    st.session_state.tasks = pd.DataFrame()
if "feedbacks" not in st.session_state:
    st.session_state.feedbacks = pd.DataFrame()

st.sidebar.title("志愿服务报表系统")
role = st.sidebar.radio("选择角色", ["管理员", "助理", "主管"], horizontal=True)
st.sidebar.markdown("---")

st.sidebar.markdown("### 数据状态")
st.sidebar.markdown(f"- 活动记录: {'✅ 已上传' if not st.session_state.activities.empty else '❌ 未上传'}")
st.sidebar.markdown(f"- 签到记录: {'✅ 已上传' if not st.session_state.checkins.empty else '❌ 未上传'}")
st.sidebar.markdown(f"- 任务记录: {'✅ 已上传' if not st.session_state.tasks.empty else '❌ 未上传'}")
st.sidebar.markdown(f"- 反馈记录: {'✅ 已上传' if not st.session_state.feedbacks.empty else '❌ 未上传'}")

if st.sidebar.button("清空所有数据", type="secondary"):
    st.session_state.activities = pd.DataFrame()
    st.session_state.checkins = pd.DataFrame()
    st.session_state.tasks = pd.DataFrame()
    st.session_state.feedbacks = pd.DataFrame()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown(
    "<small>志愿服务报表生成系统 v1.0<br>周期对比 · 风险提醒 · 一键报告</small>",
    unsafe_allow_html=True,
)

if role == "管理员":
    _render_admin_page()
elif role == "助理":
    _render_assistant_page()
else:
    _render_supervisor_page()
