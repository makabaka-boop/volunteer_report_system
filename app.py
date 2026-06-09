import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
import io

from data_processor import (
    load_csv_data, save_csv_data,
    get_current_period, get_previous_period,
    filter_activities_by_period, calculate_activity_stats,
    compare_periods, get_risk_list, filter_data_by_criteria,
    get_person_list, get_activity_list, get_date_range
)
from report_generator import (
    generate_html_report, dataframe_to_csv_bytes,
    get_report_filename, generate_summary_table
)

st.set_page_config(
    page_title="志愿服务报表系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATA_DIR = os.path.join(os.path.dirname(__file__), 'sample_data')

ACTIVITIES_CSV = os.path.join(DATA_DIR, 'activities.csv')
SIGN_INS_CSV = os.path.join(DATA_DIR, 'sign_ins.csv')
TASKS_CSV = os.path.join(DATA_DIR, 'tasks.csv')
FEEDBACK_CSV = os.path.join(DATA_DIR, 'feedback.csv')


def init_session_state():
    if 'activities_df' not in st.session_state:
        st.session_state.activities_df = load_csv_data(ACTIVITIES_CSV)
    if 'sign_ins_df' not in st.session_state:
        st.session_state.sign_ins_df = load_csv_data(SIGN_INS_CSV)
    if 'tasks_df' not in st.session_state:
        st.session_state.tasks_df = load_csv_data(TASKS_CSV)
    if 'feedback_df' not in st.session_state:
        st.session_state.feedback_df = load_csv_data(FEEDBACK_CSV)
    if 'role' not in st.session_state:
        st.session_state.role = None


def save_all_data():
    save_csv_data(st.session_state.activities_df, ACTIVITIES_CSV)
    save_csv_data(st.session_state.sign_ins_df, SIGN_INS_CSV)
    save_csv_data(st.session_state.tasks_df, TASKS_CSV)
    save_csv_data(st.session_state.feedback_df, FEEDBACK_CSV)


def render_sidebar():
    with st.sidebar:
        st.title("📊 志愿服务报表系统")
        st.markdown("---")
        
        st.subheader("角色选择")
        role = st.radio(
            "请选择您的角色",
            ["", "管理员", "助理", "主管"],
            index=0 if st.session_state.role is None else 
                  ["", "管理员", "助理", "主管"].index(st.session_state.role)
        )
        
        if role:
            st.session_state.role = role
        
        st.markdown("---")
        
        if st.session_state.role:
            role_info = {
                "管理员": "🔧 负责上传活动与签到记录",
                "助理": "📝 负责补充任务完成状态",
                "主管": "📈 负责查看周期报告和风险清单"
            }
            st.info(role_info.get(st.session_state.role, ""))
            
            st.markdown("---")
            if st.button("🔄 重置数据", type="secondary"):
                st.session_state.activities_df = load_csv_data(ACTIVITIES_CSV)
                st.session_state.sign_ins_df = load_csv_data(SIGN_INS_CSV)
                st.session_state.tasks_df = load_csv_data(TASKS_CSV)
                st.session_state.feedback_df = load_csv_data(FEEDBACK_CSV)
                st.success("数据已重置为初始状态")
                st.rerun()


def admin_page():
    st.header("🔧 管理员工作台")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 活动管理", "✅ 签到记录", "💬 反馈评分", "📊 数据概览"])
    
    with tab1:
        st.subheader("活动数据管理")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_activities = st.file_uploader(
                "上传活动数据 CSV 文件",
                type=['csv'],
                key="upload_activities",
                help="CSV文件需包含：activity_id, activity_name, activity_date, location, person_in_charge, planned_volunteers, registration_count, activity_type"
            )
            
            if uploaded_activities is not None:
                try:
                    df = pd.read_csv(uploaded_activities)
                    required_cols = ['activity_id', 'activity_name', 'activity_date', 
                                   'location', 'person_in_charge', 'planned_volunteers', 
                                   'registration_count', 'activity_type']
                    
                    if all(col in df.columns for col in required_cols):
                        if st.button("确认导入活动数据"):
                            st.session_state.activities_df = df
                            save_all_data()
                            st.success(f"成功导入 {len(df)} 条活动数据")
                            st.rerun()
                    else:
                        missing = [col for col in required_cols if col not in df.columns]
                        st.error(f"CSV文件缺少必要字段：{', '.join(missing)}")
                except Exception as e:
                    st.error(f"文件读取失败：{str(e)}")
        
        with col2:
            st.markdown("### 操作说明")
            st.markdown("""
            1. 下载模板文件作为参考
            2. 按照模板格式准备数据
            3. 上传 CSV 文件
            4. 确认导入数据
            """)
            
            template_activities = pd.DataFrame({
                'activity_id': ['A001'],
                'activity_name': ['示例活动'],
                'activity_date': ['2026-06-08'],
                'location': ['示例地点'],
                'person_in_charge': ['负责人'],
                'planned_volunteers': [50],
                'registration_count': [45],
                'activity_type': ['环保']
            })
            
            st.download_button(
                label="📥 下载活动模板",
                data=dataframe_to_csv_bytes(template_activities),
                file_name="activities_template.csv",
                mime="text/csv"
            )
        
        st.markdown("---")
        st.subheader("当前活动列表")
        
        if not st.session_state.activities_df.empty:
            st.dataframe(
                st.session_state.activities_df,
                use_container_width=True,
                hide_index=True
            )
            st.info(f"共 {len(st.session_state.activities_df)} 条活动记录")
        else:
            st.warning("暂无活动数据，请上传CSV文件")
    
    with tab2:
        st.subheader("签到记录管理")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_sign_ins = st.file_uploader(
                "上传签到记录 CSV 文件",
                type=['csv'],
                key="upload_sign_ins",
                help="CSV文件需包含：sign_in_id, activity_id, volunteer_id, volunteer_name, sign_in_time, sign_out_time, status"
            )
            
            if uploaded_sign_ins is not None:
                try:
                    df = pd.read_csv(uploaded_sign_ins)
                    required_cols = ['sign_in_id', 'activity_id', 'volunteer_id', 
                                   'volunteer_name', 'sign_in_time', 'sign_out_time', 'status']
                    
                    if all(col in df.columns for col in required_cols):
                        if st.button("确认导入签到记录"):
                            st.session_state.sign_ins_df = df
                            save_all_data()
                            st.success(f"成功导入 {len(df)} 条签到记录")
                            st.rerun()
                    else:
                        missing = [col for col in required_cols if col not in df.columns]
                        st.error(f"CSV文件缺少必要字段：{', '.join(missing)}")
                except Exception as e:
                    st.error(f"文件读取失败：{str(e)}")
        
        with col2:
            st.markdown("### 操作说明")
            st.markdown("""
            1. 下载模板文件作为参考
            2. 按照模板格式准备数据
            3. 上传 CSV 文件
            4. 确认导入数据
            """)
            
            template_sign_ins = pd.DataFrame({
                'sign_in_id': ['S001'],
                'activity_id': ['A001'],
                'volunteer_id': ['V001'],
                'volunteer_name': ['张三'],
                'sign_in_time': ['2026-06-08 08:30:00'],
                'sign_out_time': ['2026-06-08 17:00:00'],
                'status': ['已签到']
            })
            
            st.download_button(
                label="📥 下载签到模板",
                data=dataframe_to_csv_bytes(template_sign_ins),
                file_name="sign_ins_template.csv",
                mime="text/csv"
            )
        
        st.markdown("---")
        st.subheader("当前签到记录")
        
        if not st.session_state.sign_ins_df.empty:
            activity_filter = st.selectbox(
                "按活动筛选",
                options=["全部"] + st.session_state.activities_df['activity_id'].tolist() 
                if not st.session_state.activities_df.empty else ["全部"],
                key="signin_activity_filter"
            )
            
            display_df = st.session_state.sign_ins_df
            if activity_filter != "全部":
                display_df = display_df[display_df['activity_id'] == activity_filter]
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )
            st.info(f"共 {len(display_df)} 条签到记录")
        else:
            st.warning("暂无签到数据，请上传CSV文件")
    
    with tab3:
        st.subheader("反馈评分管理")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_feedback = st.file_uploader(
                "上传反馈评分 CSV 文件",
                type=['csv'],
                key="upload_feedback",
                help="CSV文件需包含：feedback_id, activity_id, volunteer_id, rating, comment, feedback_date"
            )
            
            if uploaded_feedback is not None:
                try:
                    df = pd.read_csv(uploaded_feedback)
                    required_cols = ['feedback_id', 'activity_id', 'volunteer_id', 
                                   'rating', 'comment', 'feedback_date']
                    
                    if all(col in df.columns for col in required_cols):
                        if st.button("确认导入反馈评分"):
                            st.session_state.feedback_df = df
                            save_all_data()
                            st.success(f"成功导入 {len(df)} 条反馈评分")
                            st.rerun()
                    else:
                        missing = [col for col in required_cols if col not in df.columns]
                        st.error(f"CSV文件缺少必要字段：{', '.join(missing)}")
                except Exception as e:
                    st.error(f"文件读取失败：{str(e)}")
        
        with col2:
            st.markdown("### 操作说明")
            st.markdown("""
            1. 下载模板文件作为参考
            2. 按照模板格式准备数据
            3. 上传 CSV 文件
            4. 确认导入数据
            """)
            
            template_feedback = pd.DataFrame({
                'feedback_id': ['F001'],
                'activity_id': ['A001'],
                'volunteer_id': ['V001'],
                'rating': [4.5],
                'comment': ['活动组织得很好'],
                'feedback_date': ['2026-06-09']
            })
            
            st.download_button(
                label="📥 下载反馈模板",
                data=dataframe_to_csv_bytes(template_feedback),
                file_name="feedback_template.csv",
                mime="text/csv"
            )
        
        st.markdown("---")
        st.subheader("当前反馈记录")
        
        if not st.session_state.feedback_df.empty:
            activity_filter = st.selectbox(
                "按活动筛选",
                options=["全部"] + st.session_state.activities_df['activity_id'].tolist() 
                if not st.session_state.activities_df.empty else ["全部"],
                key="feedback_activity_filter"
            )
            
            display_df = st.session_state.feedback_df
            if activity_filter != "全部":
                display_df = display_df[display_df['activity_id'] == activity_filter]
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )
            st.info(f"共 {len(display_df)} 条反馈记录")
            
            if len(display_df) > 0:
                avg_rating = round(display_df['rating'].mean(), 2)
                st.metric("平均评分", f"{avg_rating} 分")
        else:
            st.warning("暂无反馈数据，请上传CSV文件")
    
    with tab4:
        st.subheader("数据概览")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("活动总数", len(st.session_state.activities_df))
        with col2:
            st.metric("签到记录数", len(st.session_state.sign_ins_df))
        with col3:
            st.metric("任务总数", len(st.session_state.tasks_df))
        with col4:
            st.metric("反馈数量", len(st.session_state.feedback_df))


