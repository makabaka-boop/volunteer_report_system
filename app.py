"""志愿服务报表生成系统
基于 Streamlit 的多角色报表平台，支持周/月周期对比、风险提醒与报告下载。
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import pandas as pd
import streamlit as st

st.set_page_config(page_title="志愿服务报表系统", page_icon="📊", layout="wide")

# ---------- 数据缓存（临时持久化）----------
DATA_KEYS = ["activities", "registrations", "signins", "tasks", "feedback"]
for key in DATA_KEYS:
    st.session_state.setdefault(key, None)


def _read_csv(file) -> Optional[pd.DataFrame]:
    if file is None:
        return None
    try:
        df = pd.read_csv(file)
        return df
    except Exception as exc:  # noqa: BLE001
        st.error(f"读取 CSV 失败：{exc}")
        return None


def _ensure_datetime(df: pd.DataFrame, cols) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _dedup(df: Optional[pd.DataFrame], subset) -> Optional[pd.DataFrame]:
    """按指定字段去重，缺列时回退到全列去重。"""
    if df is None or df.empty:
        return df
    keep_cols = [c for c in subset if c in df.columns]
    if keep_cols:
        return df.drop_duplicates(subset=keep_cols, keep="first").reset_index(drop=True)
    return df.drop_duplicates().reset_index(drop=True)


# ---------- 周期划分 ----------
def period_bounds(ref_date: datetime, kind: str) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """根据自然周/自然月返回当前周期与上一周期的起止。"""
    ref = pd.Timestamp(ref_date).normalize()
    if kind == "周报":
        # 自然周：周一为开始
        cur_start = ref - pd.Timedelta(days=ref.weekday())
        cur_end = cur_start + pd.Timedelta(days=6)
    else:
        cur_start = ref.replace(day=1)
        next_month = (cur_start + pd.offsets.MonthBegin(1))
        cur_end = next_month - pd.Timedelta(days=1)
    return cur_start, cur_end


def previous_period(cur_start: pd.Timestamp, kind: str) -> Tuple[pd.Timestamp, pd.Timestamp]:
    if kind == "周报":
        prev_start = cur_start - pd.Timedelta(days=7)
        prev_end = cur_start - pd.Timedelta(days=1)
    else:
        prev_end = cur_start - pd.Timedelta(days=1)
        prev_start = prev_end.replace(day=1)
    return prev_start, prev_end


def assign_activity_period(activities: pd.DataFrame, kind: str) -> pd.DataFrame:
    """跨周期活动去重：以活动开始日期所在周/月作为唯一归属周期。"""
    df = activities.copy()
    if "start_time" not in df.columns:
        return df
    if kind == "周报":
        df["period_key"] = df["start_time"].dt.to_period("W-SUN").astype(str)
    else:
        df["period_key"] = df["start_time"].dt.to_period("M").astype(str)
    return df


# ---------- 指标计算 ----------
def compute_metrics(
    activities: pd.DataFrame,
    regs: pd.DataFrame,
    signins: pd.DataFrame,
    tasks: pd.DataFrame,
    feedback: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> Dict[str, float]:
    """根据归属周期统计指标，跨周期活动只计入其归属周期。"""
    period_acts = activities[
        (activities["start_time"] >= start) & (activities["start_time"] <= end + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))
    ]
    act_ids = set(period_acts["activity_id"].astype(str)) if not period_acts.empty else set()

    reg_count = 0
    if regs is not None and not regs.empty and act_ids:
        reg_count = int(regs[regs["activity_id"].astype(str).isin(act_ids)].shape[0])

    sign_count = 0
    if signins is not None and not signins.empty and act_ids:
        sign_count = int(signins[signins["activity_id"].astype(str).isin(act_ids)].shape[0])

    sign_rate = (sign_count / reg_count * 100) if reg_count else 0.0

    task_total = task_done = 0
    if tasks is not None and not tasks.empty and act_ids:
        sub = tasks[tasks["activity_id"].astype(str).isin(act_ids)]
        task_total = int(sub.shape[0])
        if "status" in sub.columns:
            task_done = int((sub["status"].astype(str).str.lower().isin(["done", "已完成", "completed"])).sum())
    task_rate = (task_done / task_total * 100) if task_total else 0.0

    avg_score = 0.0
    if feedback is not None and not feedback.empty and act_ids:
        sub = feedback[feedback["activity_id"].astype(str).isin(act_ids)]
        if "score" in sub.columns and not sub.empty:
            avg_score = float(pd.to_numeric(sub["score"], errors="coerce").mean() or 0.0)

    return {
        "活动数": int(period_acts.shape[0]),
        "报名人数": reg_count,
        "签到人数": sign_count,
        "签到率": round(sign_rate, 2),
        "任务总数": task_total,
        "任务完成数": task_done,
        "任务完成率": round(task_rate, 2),
        "平均反馈评分": round(avg_score, 2),
    }


def risk_list(
    activities: pd.DataFrame,
    regs: pd.DataFrame,
    signins: pd.DataFrame,
    tasks: pd.DataFrame,
    feedback: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """生成待跟进清单：低签到率、低完成率、低评分活动。"""
    if activities is None or activities.empty:
        return pd.DataFrame()
    rows = []
    period_acts = activities[
        (activities["start_time"] >= start) & (activities["start_time"] <= end + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))
    ]
    for _, act in period_acts.iterrows():
        aid = str(act["activity_id"])
        reg_n = int(regs[regs["activity_id"].astype(str) == aid].shape[0]) if regs is not None and not regs.empty else 0
        sign_n = int(signins[signins["activity_id"].astype(str) == aid].shape[0]) if signins is not None and not signins.empty else 0
        rate = (sign_n / reg_n * 100) if reg_n else 0.0
        t_total = t_done = 0
        if tasks is not None and not tasks.empty:
            t_sub = tasks[tasks["activity_id"].astype(str) == aid]
            t_total = int(t_sub.shape[0])
            if "status" in t_sub.columns:
                t_done = int((t_sub["status"].astype(str).str.lower().isin(["done", "已完成", "completed"])).sum())
        t_rate = (t_done / t_total * 100) if t_total else 0.0
        score = 0.0
        if feedback is not None and not feedback.empty:
            f_sub = feedback[feedback["activity_id"].astype(str) == aid]
            if "score" in f_sub.columns and not f_sub.empty:
                score = float(pd.to_numeric(f_sub["score"], errors="coerce").mean() or 0.0)

        risks = []
        if reg_n and rate < 60:
            risks.append(f"签到率偏低({rate:.0f}%)")
        if t_total and t_rate < 60:
            risks.append(f"任务完成率偏低({t_rate:.0f}%)")
        if score and score < 3.5:
            risks.append(f"评分偏低({score:.1f})")
        if reg_n == 0:
            risks.append("无报名记录")
        if risks:
            rows.append({
                "活动ID": aid,
                "活动名称": act.get("activity_name", ""),
                "负责人": act.get("owner", ""),
                "开始时间": act.get("start_time"),
                "签到率%": round(rate, 1),
                "任务完成率%": round(t_rate, 1),
                "平均评分": round(score, 2),
                "风险提示": "；".join(risks),
            })
    return pd.DataFrame(rows)


# ---------- 报告渲染 ----------
def metrics_diff(cur: Dict[str, float], prev: Dict[str, float]) -> pd.DataFrame:
    rows = []
    for k in cur.keys():
        c = cur[k]
        p = prev.get(k, 0)
        delta = c - p
        rows.append({"指标": k, "当前周期": c, "上一周期": p, "变化": round(delta, 2)})
    return pd.DataFrame(rows)


def render_html_report(title: str, period_label: str, diff_df: pd.DataFrame, risk_df: pd.DataFrame) -> str:
    diff_html = diff_df.to_html(index=False, border=0, classes="tbl")
    risk_html = risk_df.to_html(index=False, border=0, classes="tbl") if not risk_df.empty else "<p>本周期无风险活动</p>"
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{title}</title>
<style>
body{{font-family:-apple-system,Segoe UI,sans-serif;margin:32px;color:#222;}}
h1{{color:#1f4e79}} h2{{color:#2e75b6;border-bottom:1px solid #eee;padding-bottom:6px;}}
.tbl{{border-collapse:collapse;width:100%;margin:12px 0;}}
.tbl th,.tbl td{{border:1px solid #ddd;padding:8px 12px;text-align:left;}}
.tbl th{{background:#f3f7fb;}}
.meta{{color:#666;font-size:13px;}}
</style></head><body>
<h1>{title}</h1>
<p class="meta">周期：{period_label}　生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<h2>核心指标对比</h2>
{diff_html}
<h2>待跟进 / 风险清单</h2>
{risk_html}
</body></html>"""


