import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import base64
from pathlib import Path
import hashlib

# Page configuration
st.set_page_config(
    page_title="Biometric Device Monitor Pro",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem;
        font-weight: bold;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        transition: transform 0.3s;
    }
    .metric-card:hover {
        transform: translateY(-5px);
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'summary_data' not in st.session_state:
    st.session_state.summary_data = None
if 'processing_history' not in st.session_state:
    st.session_state.processing_history = []
if 'alerts_config' not in st.session_state:
    st.session_state.alerts_config = {
        'inactive_threshold': 30,
        'email_alerts': False,
        'email_recipient': ''
    }
if 'saved_reports' not in st.session_state:
    st.session_state.saved_reports = []

# Title
st.markdown('<div class="main-header">🏢 Biometric Device Monitoring System PRO</div>', unsafe_allow_html=True)
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("📁 Data Upload")
    
    portal_file = st.file_uploader(
        "**Device Export File** (Excel)",
        type=['xlsx', 'xls'],
        help="Required columns: 'Serial Number', 'Last Activity'"
    )
    
    master_file = st.file_uploader(
        "**Biometric Master File** (Excel)",
        type=['xlsx', 'xls'],
        help="Required columns: 'Serial Number', 'Area', 'Ward'"
    )
    
    st.markdown("---")
    
    with st.expander("⚙️ **Advanced Settings**", expanded=False):
        active_days = st.number_input("Active Days Threshold", min_value=1, max_value=30, value=2)
        st.session_state.alerts_config['inactive_threshold'] = st.slider(
            "Inactive Alert Threshold (days)", 
            min_value=7, max_value=90, value=30
        )
    
    process_button = st.button("🚀 **Process Data**", type="primary", use_container_width=True)
    
    st.markdown("---")
    
    with st.expander("📋 **Status Rules**", expanded=False):
        st.markdown(f"""
        1. **Ward NULL** → Status = Area value
        2. **Days ≤ {active_days} & Area ≠ 'Not Authorized'** → ✅ Active
        3. **Days > {active_days} & Area ≠ 'Not Authorized'** → ⚠️ Inactive
        4. **Area = 'Not Authorized'** → 🚫 Blocked
        """)
    
    # Export Section
    if st.session_state.processed_data is not None:
        st.markdown("---")
        st.header("📥 Export Options")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📄 CSV", use_container_width=True):
                csv = st.session_state.processed_data.to_csv(index=False)
                b64 = base64.b64encode(csv.encode()).decode()
                href = f'<a href="data:file/csv;base64,{b64}" download="biometric_report.csv">Download CSV</a>'
                st.markdown(href, unsafe_allow_html=True)
        
        with col2:
            if st.button("📊 Excel", use_container_width=True):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    st.session_state.processed_data.to_excel(writer, sheet_name='Processed Data', index=False)
                    if st.session_state.summary_data is not None:
                        st.session_state.summary_data.to_excel(writer, sheet_name='Summary', index=False)
                excel_data = output.getvalue()
                b64 = base64.b64encode(excel_data).decode()
                href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="biometric_report.xlsx">Download Excel</a>'
                st.markdown(href, unsafe_allow_html=True)

# Processing function
def process_biometric_data(portal_file, master_file, active_threshold=2):
    try:
        portal_df = pd.read_excel(portal_file)
        try:
            master_df = pd.read_excel(master_file, sheet_name="Master")
        except:
            master_df = pd.read_excel(master_file)
        
        def find_serial_column(df):
            for col in df.columns:
                col_lower = col.lower()
                if 'serial' in col_lower or 's/no' in col_lower or 'device' in col_lower or 'sl no' in col_lower:
                    return col
            return None
        
        portal_serial_col = find_serial_column(portal_df)
        master_serial_col = find_serial_column(master_df)
        
        if portal_serial_col is None or master_serial_col is None:
            st.error("❌ Could not find 'Serial Number' column!")
            return None, None
        
        if portal_serial_col != 'Serial Number':
            portal_df = portal_df.rename(columns={portal_serial_col: 'Serial Number'})
        if master_serial_col != 'Serial Number':
            master_df = master_df.rename(columns={master_serial_col: 'Serial Number'})
        
        merged = master_df.merge(portal_df, on="Serial Number", how="left")
        
        last_activity_col = None
        for col in merged.columns:
            col_lower = col.lower()
            if 'last' in col_lower and ('activity' in col_lower or 'login' in col_lower or 'used' in col_lower):
                last_activity_col = col
                break
        
        if last_activity_col is None:
            st.error("❌ Could not find 'Last Activity' column!")
            return None, None
        
        merged['Last Activity Date'] = pd.to_datetime(merged[last_activity_col], errors='coerce')
        
        max_date = merged['Last Activity Date'].max()
        if pd.isna(max_date):
            merged['Days Inactive'] = 0
        else:
            merged['Days Inactive'] = (max_date - merged['Last Activity Date']).dt.days
            merged['Days Inactive'] = merged['Days Inactive'].fillna(0)
        
        def determine_status(row):
            ward = row.get('Ward', '')
            ward_null = pd.isna(ward) or str(ward).strip() == '' or str(ward).strip().lower() == 'nan'
            
            if ward_null:
                area_val = row.get('Area', 'Unknown')
                return str(area_val) if not pd.isna(area_val) else 'Unknown'
            
            area = str(row.get('Area', '')).strip()
            days = row.get('Days Inactive', 0)
            
            if area == 'Not Authorized':
                return '🚫 Blocked'
            elif days <= active_threshold:
                return '✅ Active'
            else:
                return '⚠️ Inactive'
        
        merged['Status'] = merged.apply(determine_status, axis=1)
        
        summary = merged['Status'].value_counts().reset_index()
        summary.columns = ['Status', 'Count']
        summary['Percentage'] = (summary['Count'] / summary['Count'].sum() * 100).round(1)
        
        display_cols = ['Serial Number', 'Days Inactive', 'Status']
        if 'Area' in merged.columns:
            display_cols.insert(1, 'Area')
        if 'Ward' in merged.columns:
            display_cols.insert(2, 'Ward')
        if last_activity_col:
            display_cols.append(last_activity_col)
        
        result_df = merged[display_cols].copy()
        result_df['Processed'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return result_df, summary
        
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        return None, None

# Process button
if process_button:
    if portal_file is None or master_file is None:
        st.warning("⚠️ Please upload both files!")
    else:
        with st.spinner("🔄 Processing..."):
            processed_df, summary_df = process_biometric_data(portal_file, master_file, active_days)
            
            if processed_df is not None:
                st.session_state.processed_data = processed_df
                st.session_state.summary_data = summary_df
                
                st.session_state.processing_history.append({
                    'timestamp': datetime.now(),
                    'total_devices': len(processed_df),
                    'file_name': portal_file.name,
                    'active_count': len(processed_df[processed_df['Status'] == '✅ Active']),
                    'inactive_count': len(processed_df[processed_df['Status'] == '⚠️ Inactive']),
                    'blocked_count': len(processed_df[processed_df['Status'] == '🚫 Blocked'])
                })
                
                # Alert check
                inactive_devices = processed_df[processed_df['Status'] == '⚠️ Inactive']
                long_inactive = inactive_devices[inactive_devices['Days Inactive'] > st.session_state.alerts_config['inactive_threshold']]
                
                if len(long_inactive) > 0:
                    st.warning(f"⚠️ Alert: {len(long_inactive)} devices inactive > {st.session_state.alerts_config['inactive_threshold']} days!")
                
                st.success("✅ Processing complete!")
                st.balloons()

# Main content - ALL TABS WORKING
if st.session_state.processed_data is not None:
    df = st.session_state.processed_data
    summary = st.session_state.summary_data
    
    # Create ALL 5 tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Dashboard", "📋 Device Data", "📈 Analytics", "📜 History", "💾 Saved Reports"])
    
    # ==================== TAB 1: DASHBOARD ====================
    with tab1:
        # KPI Cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_devices = len(df)
            st.metric("📊 Total Devices", total_devices)
        
        with col2:
            active_count = len(df[df['Status'] == '✅ Active'])
            active_pct = (active_count/total_devices*100) if total_devices > 0 else 0
            st.metric("✅ Active", f"{active_count}", delta=f"{active_pct:.1f}%")
        
        with col3:
            inactive_count = len(df[df['Status'] == '⚠️ Inactive'])
            inactive_pct = (inactive_count/total_devices*100) if total_devices > 0 else 0
            st.metric("⚠️ Inactive", f"{inactive_count}", delta=f"{inactive_pct:.1f}%", delta_color="inverse")
        
        with col4:
            blocked_count = len(df[df['Status'] == '🚫 Blocked'])
            blocked_pct = (blocked_count/total_devices*100) if total_devices > 0 else 0
            st.metric("🚫 Blocked", f"{blocked_count}", delta=f"{blocked_pct:.1f}%")
        
        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Status Distribution")
            fig1 = px.pie(summary, values='Count', names='Status', hole=0.3, 
                          color_discrete_sequence=['#2ecc71', '#e74c3c', '#95a5a6', '#3498db'])
            fig1.update_traces(textposition='inside', textinfo='percent+label')
            fig1.update_layout(height=400)
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            st.subheader("Inactive Days Distribution")
            df['Days Group'] = pd.cut(df['Days Inactive'], bins=[-1, 0, 2, 7, 30, 90, float('inf')],
                                       labels=['0', '1-2', '3-7', '8-30', '31-90', '90+'])
            days_dist = df['Days Group'].value_counts().reset_index()
            days_dist.columns = ['Days', 'Count']
            fig2 = px.bar(days_dist, x='Days', y='Count', title='Devices by Inactive Days',
                          color='Count', color_continuous_scale='Viridis')
            fig2.update_layout(height=400)
            st.plotly_chart(fig2, use_container_width=True)
        
        # Additional metrics
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            avg_inactive = df['Days Inactive'].mean()
            st.metric("📊 Avg Inactive Days", f"{avg_inactive:.1f}")
        with col2:
            max_inactive = df['Days Inactive'].max()
            st.metric("⚠️ Max Inactive Days", f"{max_inactive}")
        with col3:
            compliance_rate = (active_count / total_devices * 100) if total_devices > 0 else 0
            st.metric("✅ Compliance Rate", f"{compliance_rate:.1f}%")
    
    # ==================== TAB 2: DEVICE DATA ====================
    with tab2:
        st.subheader("Detailed Device Data")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.multiselect("Filter by Status", options=df['Status'].unique(), 
                                           default=df['Status'].unique(), key="filter1")
        with col2:
            if 'Area' in df.columns:
                area_filter = st.multiselect("Filter by Area", options=df['Area'].unique(), 
                                             default=df['Area'].unique(), key="filter2")
            else:
                area_filter = []
        with col3:
            search = st.text_input("🔍 Search Serial Number", placeholder="Enter serial...")
        
        # Apply filters
        filtered_df = df[df['Status'].isin(status_filter)]
        if area_filter:
            filtered_df = filtered_df[filtered_df['Area'].isin(area_filter)]
        if search:
            filtered_df = filtered_df[filtered_df['Serial Number'].astype(str).str.contains(search, case=False)]
        
        # Color coding function
        def color_status(val):
            if '✅' in str(val):
                return 'background-color: #90EE90'
            elif '⚠️' in str(val):
                return 'background-color: #FFB6C1'
            elif '🚫' in str(val):
                return 'background-color: #D3D3D3'
            return ''
        
        styled_df = filtered_df.style.map(color_status, subset=['Status'])
        st.dataframe(styled_df, width='stretch', height=500)
        st.caption(f"Showing {len(filtered_df)} of {len(df)} records")
        
        # Export filtered data
        if st.button("📥 Export Filtered Data"):
            csv = filtered_df.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="filtered_data.csv">Download CSV</a>'
            st.markdown(href, unsafe_allow_html=True)
        
        # Top inactive
        st.markdown("---")
        st.subheader("⚠️ Top 10 Most Inactive Devices")
        top_inactive = df.nlargest(10, 'Days Inactive')[['Serial Number', 'Days Inactive', 'Status']]
        if 'Area' in df.columns:
            top_inactive.insert(1, 'Area', df.loc[top_inactive.index, 'Area'])
        st.dataframe(top_inactive, width='stretch')
    
    # ==================== TAB 3: ANALYTICS ====================
    with tab3:
        st.subheader("Advanced Analytics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Status by Area")
            if 'Area' in df.columns:
                area_status = pd.crosstab(df['Area'], df['Status'])
                fig3 = px.imshow(area_status, text_auto=True, aspect="auto", 
                                 title="Heatmap: Status by Area", color_continuous_scale='Viridis')
                fig3.update_layout(height=500)
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.info("Area column not available")
        
        with col2:
            st.markdown("#### Status Trends")
            if len(st.session_state.processing_history) > 1:
                history_df = pd.DataFrame(st.session_state.processing_history)
                history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
                history_df = history_df.sort_values('timestamp')
                
                fig4 = px.line(history_df, x='timestamp', y=['active_count', 'inactive_count', 'blocked_count'],
                               title='Device Status Trends', labels={'value': 'Count', 'timestamp': 'Date'},
                               color_discrete_map={'active_count': '#2ecc71', 'inactive_count': '#e74c3c', 'blocked_count': '#95a5a6'})
                fig4.update_layout(height=500)
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info("Process more files to see trends (need at least 2 reports)")
        
        # Cumulative distribution
        st.markdown("#### Cumulative Distribution")
        df_sorted = df.sort_values('Days Inactive')
        df_sorted['Cumulative %'] = (df_sorted.index + 1) / len(df_sorted) * 100
        
        fig5 = px.line(df_sorted, x='Days Inactive', y='Cumulative %', 
                       title='Cumulative Distribution of Inactive Days')
        fig5.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="80%")
        fig5.add_hline(y=95, line_dash="dash", line_color="orange", annotation_text="95%")
        fig5.update_layout(height=400)
        st.plotly_chart(fig5, use_container_width=True)
        
        # Statistics table
        st.markdown("#### Statistical Summary")
        stats_df = pd.DataFrame({
            'Metric': ['Mean Inactive Days', 'Median Inactive Days', 'Std Deviation', 'Min Days', 'Max Days'],
            'Value': [
                f"{df['Days Inactive'].mean():.1f}",
                f"{df['Days Inactive'].median():.1f}",
                f"{df['Days Inactive'].std():.1f}",
                f"{df['Days Inactive'].min()}",
                f"{df['Days Inactive'].max()}"
            ]
        })
        st.dataframe(stats_df, width='stretch')
    
    # ==================== TAB 4: HISTORY ====================
    with tab4:
        st.subheader("Processing History")
        
        if st.session_state.processing_history:
            history_df = pd.DataFrame(st.session_state.processing_history)
            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
            history_df = history_df.sort_values('timestamp', ascending=False)
            
            display_history = history_df[['timestamp', 'file_name', 'total_devices', 'active_count', 'inactive_count', 'blocked_count']].copy()
            display_history.columns = ['Date & Time', 'File Name', 'Total', 'Active', 'Inactive', 'Blocked']
            st.dataframe(display_history, width='stretch')
            
            # Compare reports
            if len(st.session_state.processing_history) >= 2:
                st.markdown("---")
                st.subheader("Compare Reports")
                
                col1, col2 = st.columns(2)
                with col1:
                    idx1 = st.selectbox("First Report", range(len(st.session_state.processing_history)), 
                                        format_func=lambda x: st.session_state.processing_history[x]['timestamp'].strftime('%Y-%m-%d %H:%M'))
                with col2:
                    idx2 = st.selectbox("Second Report", range(len(st.session_state.processing_history)), 
                                        format_func=lambda x: st.session_state.processing_history[x]['timestamp'].strftime('%Y-%m-%d %H:%M'),
                                        index=min(1, len(st.session_state.processing_history)-1))
                
                if idx1 != idx2:
                    r1 = st.session_state.processing_history[idx1]
                    r2 = st.session_state.processing_history[idx2]
                    
                    comparison = pd.DataFrame({
                        'Metric': ['Total', 'Active', 'Inactive', 'Blocked'],
                        r1['timestamp'].strftime('%Y-%m-%d'): [r1['total_devices'], r1['active_count'], r1['inactive_count'], r1['blocked_count']],
                        r2['timestamp'].strftime('%Y-%m-%d'): [r2['total_devices'], r2['active_count'], r2['inactive_count'], r2['blocked_count']],
                        'Change': [
                            r2['total_devices'] - r1['total_devices'],
                            r2['active_count'] - r1['active_count'],
                            r2['inactive_count'] - r1['inactive_count'],
                            r2['blocked_count'] - r1['blocked_count']
                        ]
                    })
                    st.dataframe(comparison, width='stretch')
        else:
            st.info("No processing history yet. Process some data to see history here!")
    
    # ==================== TAB 5: SAVED REPORTS ====================
    with tab5:
        st.subheader("Saved Reports")
        
        # Save current report button
        if st.button("💾 Save Current Report"):
            report_name = f"Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.session_state.saved_reports.append({
                'name': report_name,
                'date': datetime.now(),
                'data': st.session_state.processed_data.copy(),
                'summary': st.session_state.summary_data.copy() if st.session_state.summary_data is not None else None
            })
            st.success(f"Report '{report_name}' saved!")
            st.rerun()
        
        st.markdown("---")
        
        if st.session_state.saved_reports:
            for idx, report in enumerate(reversed(st.session_state.saved_reports)):
                with st.expander(f"📄 {report['name']} - {report['date'].strftime('%Y-%m-%d %H:%M:%S')}"):
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Devices", len(report['data']))
                    with col2:
                        active = len(report['data'][report['data']['Status'] == '✅ Active'])
                        st.metric("Active", active)
                    with col3:
                        inactive = len(report['data'][report['data']['Status'] == '⚠️ Inactive'])
                        st.metric("Inactive", inactive)
                    with col4:
                        blocked = len(report['data'][report['data']['Status'] == '🚫 Blocked'])
                        st.metric("Blocked", blocked)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"📊 Load Report", key=f"load_{idx}"):
                            st.session_state.processed_data = report['data']
                            st.session_state.summary_data = report['summary']
                            st.success("Report loaded!")
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ Delete Report", key=f"del_{idx}"):
                            st.session_state.saved_reports.pop(len(st.session_state.saved_reports) - 1 - idx)
                            st.rerun()
        else:
            st.info("No saved reports. Click 'Save Current Report' to store the current analysis!")

else:
    # Welcome screen
    st.info("""
    ### 👋 Welcome to Biometric Device Monitoring System PRO!
    
    **Get started:**
    1. Upload your **Device Export File** (Excel with Serial Number & Last Activity)
    2. Upload your **Biometric Master File** (Excel with Serial Number, Area, Ward)
    3. Click **Process Data** button
    
    **Features:**
    - ✅ Interactive Dashboard with KPI cards
    - 📋 Sortable and filterable device data
    - 📈 Advanced analytics and trends
    - 📜 Processing history with comparisons
    - 💾 Save and load reports
    - 📥 Export to CSV/Excel
    """)

# Footer
st.markdown("---")
st.markdown(
    f"<p style='text-align: center; color: gray;'>🏢 Biometric Device Monitor PRO | v3.0 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
    unsafe_allow_html=True
)