def assistant_page():
    st.header("📝 助理工作台")
    
    tab1, tab2 = st.tabs(["📋 任务管理", "💬 反馈管理"])
    
    with tab1:
        st.subheader("任务完成状态更新")
        
        if st.session_state.activities_df.empty:
            st.warning("暂无活动数据，请先由管理员上传活动数据")
            return
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            activity_id = st.selectbox(
                "选择活动",
                options=st.session_state.activities_df['activity_id'].tolist(),
                format_func=lambda x: f"{x} - {st.session_state.activities_df[st.session_state.activities_df['activity_id'] == x]['activity_name'].iloc[0]}"
            )
        
        if activity_id:
            activity_tasks = st.session_state.tasks_df[
                st.session_state.tasks_df['activity_id'] == activity_id
            ].copy()
            
            if activity_tasks.empty:
                st.info("该活动暂无任务")
                
                with st.expander("➕ 添加新任务"):
                    new_task_id = st.text_input("任务ID", value=f"T{len(st.session_state.tasks_df)+1:03d}")
                    new_task_name = st.text_input("任务名称")
                    new_assigned_to = st.text_input("分配给")
                    new_description = st.text_area("任务描述")
                    new_due_date = st.date_input("截止日期")
                    new_status = st.selectbox("状态", ["未开始", "进行中", "已完成"])
                    new_note = st.text_area("完成备注")
                    
                    if st.button("添加任务"):
                        if new_task_name:
                            new_task = pd.DataFrame([{
                                'task_id': new_task_id,
                                'activity_id': activity_id,
                                'task_name': new_task_name,
                                'assigned_to': new_assigned_to,
                                'task_description': new_description,
                                'due_date': new_due_date.strftime('%Y-%m-%d'),
                                'status': new_status,
                                'completion_note': new_note
                            }])
                            
                            st.session_state.tasks_df = pd.concat(
                                [st.session_state.tasks_df, new_task], 
                                ignore_index=True
                            )
                            save_all_data()
                            st.success("任务添加成功")
                            st.rerun()
                        else:
                            st.error("请填写任务名称")
            else:
                st.markdown("### 任务列表")
                
                edited_tasks = st.data_editor(
                    activity_tasks,
                    column_config={
                        "task_id": st.column_config.TextColumn("任务ID", disabled=True),
                        "activity_id": st.column_config.TextColumn("活动ID", disabled=True),
                        "task_name": st.column_config.TextColumn("任务名称"),
                        "assigned_to": st.column_config.TextColumn("分配给"),
                        "task_description": st.column_config.TextColumn("任务描述"),
                        "due_date": st.column_config.TextColumn("截止日期"),
                        "status": st.column_config.SelectboxColumn(
                            "状态",
                            options=["未开始", "进行中", "已完成"]
                        ),
                        "completion_note": st.column_config.TextColumn("完成备注")
                    },
                    use_container_width=True,
                    hide_index=True,
                    num_rows="dynamic"
                )
                
                col_save, col_reset = st.columns(2)
                with col_save:
                    if st.button("💾 保存修改"):
                        other_tasks = st.session_state.tasks_df[
                            st.session_state.tasks_df['activity_id'] != activity_id
                        ]
                        st.session_state.tasks_df = pd.concat(
                            [other_tasks, edited_tasks], 
                            ignore_index=True
                        )
                        save_all_data()
                        st.success("任务状态已保存")
                        st.rerun()
                with col_reset:
                    if st.button("🔄 撤销修改"):
                        st.rerun()
                
                st.markdown("### 任务统计")
                total = len(activity_tasks)
                completed = len(activity_tasks[activity_tasks['status'] == '已完成'])
                in_progress = len(activity_tasks[activity_tasks['status'] == '进行中'])
                not_started = len(activity_tasks[activity_tasks['status'] == '未开始'])
                completion_rate = round(completed / total * 100, 1) if total > 0 else 0
                
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("总任务数", total)
                with c2:
                    st.metric("已完成", completed)
                with c3:
                    st.metric("进行中", in_progress)
                with c4:
                    st.metric("完成率", f"{completion_rate}%")
    
    with tab2:
        st.subheader("反馈评分管理")
        
        if st.session_state.activities_df.empty:
            st.warning("暂无活动数据")
            return
        
        if not st.session_state.feedback_df.empty:
            st.dataframe(
                st.session_state.feedback_df,
                use_container_width=True,
                hide_index=True
            )
            st.info(f"共 {len(st.session_state.feedback_df)} 条反馈记录")
        else:
            st.info("暂无反馈记录")