# ---------- 页面 ----------
st.title("📊 志愿服务报表生成系统")

with st.sidebar:
    st.header("角色选择")
    role = st.radio("当前角色", ["管理员", "助理", "主管"], index=0)
    st.markdown("---")
    st.caption("数据采用临时缓存，刷新页面即清空。")

# 角色：管理员（上传活动与签到）
if role == "管理员":
    st.subheader("管理员：上传活动 / 报名 / 签到记录")
    c1, c2, c3 = st.columns(3)
    with c1:
        f = st.file_uploader("活动表 activities.csv", type=["csv"], key="up_act")
        if f:
            df = _read_csv(f)
            if df is not None:
                df = _ensure_datetime(df, ["start_time", "end_time"])
                st.session_state["activities"] = df
                st.success(f"已加载活动 {len(df)} 条")
    with c2:
        f = st.file_uploader("报名表 registrations.csv", type=["csv"], key="up_reg")
        if f:
            df = _read_csv(f)
            if df is not None:
                df = _ensure_datetime(df, ["register_time"])
                before = len(df)
                df = _dedup(df, ["activity_id", "volunteer_id"])
                st.session_state["registrations"] = df
                dup = before - len(df)
                msg = f"已加载报名 {len(df)} 条" + (f"（已去重 {dup} 条）" if dup else "")
                st.success(msg)
    with c3:
        f = st.file_uploader("签到表 signins.csv", type=["csv"], key="up_sign")
        if f:
            df = _read_csv(f)
            if df is not None:
                df = _ensure_datetime(df, ["signin_time"])
                before = len(df)
                df = _dedup(df, ["activity_id", "volunteer_id"])
                st.session_state["signins"] = df
                dup = before - len(df)
                msg = f"已加载签到 {len(df)} 条" + (f"（已去重 {dup} 条）" if dup else "")
                st.success(msg)
    st.info("活动表必含字段：activity_id, activity_name, owner, start_time, end_time；报名/签到含 activity_id, volunteer_id 等。")
    if st.session_state["activities"] is not None:
        st.dataframe(st.session_state["activities"].head(20), use_container_width=True)

