import pandas as pd
from datetime import datetime
from typing import Dict, Optional
import io


def generate_html_report(current_stats: Dict,
                          previous_stats: Dict,
                          comparison: Dict,
                          risk_df: pd.DataFrame,
                          activities_df: pd.DataFrame,
                          period_type: str = 'week',
                          period_date: Optional[datetime] = None) -> str:
    if period_date is None:
        period_date = datetime.now()
    
    period_label = '周报' if period_type == 'week' else '月报'
    period_str = period_date.strftime('%Y年%m月%d日')
    
    html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>志愿服务{period_label} - {period_str}</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background-color: #f5f7fa;
                color: #333;
                padding: 20px;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 12px;
                margin-bottom: 30px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .header h1 {{
                font-size: 28px;
                margin-bottom: 10px;
            }}
            .header .date {{
                font-size: 16px;
                opacity: 0.9;
            }}
            .section {{
                background: white;
                border-radius: 12px;
                padding: 24px;
                margin-bottom: 24px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
            }}
            .section h2 {{
                font-size: 20px;
                color: #1a1a1a;
                margin-bottom: 20px;
                padding-bottom: 12px;
                border-bottom: 2px solid #f0f0f0;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }}
            .stat-card {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                border-left: 4px solid #667eea;
            }}
            .stat-card .label {{
                font-size: 14px;
                color: #666;
                margin-bottom: 8px;
            }}
            .stat-card .value {{
                font-size: 28px;
                font-weight: bold;
                color: #1a1a1a;
                margin-bottom: 6px;
            }}
            .stat-card .change {{
                font-size: 13px;
            }}
            .change.positive {{
                color: #10b981;
            }}
            .change.negative {{
                color: #ef4444;
            }}
            .change.neutral {{
                color: #6b7280;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 16px;
            }}
            table th,
            table td {{
                padding: 12px 16px;
                text-align: left;
                border-bottom: 1px solid #f0f0f0;
            }}
            table th {{
                background-color: #f8f9fa;
                font-weight: 600;
                color: #374151;
                font-size: 14px;
            }}
            table td {{
                font-size: 14px;
                color: #4b5563;
            }}
            table tr:hover {{
                background-color: #f9fafb;
            }}
            .risk-high {{
                background-color: #fef2f2;
                color: #dc2626;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 500;
            }}
            .risk-medium {{
                background-color: #fffbeb;
                color: #d97706;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 500;
            }}
            .risk-low {{
                background-color: #f0fdf4;
                color: #16a34a;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 500;
            }}
            .activity-list {{
                list-style: none;
            }}
            .activity-item {{
                padding: 16px;
                border-bottom: 1px solid #f0f0f0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .activity-item:last-child {{
                border-bottom: none;
            }}
            .activity-info h3 {{
                font-size: 16px;
                color: #1f2937;
                margin-bottom: 4px;
            }}
            .activity-info p {{
                font-size: 13px;
                color: #6b7280;
            }}
            .activity-meta {{
                text-align: right;
            }}
            .activity-meta .date {{
                font-size: 13px;
                color: #9ca3af;
            }}
            .footer {{
                text-align: center;
                padding: 20px;
                color: #9ca3af;
                font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>志愿服务{period_label}</h1>
                <div class="date">报告生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}</div>
            </div>
            
            <div class="section">
                <h2>核心指标概览</h2>
                <div class="stats-grid">
    """
    
    stats_info = [
        ('total_activities', '活动数量', '个'),
        ('total_registrations', '报名人数', '人'),
        ('total_sign_ins', '签到人数', '人'),
        ('sign_in_rate', '签到率', '%'),
        ('total_tasks', '任务总数', '个'),
        ('task_completion_rate', '任务完成率', '%'),
        ('avg_rating', '平均评分', '分'),
        ('feedback_count', '反馈数量', '条')
    ]
    
    for key, label, unit in stats_info:
        value = current_stats.get(key, 0)
        diff_key = f'{key}_diff'
        diff = comparison.get(diff_key, 0)
        
        if key in ['sign_in_rate', 'task_completion_rate', 'avg_rating']:
            value_str = f'{value}{unit}'
            diff_str = f'{diff:+.2f}{unit}'
        else:
            value_str = f'{value}{unit}'
            pct_key = f'{key}_pct'
            pct = comparison.get(pct_key, 0)
            diff_str = f'{diff:+d} ({pct:+.1f}%)'
        
        if diff > 0:
            change_class = 'positive'
            change_icon = '↑'
        elif diff < 0:
            change_class = 'negative'
            change_icon = '↓'
        else:
            change_class = 'neutral'
            change_icon = '→'
        
        html += f"""
                    <div class="stat-card">
                        <div class="label">{label}</div>
                        <div class="value">{value_str}</div>
                        <div class="change {change_class}">{change_icon} 较上期 {diff_str}</div>
                    </div>
        """
    
    html += """
                </div>
            </div>
    """
    
    if not risk_df.empty:
        html += f"""
            <div class="section">
                <h2>风险提醒清单（共{len(risk_df)}项）</h2>
                <table>
                    <thead>
                        <tr>
                            <th>活动ID</th>
                            <th>活动名称</th>
                            <th>风险类型</th>
                            <th>风险等级</th>
                            <th>描述</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for _, risk in risk_df.iterrows():
            risk_class = 'risk-high' if risk['risk_level'] == '高' else 'risk-medium'
            html += f"""
                        <tr>
                            <td>{risk['activity_id']}</td>
                            <td>{risk['activity_name']}</td>
                            <td>{risk['risk_type']}</td>
                            <td><span class="{risk_class}">{risk['risk_level']}</span></td>
                            <td>{risk['description']}</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
            </div>
        """
    
    if not activities_df.empty:
        html += f"""
            <div class="section">
                <h2>本期活动列表（共{len(activities_df)}个活动）</h2>
                <table>
                    <thead>
                        <tr>
                            <th>活动ID</th>
                            <th>活动名称</th>
                            <th>活动日期</th>
                            <th>地点</th>
                            <th>负责人</th>
                            <th>报名人数</th>
                            <th>活动类型</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for _, activity in activities_df.iterrows():
            activity_date = pd.to_datetime(activity['activity_date']).strftime('%Y-%m-%d')
            html += f"""
                        <tr>
                            <td>{activity['activity_id']}</td>
                            <td>{activity['activity_name']}</td>
                            <td>{activity_date}</td>
                            <td>{activity['location']}</td>
                            <td>{activity['person_in_charge']}</td>
                            <td>{activity['registration_count']}</td>
                            <td>{activity['activity_type']}</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
            </div>
        """
    
    html += f"""
            <div class="footer">
                本报告由志愿服务报表系统自动生成 | {datetime.now().strftime('%Y年%m月%d日')}
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
    return csv_buffer.getvalue().encode('utf-8-sig')


def get_report_filename(period_type: str, period_date: datetime, format_type: str = 'html') -> str:
    period_label = 'weekly' if period_type == 'week' else 'monthly'
    date_str = period_date.strftime('%Y%m%d')
    return f'volunteer_{period_label}_report_{date_str}.{format_type}'


def generate_summary_table(current_stats: Dict, 
                            previous_stats: Dict, 
                            comparison: Dict) -> pd.DataFrame:
    data = [
        {'指标': '活动数量', '本期': current_stats['total_activities'], 
         '上期': previous_stats['total_activities'], 
         '变化量': comparison['total_activities_diff'],
         '变化率(%)': comparison['total_activities_pct']},
        {'指标': '报名人数', '本期': current_stats['total_registrations'],
         '上期': previous_stats['total_registrations'],
         '变化量': comparison['total_registrations_diff'],
         '变化率(%)': comparison['total_registrations_pct']},
        {'指标': '签到人数', '本期': current_stats['total_sign_ins'],
         '上期': previous_stats['total_sign_ins'],
         '变化量': comparison['total_sign_ins_diff'],
         '变化率(%)': comparison['total_sign_ins_pct']},
        {'指标': '签到率(%)', '本期': current_stats['sign_in_rate'],
         '上期': previous_stats['sign_in_rate'],
         '变化量': comparison['sign_in_rate_diff'],
         '变化率(%)': '-'},
        {'指标': '任务总数', '本期': current_stats['total_tasks'],
         '上期': previous_stats['total_tasks'],
         '变化量': comparison['total_tasks_diff'],
         '变化率(%)': comparison['total_tasks_pct']},
        {'指标': '任务完成率(%)', '本期': current_stats['task_completion_rate'],
         '上期': previous_stats['task_completion_rate'],
         '变化量': comparison['task_completion_rate_diff'],
         '变化率(%)': '-'},
        {'指标': '平均评分', '本期': current_stats['avg_rating'],
         '上期': previous_stats['avg_rating'],
         '变化量': comparison['avg_rating_diff'],
         '变化率(%)': '-'},
        {'指标': '反馈数量', '本期': current_stats['feedback_count'],
         '上期': previous_stats['feedback_count'],
         '变化量': comparison['feedback_count_diff'],
         '变化率(%)': comparison['feedback_count_pct']}
    ]
    
    return pd.DataFrame(data)
