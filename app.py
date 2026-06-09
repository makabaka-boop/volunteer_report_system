import os
import io
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from analyzer import (
    validate_and_parse,
    compute_activity_metrics,
    build_period_summary,
    compare_periods,
    get_followup_list,
    get_period_label,
    get_period_range,
    assign_period,
    apply_filters,
)
from report_generator import generate_html_report, df_to_csv_download, build_export_tables


st.set_page_config(
    page_title="志愿服务报表系统",
    page_icon="🤝",
    layout="wide",
)


SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_data")
DATA_KEYS = ["activities", "registrations", "signins", "tasks", "feedback"]


def init_state():
    for k in DATA_KEYS:
        if k not in st.session_state:
            st.session_state[k] = None
    if "data_loaded" not in st.session_state:
        st.session_state.data_loaded = False


def load_sample_data():
    paths = {
        "activities": os.path.join(SAMPLE_DIR, "activities.csv"),
        "registrations": os.path.join(SAMPLE_DIR, "registrations.csv"),
        "signins": os.path.join(SAMPLE_DIR, "signins.csv"),
        "tasks": os.path.join(SAMPLE_DIR, "tasks.csv"),
        "feedback": os.path.join(SAMPLE_DIR, "feedback.csv"),
    }
    for k, p in paths.items():
        if os.path.exists(p):
            df = pd.read_csv(p)
            st.session_state[k] = validate_and_parse(df, k)
    st.session_state.data_loaded = True


def parse_upload(uploaded_file, key):
    if uploaded_file is None:
        return None
    try:
        df = pd.read_csv(uploaded_file)
        return validate_and_parse(df, key)
    except Exception as e:
        st.error(f"解析 {key} 失败: {e}")
        return None


def data_ready():
    return all(st.session_state.get(k) is not None for k in DATA_KEYS)