# 角色：助理（补充任务完成 + 反馈评分）
elif role == "助理":
    st.subheader("助理：补充任务完成状态 / 反馈评分")
    c1, c2 = st.columns(2)
    with c1:
        f = st.file_uploader("任务表 tasks.csv", type=["csv"], key="up_task")
        if f:
            df = _read_csv(f)
            if df is not None:
                df = _ensure_datetime(df, ["due_time", "complete_time"])
                st.session_state["tasks"] = df
                st.success(f"已加载任务 {len(df)} 条")
    with c2:
        f = st.file_uploader("反馈表 feedback.csv", type=["csv"], key="up_fb")
        if f:
            df = _read_csv(f)
            if df is not None:
                df = _ensure_datetime(df, ["feedback_time"])
                st.session_state["feedback"] = df
                st.success(f"已加载反馈 {len(df)} 条")
    st.info("任务表字段：activity_id, task_id, status(done/pending)；反馈表字段：activity_id, score(1-5)。")
    tasks_df = st.session_state.get("tasks")
    if tasks_df is not None:
        st.markdown("**在线编辑任务状态**（修改后将更新缓存）")
        edited = st.data_editor(tasks_df, num_rows="dynamic", use_container_width=True, key="task_editor")
        if st.button("保存任务变更"):
            st.session_state["tasks"] = edited
            st.success("已更新缓存")

