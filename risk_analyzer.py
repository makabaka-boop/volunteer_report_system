import pandas as pd

CHECKIN_RATE_THRESHOLD = 60.0
TASK_RATE_THRESHOLD = 50.0
FEEDBACK_SCORE_THRESHOLD = 3.0


def analyze_risks(activities, checkins, tasks, feedbacks):
    risks = []

    if activities.empty:
        return pd.DataFrame()

    for _, act in activities.iterrows():
        aid = act["activity_id"]
        name = act["activity_name"]
        person = act["responsible_person"]

        cr = 0.0
        tr = 0.0
        avg_s = 0.0

        if not checkins.empty:
            c = checkins[checkins["activity_id"] == aid]
            if not c.empty:
                reg = c["volunteer_name"].nunique()
                checked = c[c["status"] == "已签到"]["volunteer_name"].nunique()
                cr = round(checked / reg * 100, 1) if reg > 0 else 0.0

        if not tasks.empty:
            t = tasks[tasks["activity_id"] == aid]
            if not t.empty:
                t_total = len(t)
                t_done = len(t[t["completion_status"] == "已完成"])
                tr = round(t_done / t_total * 100, 1) if t_total > 0 else 0.0

        if not feedbacks.empty:
            f = feedbacks[feedbacks["activity_id"] == aid]
            if not f.empty:
                avg_s = round(f["score"].mean(), 2)

        if cr < CHECKIN_RATE_THRESHOLD:
            risks.append({
                "活动ID": aid,
                "活动名称": name,
                "负责人": person,
                "风险类型": "签到率偏低",
                "当前值": f"{cr}%",
                "阈值": f"< {CHECKIN_RATE_THRESHOLD}%",
                "建议": "关注志愿者出勤情况，必要时发送提醒或调整活动时间",
            })

        if tr < TASK_RATE_THRESHOLD:
            risks.append({
                "活动ID": aid,
                "活动名称": name,
                "负责人": person,
                "风险类型": "任务完成率偏低",
                "当前值": f"{tr}%",
                "阈值": f"< {TASK_RATE_THRESHOLD}%",
                "建议": "评估任务难度与资源匹配，考虑增派人手或拆分任务",
            })

        if avg_s < FEEDBACK_SCORE_THRESHOLD and avg_s > 0:
            risks.append({
                "活动ID": aid,
                "活动名称": name,
                "负责人": person,
                "风险类型": "反馈评分偏低",
                "当前值": f"{avg_s}",
                "阈值": f"< {FEEDBACK_SCORE_THRESHOLD}",
                "建议": "收集具体反馈意见，改进活动组织与体验",
            })

    return pd.DataFrame(risks)


def build_followup_list(activities, checkins, tasks):
    items = []

    if activities.empty:
        return pd.DataFrame()

    for _, act in activities.iterrows():
        aid = act["activity_id"]
        name = act["activity_name"]
        person = act["responsible_person"]

        if not checkins.empty:
            c = checkins[checkins["activity_id"] == aid]
            not_checked = c[c["status"] == "未签到"]
            for _, row in not_checked.iterrows():
                items.append({
                    "活动ID": aid,
                    "活动名称": name,
                    "负责人": person,
                    "待跟进事项": f"志愿者 {row['volunteer_name']} 未签到",
                    "类型": "签到异常",
                })

        if not tasks.empty:
            t = tasks[tasks["activity_id"] == aid]
            incomplete = t[t["completion_status"].isin(["未完成", "进行中"])]
            for _, row in incomplete.iterrows():
                items.append({
                    "活动ID": aid,
                    "活动名称": name,
                    "负责人": person,
                    "待跟进事项": f"任务「{row['task_name']}」未完成（负责人: {row['volunteer_name']}）",
                    "类型": "任务未完成",
                })

    return pd.DataFrame(items)