def supervisor_page():
    st.header("📈 主管报表中心")
    
    if 'report_generated' not in st.session_state:
        st.session_state.report_generated = False
    if 'report_data' not in st.session_state:
        st.session_state.report_data = None
    
    tab1, tab2, tab3 = st.tabs(["📊 周期报表", "⚠️ 风险清单", "🔍 数据筛选"])
    
    with tab1:
        st.subheader("周期报表生成")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            period_type = st.selectbox(
                "报表周期",
                options=["周报", "月报"],
                index=0
            )
            period_type_key = 'week' if period_type == '周报' else 'month'
        
        with col2:
            min_date, max_date = get_date_range(st.session_state.activities_df)
            if min_date and max_date:
                default_date = max_date
            else:
                default_date = date.today()
            
            selected_date = st.date_input(
                "选择日期",
                value=default_date
            )
        
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            generate_report = st.button("📄 生成报告", type="primary", use_container_width=True)
        
        selected_datetime = datetime.combine(selected_date, datetime.min.time())
        current_start, current_end = get_current_period(selected_datetime, period_type_key)
        prev_start, prev_end = get_previous_period(selected_datetime, period_type_key)
        
        st.info(f"**本期**：{current_start.strftime('%Y-%m-%d')} 至 {current_end.strftime('%Y-%m-%d')} | "
                f"**上期**：{prev_start.strftime('%Y-%m-%d')} 至 {prev_end.strftime('%Y-%m-%d')}")
        
        if generate_report:
            current_activities = filter_activities_by_period(
                st.session_state.activities_df, current_start, current_end
            )
            prev_activities = filter_activities_by_period(
                st.session_state.activities_df, prev_start, prev_end
            )
            
            current_stats = calculate_activity_stats(
                current_activities,
                st.session_state.sign_ins_df,
                st.session_state.tasks_df,
                st.session_state.feedback_df
            )
            
            previous_stats = calculate_activity_stats(
                prev_activities,
                st.session_state.sign_ins_df,
                st.session_state.tasks_df,
                st.session_state.feedback_df
            )
            
            comparison = compare_periods(current_stats, previous_stats)
            
            risk_df = get_risk_list(
                current_activities,
                st.session_state.sign_ins_df,
                st.session_state.tasks_df,
                st.session_state.feedback_df
            )
            
            html_report = generate_html_report(
                current_stats,
                previous_stats,
                comparison,
                risk_df,
                current_activities,
                period_type_key,
                selected_datetime
            )
            
            summary_df = generate_summary_table(current_stats, previous_stats, comparison)
            
            st.session_state.report_data = {
                'current_stats': current_stats,
                'previous_stats': previous_stats,
                'comparison': comparison,
                'current_activities': current_activities,
                'risk_df': risk_df,
                'html_report': html_report,
                'summary_df': summary_df,
                'period_type_key': period_type_key,
                'selected_datetime': selected_datetime
            }
            st.session_state.report_generated = True
            st.success("✅ 报告生成成功！")
        
        if st.session_state.report_generated and st.session_state.report_data:
            data = st.session_state.report_data
            current_stats = data['current_stats']
            previous_stats = data['previous_stats']
            comparison = data['comparison']
            current_activities = data['current_activities']
            risk_df = data['risk_df']
            html_report = data['html_report']
            summary_df = data['summary_df']
            period_type_key = data['period_type_key']
            selected_datetime = data['selected_datetime']
            
            st.markdown("---")
            st.subheader("📊 核心指标对比")
            
            cols = st.columns(4)
            
            metric_configs = [
                ("活动数量", 'total_activities', '个'),
                ("报名人数", 'total_registrations', '人'),
                ("签到人数", 'total_sign_ins', '人'),
                ("签到率", 'sign_in_rate', '%'),
            ]
            
            for i, (label, key, unit) in enumerate(metric_configs):
                with cols[i % 4]:
                    value = current_stats[key]
                    diff = comparison[f'{key}_diff']
                    
                    if key in ['sign_in_rate', 'task_completion_rate', 'avg_rating']:
                        delta_str = f"{diff:+.2f}{unit}"
                        value_str = f"{value}{unit}"
                    else:
                        pct = comparison[f'{key}_pct']
                        delta_str = f"{diff:+d} ({pct:+.1f}%)"
                        value_str = f"{value}{unit}"
                    
                    st.metric(
                        label=label,
                        value=value_str,
                        delta=delta_str,
                        delta_color="normal"
                    )
            
            cols2 = st.columns(4)
            
            metric_configs2 = [
                ("任务总数", 'total_tasks', '个'),
                ("任务完成率", 'task_completion_rate', '%'),
                ("平均评分", 'avg_rating', '分'),
                ("反馈数量", 'feedback_count', '条'),
            ]
            
            for i, (label, key, unit) in enumerate(metric_configs2):
                with cols2[i % 4]:
                    value = current_stats[key]
                    diff = comparison[f'{key}_diff']
                    
                    if key in ['sign_in_rate', 'task_completion_rate', 'avg_rating']:
                        delta_str = f"{diff:+.2f}{unit}"
                        value_str = f"{value}{unit}"
                    else:
                        pct = comparison[f'{key}_pct']
                        delta_str = f"{diff:+d} ({pct:+.1f}%)"
                        value_str = f"{value}{unit}"
                    
                    st.metric(
                        label=label,
                        value=value_str,
                        delta=delta_str,
                        delta_color="normal"
                    )
            
            st.markdown("---")
            st.subheader("📋 本期活动列表")
            
            if not current_activities.empty:
                st.dataframe(
                    current_activities,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("本期暂无活动数据")
            
            st.markdown("---")
            st.subheader("📥 报告下载")
            
            col_html, col_csv = st.columns(2)
            
            with col_html:
                st.download_button(
                    label="📄 下载 HTML 报告",
                    data=html_report,
                    file_name=get_report_filename(period_type_key, selected_datetime, 'html'),
                    mime="text/html",
                    use_container_width=True
                )
            
            with col_csv:
                st.download_button(
                    label="📊 下载统计表格 (CSV)",
                    data=dataframe_to_csv_bytes(summary_df),
                    file_name=get_report_filename(period_type_key, selected_datetime, 'csv'),
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.info("👆 请选择报表周期和日期，点击「生成报告」按钮查看报表")
    
    with tab2:
        st.subheader("⚠️ 风险提醒清单")
        
        risk_df = get_risk_list(
            st.session_state.activities_df,
            st.session_state.sign_ins_df,
            st.session_state.tasks_df,
            st.session_state.feedback_df
        )
        
        if risk_df.empty:
            st.success("🎉 暂无风险项目，一切正常！")
        else:
            high_risk = risk_df[risk_df['risk_level'] == '高']
            medium_risk = risk_df[risk_df['risk_level'] == '中']
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("总风险项", len(risk_df))
            with c2:
                st.metric("高风险", len(high_risk), delta_color="inverse")
            with c3:
                st.metric("中风险", len(medium_risk), delta_color="off")
            
            st.markdown("---")
            
            risk_level_filter = st.multiselect(
                "按风险等级筛选",
                options=["高", "中"],
                default=["高", "中"]
            )
            
            filtered_risk = risk_df[risk_df['risk_level'].isin(risk_level_filter)]
            
            st.dataframe(
                filtered_risk,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "risk_level": st.column_config.Column(
                        "风险等级",
                        width="small"
                    )
                }
            )
            
            st.download_button(
                label="📥 下载风险清单",
                data=dataframe_to_csv_bytes(filtered_risk),
                file_name="risk_list.csv",
                mime="text/csv"
            )
    
    with tab3:
        st.subheader("🔍 数据筛选分析")
        
        col1, col2 = st.columns(2)
        
        with col1:
            person_list = get_person_list(st.session_state.activities_df)
            selected_persons = st.multiselect(
                "按负责人筛选",
                options=person_list,
                default=person_list
            )
        
        with col2:
            activity_list = get_activity_list(st.session_state.activities_df)
            activity_options = [f"{aid} - {aname}" for aid, aname in activity_list]
            selected_activity_labels = st.multiselect(
                "按活动筛选",
                options=activity_options,
                default=[]
            )
            selected_activity_ids = [label.split(" - ")[0] for label in selected_activity_labels]
        
        min_date, max_date = get_date_range(st.session_state.activities_df)
        if min_date and max_date:
            date_range = st.date_input(
                "选择日期范围",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )
            if len(date_range) == 2:
                start_date = datetime.combine(date_range[0], datetime.min.time())
                end_date = datetime.combine(date_range[1], datetime.max.time())
            else:
                start_date = end_date = None
        else:
            start_date = end_date = None
        
        filtered_activities, filtered_sign_ins, filtered_tasks, filtered_feedback = filter_data_by_criteria(
            st.session_state.activities_df,
            st.session_state.sign_ins_df,
            st.session_state.tasks_df,
            st.session_state.feedback_df,
            activity_filter=selected_activity_ids if selected_activity_ids else None,
            person_filter=selected_persons if selected_persons else None,
            date_range=(start_date, end_date) if start_date and end_date else None
        )
        
        st.markdown("---")
        st.subheader("📊 筛选结果统计")
        
        stats = calculate_activity_stats(
            filtered_activities,
            filtered_sign_ins,
            filtered_tasks,
            filtered_feedback
        )
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("活动数量", stats['total_activities'])
        with c2:
            st.metric("报名人数", stats['total_registrations'])
        with c3:
            st.metric("签到率", f"{stats['sign_in_rate']}%")
        with c4:
            st.metric("任务完成率", f"{stats['task_completion_rate']}%")
        
        c5, c6, c7, c8 = st.columns(4)
        with c5:
            st.metric("任务总数", stats['total_tasks'])
        with c6:
            st.metric("已完成任务", stats['completed_tasks'])
        with c7:
            st.metric("平均评分", stats['avg_rating'])
        with c8:
            st.metric("反馈数量", stats['feedback_count'])
        
        st.markdown("---")
        st.subheader("📋 筛选结果详情")
        
        detail_tab1, detail_tab2, detail_tab3, detail_tab4 = st.tabs(
            ["活动列表", "签到记录", "任务列表", "反馈评分"]
        )
        
        with detail_tab1:
            if not filtered_activities.empty:
                st.dataframe(filtered_activities, use_container_width=True, hide_index=True)
            else:
                st.info("暂无数据")
        
        with detail_tab2:
            if not filtered_sign_ins.empty:
                st.dataframe(filtered_sign_ins, use_container_width=True, hide_index=True)
            else:
                st.info("暂无数据")
        
        with detail_tab3:
            if not filtered_tasks.empty:
                st.dataframe(filtered_tasks, use_container_width=True, hide_index=True)
            else:
                st.info("暂无数据")
        
        with detail_tab4:
            if not filtered_feedback.empty:
                st.dataframe(filtered_feedback, use_container_width=True, hide_index=True)
            else:
                st.info("暂无数据")


def main():
    init_session_state()
    render_sidebar()
    
    if not st.session_state.role:
        st.title("📊 志愿服务报表系统")
        st.markdown("---")
        
        st.markdown("### 欢迎使用志愿服务报表系统！")
        st.markdown("""
        本系统用于分析志愿服务的报名、签到、任务完成、反馈评分和风险提醒。
        
        **主要功能：**
        - 👤 **管理员**：上传活动与签到记录
        - ✍️ **助理**：补充任务完成状态
        - 📊 **主管**：查看周期报告和风险清单
        
        请在左侧选择您的角色开始使用。
        """)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info("🔧 **管理员**\n\n负责上传活动数据和签到记录，管理基础数据。")
        
        with col2:
            st.info("📝 **助理**\n\n负责补充和更新任务完成状态，跟踪任务进度。")
        
        with col3:
            st.info("📈 **主管**\n\n负责查看周期报表、风险清单，进行数据分析和决策。")
        
        st.markdown("---")
        st.subheader("📊 系统数据概览")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("活动总数", len(st.session_state.activities_df))
        with col2:
            st.metric("签到记录", len(st.session_state.sign_ins_df))
        with col3:
            st.metric("任务总数", len(st.session_state.tasks_df))
        with col4:
            st.metric("反馈数量", len(st.session_state.feedback_df))
    
    else:
        if st.session_state.role == "管理员":
            admin_page()
        elif st.session_state.role == "助理":
            assistant_page()
        elif st.session_state.role == "主管":
            supervisor_page()


if __name__ == "__main__":
    main()