# 角色：主管（查看报告）
else:
    st.subheader("主管：周期报表 与 风险清单")
    activities = st.session_state.get("activities")
    if activities is None or activities.empty:
        st.warning("尚未上传活动数据，请联系管理员先上传。")
        st.stop()

    regs = st.session_state.get("registrations")
    signins = st.session_state.get("signins")
    tasks = st.session_state.get("tasks")
    feedback = st.session_state.get("feedback")

    # 控件区
    top1, top2 = st.columns([1, 1])
    with top1:
        kind = st.selectbox("报表周期", ["周报", "月报"])
    with top2:
        ref_date = st.date_input("参考日期", value=datetime.now().date())

    cur_start, cur_end = period_bounds(datetime.combine(ref_date, datetime.min.time()), kind)
    prev_start, prev_end = previous_period(cur_start, kind)

    # 兼容缺列：补齐 activity_name / owner
    if "activity_name" not in activities.columns:
        activities = activities.copy()
        activities["activity_name"] = activities.get("activity_id", pd.Series(dtype=str)).astype(str).map(lambda x: f"活动{x}")
        st.warning("活动表未提供 activity_name 字段，已用 activity_id 自动填充。")
    if "owner" not in activities.columns:
        activities = activities.copy()
        activities["owner"] = "未指定"
        st.warning("活动表未提供 owner 字段，已默认填充“未指定”。")

    # 筛选
    f1, f2, f3 = st.columns(3)
    with f1:
        act_options = ["全部"] + sorted(activities["activity_name"].dropna().astype(str).unique().tolist())
        sel_act = st.selectbox("按活动筛选", act_options)
    with f2:
        owner_options = ["全部"] + sorted(activities["owner"].dropna().astype(str).unique().tolist())
        sel_owner = st.selectbox("按负责人筛选", owner_options)
    with f3:
        date_range = st.date_input(
            "自定义日期范围（可选，覆盖周期）",
            value=(cur_start.date(), cur_end.date()),
        )

    # 应用筛选
    acts = activities.copy()
    if sel_act != "全部":
        acts = acts[acts["activity_name"].astype(str) == sel_act]
    if sel_owner != "全部":
        acts = acts[acts["owner"].astype(str) == sel_owner]

    # 决定当前/上一周期范围（自定义日期会覆盖默认周期）
    if isinstance(date_range, tuple) and len(date_range) == 2:
        cur_start = pd.Timestamp(date_range[0])
        cur_end = pd.Timestamp(date_range[1])
        prev_start, prev_end = previous_period(cur_start, kind)

    # 在周期最终确定后再显示文案
    st.markdown(
        f"**当前周期**：{cur_start.date()} ~ {cur_end.date()}　"
        f"**上一周期**：{prev_start.date()} ~ {prev_end.date()}"
    )

    # 跨周期去重：以活动 start_time 归属周期 → 确保活动只在其归属周期被统计
    acts = assign_activity_period(acts, kind)

    cur_metrics = compute_metrics(acts, regs, signins, tasks, feedback, cur_start, cur_end)
    prev_metrics = compute_metrics(acts, regs, signins, tasks, feedback, prev_start, prev_end)

    st.markdown("### 核心指标")
    m_cols = st.columns(5)
    m_cols[0].metric("报名人数", cur_metrics["报名人数"], cur_metrics["报名人数"] - prev_metrics["报名人数"])
    m_cols[1].metric("签到率(%)", cur_metrics["签到率"], round(cur_metrics["签到率"] - prev_metrics["签到率"], 2))
    m_cols[2].metric("任务完成率(%)", cur_metrics["任务完成率"], round(cur_metrics["任务完成率"] - prev_metrics["任务完成率"], 2))
    m_cols[3].metric("反馈评分", cur_metrics["平均反馈评分"], round(cur_metrics["平均反馈评分"] - prev_metrics["平均反馈评分"], 2))
    m_cols[4].metric("活动数", cur_metrics["活动数"], cur_metrics["活动数"] - prev_metrics["活动数"])

    diff_df = metrics_diff(cur_metrics, prev_metrics)
    st.markdown("### 周期对比明细")
    st.dataframe(diff_df, use_container_width=True)

    st.markdown("### 待跟进 / 风险清单")
    risk_df = risk_list(acts, regs, signins, tasks, feedback, cur_start, cur_end)
    if risk_df.empty:
        st.success("当前周期未发现明显风险活动 🎉" if False else "当前周期未发现明显风险活动")
    else:
        st.dataframe(risk_df, use_container_width=True)

    # 下载
    st.markdown("### 报告下载")
    title = f"志愿服务{kind}"
    period_label = f"{cur_start.date()} ~ {cur_end.date()}"
    html = render_html_report(title, period_label, diff_df, risk_df)

    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            "下载 HTML 报告",
            data=html.encode("utf-8"),
            file_name=f"{title}_{cur_start.date()}.html",
            mime="text/html",
        )
    with d2:
        buf = io.StringIO()
        diff_df.to_csv(buf, index=False)
        st.download_button(
            "下载指标对比 CSV",
            data=buf.getvalue().encode("utf-8-sig"),
            file_name=f"{title}_指标对比_{cur_start.date()}.csv",
            mime="text/csv",
        )
    with d3:
        buf = io.StringIO()
        if not risk_df.empty:
            risk_df.to_csv(buf, index=False)
        st.download_button(
            "下载风险清单 CSV",
            data=buf.getvalue().encode("utf-8-sig"),
            file_name=f"{title}_风险清单_{cur_start.date()}.csv",
            mime="text/csv",
            disabled=risk_df.empty,
        )

    with st.expander("查看 HTML 报告预览"):
        st.components.v1.html(html, height=600, scrolling=True)