def render_sidebar():
    st.sidebar.title("🤝 志愿服务报表系统")
    role = st.sidebar.radio(
        "选择角色",
        ["👨‍💼 主管", "🔧 管理员", "📝 助理"],
        index=0,
    )
    st.sidebar.markdown("---")

    if not st.session_state.data_loaded:
        st.sidebar.info("暂无数据，请先加载数据或上传CSV")
        if st.sidebar.button("📦 加载示例数据", use_container_width=True):
            load_sample_data()
            st.rerun()
    else:
        st.sidebar.success("✅ 数据已加载")
        if st.sidebar.button("🔄 重新加载示例数据", use_container_width=True):
            load_sample_data()
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.caption(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    return role


def render_admin_page():
    st.header("🔧 管理员 — 数据上传")
    st.write("上传志愿服务相关 CSV 文件。上传后数据保存在当前会话缓存中。")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📤 活动与报名")
        act_file = st.file_uploader("活动表 activities.csv", type="csv", key="up_act")
        reg_file = st.file_uploader("报名表 registrations.csv", type="csv", key="up_reg")
        sin_file = st.file_uploader("签到表 signins.csv", type="csv", key="up_sin")
    with col2:
        st.subheader("📤 任务与反馈")
        task_file = st.file_uploader("任务表 tasks.csv", type="csv", key="up_task")
        fb_file = st.file_uploader("反馈表 feedback.csv", type="csv", key="up_fb")

    if st.button("✅ 提交并解析上传数据", type="primary"):
        results = {}
        results["activities"] = parse_upload(act_file, "activities")
        results["registrations"] = parse_upload(reg_file, "registrations")
        results["signins"] = parse_upload(sin_file, "signins")
        results["tasks"] = parse_upload(task_file, "tasks")
        results["feedback"] = parse_upload(fb_file, "feedback")

        ok = True
        for k, v in results.items():
            if v is not None:
                st.session_state[k] = v
            elif st.session_state.get(k) is None:
                ok = False
                st.warning(f"{k} 未上传或解析失败")

        if ok:
            st.session_state.data_loaded = True
            st.success("数据上传成功！")
            st.rerun()
        else:
            st.info("部分数据仍使用原有缓存，新数据已更新。")

    st.markdown("---")
    if st.session_state.data_loaded:
        st.subheader("📊 当前数据概览")
        cols = st.columns(5)
        labels = [("activities", "活动"), ("registrations", "报名记录"),
                  ("signins", "签到记录"), ("tasks", "任务"), ("feedback", "反馈")]
        for col, (k, label) in zip(cols, labels):
            df = st.session_state[k]
            col.metric(label, len(df) if df is not None else 0)

        with st.expander("查看活动表样例"):
            st.dataframe(st.session_state["activities"], use_container_width=True)
    else:
        st.info("请先加载示例数据或上传CSV文件。")


def render_assistant_page():
    st.header("📝 助理 — 任务完成状态维护")
    if not data_ready():
        st.warning("请先在管理员页面加载数据或上传CSV。")
        return

    tasks_df = st.session_state["tasks"].copy()
    acts_df = st.session_state["activities"]
    merged = tasks_df.merge(acts_df[["activity_id", "name", "person_in_charge", "date"]], on="activity_id", how="left")

    st.subheader("按活动筛选任务")
    act_options = ["全部活动"] + sorted(merged["activity_id"].unique().tolist())
    sel_act = st.selectbox("选择活动", act_options)
    status_options = st.multiselect("状态筛选", ["pending", "in_progress", "completed"], default=["pending", "in_progress"])

    view = merged.copy()
    if sel_act != "全部活动":
        view = view[view["activity_id"] == sel_act]
    if status_options:
        view = view[view["status"].isin(status_options)]

    st.write(f"共 **{len(view)}** 条任务记录")

    status_map = {"pending": "⏳ 待处理", "in_progress": "🔄 进行中", "completed": "✅ 已完成"}
    rev_status_map = {v: k for k, v in status_map.items()}
    view_display = view[["task_id", "activity_id", "name", "volunteer_id", "task_name", "status", "update_time"]].copy()
    view_display["status"] = view_display["status"].map(lambda x: status_map.get(x, x))
    edited = st.data_editor(
        view_display,
        use_container_width=True,
        column_config={
            "status": st.column_config.SelectboxColumn(
                "状态", options=list(status_map.values()),
                required=True,
            ),
            "update_time": st.column_config.DatetimeColumn("更新时间", disabled=True),
            "task_id": st.column_config.TextColumn("任务ID", disabled=True),
            "activity_id": st.column_config.TextColumn("活动ID", disabled=True),
            "name": st.column_config.TextColumn("活动名称", disabled=True),
            "volunteer_id": st.column_config.TextColumn("志愿者ID", disabled=True),
            "task_name": st.column_config.TextColumn("任务名称", disabled=True),
        },
        key="task_editor",
    )

    if st.button("💾 保存任务状态更新", type="primary"):
        updated_tasks = st.session_state["tasks"].copy()
        now = pd.Timestamp(datetime.now())
        changed = 0
        for _, row in edited.iterrows():
            tid = row["task_id"]
            new_status = rev_status_map.get(row["status"], row["status"])
            idx = updated_tasks[updated_tasks["task_id"] == tid].index
            if len(idx) > 0:
                old_status = updated_tasks.at[idx[0], "status"]
                if old_status != new_status:
                    updated_tasks.at[idx[0], "status"] = new_status
                    updated_tasks.at[idx[0], "update_time"] = now
                    changed += 1
        st.session_state["tasks"] = updated_tasks
        st.success(f"已更新 {changed} 条任务记录。")


def render_supervisor_page():
    st.header("👨‍💼 主管 — 周期报表与风险监控")
    if not data_ready():
        st.warning("请先在管理员页面加载数据或上传CSV。")
        return

    activities_df = st.session_state["activities"]
    registrations_df = st.session_state["registrations"]
    signins_df = st.session_state["signins"]
    tasks_df = st.session_state["tasks"]
    feedback_df = st.session_state["feedback"]

    act_metrics_full = compute_activity_metrics(activities_df, registrations_df, signins_df, tasks_df, feedback_df)

    st.subheader("🔍 筛选条件")
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        all_acts = sorted(activities_df["activity_id"].unique().tolist())
        sel_acts = st.multiselect("按活动筛选", all_acts, default=[], placeholder="全部活动")
    with fcol2:
        all_persons = sorted(activities_df["person_in_charge"].unique().tolist())
        sel_persons = st.multiselect("按负责人筛选", all_persons, default=[], placeholder="全部负责人")
    with fcol3:
        min_date = activities_df["date"].min().date()
        max_date = activities_df["date"].max().date()
        dr = st.date_input("日期范围", value=(min_date, max_date), min_value=min_date, max_value=max_date)

    am, acts, reg, sin, tk, fb = apply_filters(
        act_metrics_full, activities_df, registrations_df, signins_df, tasks_df, feedback_df,
        selected_activities=sel_acts if sel_acts else None,
        selected_persons=sel_persons if sel_persons else None,
        date_range=dr if len(dr) == 2 else None,
    )

    filter_parts = []
    if sel_acts:
        filter_parts.append(f"活动: {', '.join(sel_acts)}")
    if sel_persons:
        filter_parts.append(f"负责人: {', '.join(sel_persons)}")
    if len(dr) == 2:
        filter_parts.append(f"日期: {dr[0]} ~ {dr[1]}")
    filter_info = " | ".join(filter_parts) if filter_parts else "无筛选（全部数据）"

    if len(am) == 0:
        st.warning("当前筛选条件下无活动数据，请调整筛选。")
        return

    st.markdown("---")
    st.subheader("📅 报表周期选择")
    pcol1, pcol2 = st.columns([1, 2])
    with pcol1:
        period_type = st.radio("周期类型", ["weekly", "monthly"], format_func=lambda x: "周报（自然周）" if x == "weekly" else "月报（自然月）", horizontal=True)
    with pcol2:
        am_period = am.copy()
        am_period["period"] = am_period["date"].apply(lambda d: assign_period(d, period_type))
        available_periods = sorted(am_period["period"].unique().tolist(), reverse=True)
        period_options = [(p, f"{p} — {get_period_label(p, period_type)}") for p in available_periods]
        sel_period_label = st.selectbox(
            "选择报告周期",
            [label for _, label in period_options],
            index=0,
        )
        sel_period = period_options[[label for _, label in period_options].index(sel_period_label)][0]

    period_summary_full = build_period_summary(am, period_type)
    curr_acts = am_period[am_period["period"] == sel_period].copy()
    comparison = compare_periods(period_summary_full, sel_period, period_type)

    kcol1, kcol2, kcol3, kcol4 = st.columns(4)
    m = comparison
    with kcol1:
        st.metric("活动数量", m["activity_count"]["current"], delta=m["activity_count"]["delta"])
        st.metric("报名总人次", m["total_registrations"]["current"], delta=m["total_registrations"]["delta"])
    with kcol2:
        sr = m["avg_signin_rate"]["current"]
        sr_prev = m["avg_signin_rate"]["previous"]
        st.metric("平均签到率", f"{sr:.0%}", delta=f"{(sr - sr_prev)*100:+.1f}pp" if sr_prev else None)
        cr = m["avg_completion_rate"]["current"]
        cr_prev = m["avg_completion_rate"]["previous"]
        st.metric("任务完成率", f"{cr:.0%}", delta=f"{(cr - cr_prev)*100:+.1f}pp" if cr_prev else None)
    with kcol3:
        sc = m["avg_score"]["current"]
        sc_prev = m["avg_score"]["previous"]
        st.metric("平均反馈评分", f"{sc:.2f}" if sc > 0 else "—", delta=f"{sc - sc_prev:+.2f}" if sc_prev else None)
        st.metric("签到总人次", m["total_signins"]["current"], delta=m["total_signins"]["delta"])
    with kcol4:
        st.metric("⚠️ 风险活动", m["risk_activity_count"]["current"], delta=m["risk_activity_count"]["delta"])
        st.metric("📌 待跟进任务", m["total_pending_tasks"]["current"], delta=m["total_pending_tasks"]["delta"])

    st.caption(f"对比说明：本期 {comparison['_meta']['current_label']} vs 上期 {comparison['_meta']['previous_label']}")

    tab1, tab2, tab3, tab4 = st.tabs(["📋 本期活动明细", "⚠️ 待跟进清单", "📈 周期趋势", "📥 下载报告"])

    with tab1:
        st.dataframe(
            curr_acts[["activity_id", "name", "date", "person_in_charge", "location",
                        "reg_count", "signin_count", "signin_rate",
                        "task_completed", "task_total", "task_completion_rate",
                        "avg_score", "fb_count", "risk_flags"]].sort_values("date"),
            use_container_width=True,
            column_config={
                "signin_rate": st.column_config.ProgressColumn("签到率", min_value=0, max_value=1, format="%d%%"),
                "task_completion_rate": st.column_config.ProgressColumn("完成率", min_value=0, max_value=1, format="%d%%"),
                "avg_score": st.column_config.NumberColumn("评分", format="%.2f"),
                "date": st.column_config.DateColumn("日期"),
            },
        )

    with tab2:
        fu = get_followup_list(curr_acts, tk, fb)
        if len(fu) > 0:
            pri_color = {"高": "🔴", "中": "🟡", "低": "🟢"}
            fu_display = fu.copy()
            fu_display.insert(0, "级别", fu_display["priority"].map(pri_color))
            st.dataframe(fu_display, use_container_width=True, hide_index=True)
        else:
            st.success("本期无待跟进事项 ✅")

    with tab3:
        st.dataframe(
            period_summary_full[["period", "activity_count", "total_registrations", "total_signins",
                                  "avg_signin_rate", "avg_completion_rate", "avg_score",
                                  "risk_activity_count", "total_pending_tasks"]].sort_values("period"),
            use_container_width=True,
            column_config={
                "avg_signin_rate": st.column_config.ProgressColumn("签到率", min_value=0, max_value=1, format="%d%%"),
                "avg_completion_rate": st.column_config.ProgressColumn("完成率", min_value=0, max_value=1, format="%d%%"),
                "avg_score": st.column_config.NumberColumn("评分", format="%.2f"),
            },
        )

    with tab4:
        st.subheader("📥 生成并下载报告")
        fu_curr = get_followup_list(curr_acts, tk, fb)

        overview_df, act_export, fu_export, trend_export = build_export_tables(
            curr_acts, period_summary_full, comparison, fu_curr, period_type, sel_period,
        )

        html_content = generate_html_report(
            period_type, sel_period, comparison, period_summary_full,
            curr_acts, fu_curr, filter_info,
        )

        st.download_button(
            label="📄 下载 HTML 报表",
            data=html_content.encode("utf-8"),
            file_name=f"volunteer_report_{sel_period}.html",
            mime="text/html",
            use_container_width=True,
        )

        dc1, dc2 = st.columns(2)
        with dc1:
            st.download_button("📊 核心指标 (CSV)", df_to_csv_download(overview_df),
                               f"metrics_{sel_period}.csv", "text/csv", use_container_width=True)
            st.download_button("📋 活动明细 (CSV)", df_to_csv_download(act_export),
                               f"activities_{sel_period}.csv", "text/csv", use_container_width=True)
        with dc2:
            st.download_button("⚠️ 待跟进清单 (CSV)", df_to_csv_download(fu_export),
                               f"followup_{sel_period}.csv", "text/csv", use_container_width=True)
            st.download_button("📈 周期趋势 (CSV)", df_to_csv_download(trend_export),
                               f"trend_{sel_period}.csv", "text/csv", use_container_width=True)

        st.markdown("---")
        st.subheader("📄 报告预览")
        st.components.v1.html(html_content, height=800, scrolling=True)


def main():
    init_state()
    role = render_sidebar()
    if "主管" in role:
        render_supervisor_page()
    elif "管理员" in role:
        render_admin_page()
    elif "助理" in role:
        render_assistant_page()


if __name__ == "__main__":
    main()
