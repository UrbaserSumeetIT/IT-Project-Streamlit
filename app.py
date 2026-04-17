import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import base64
from pathlib import Path
import hashlib
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import seaborn as sns

# Check if kaleido is available for Plotly image export
try:
    import kaleido
    KALEIDO_AVAILABLE = True
except ImportError:
    KALEIDO_AVAILABLE = False

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

# Function to safely export Plotly chart as image
def export_plotly_as_image(fig, filename, format="png", width=800, height=500, scale=2):
    """Safely export Plotly chart as image with fallback message"""
    if KALEIDO_AVAILABLE:
        try:
            img_bytes = fig.to_image(format=format, width=width, height=height, scale=scale)
            b64 = base64.b64encode(img_bytes).decode()
            href = f'<a href="data:image/{format};base64,{b64}" download="{filename}">Click here to download</a>'
            return href
        except Exception as e:
            return f"<span style='color:red'>Error exporting image: {str(e)}</span>"
    else:
        return "<span style='color:orange'>⚠️ Install kaleido for image export: <code>pip install -U kaleido</code></span>"

# Function to convert dataframe to image
def dataframe_to_image(df, title="Data Table", max_rows=50):
    """Convert dataframe to image using matplotlib"""
    try:
        # Limit rows for image
        display_df = df.head(max_rows) if len(df) > max_rows else df
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, min(8, len(display_df) * 0.3 + 1)))
        ax.axis('tight')
        ax.axis('off')
        
        # Create table
        table = ax.table(cellText=display_df.values,
                        colLabels=display_df.columns,
                        cellLoc='left',
                        loc='center',
                        colWidths=[0.15] * len(display_df.columns))
        
        # Style the table
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.2, 1.5)
        
        # Color header
        for (i, j), cell in table.get_celld().items():
            if i == 0:
                cell.set_facecolor('#667eea')
                cell.set_text_props(weight='bold', color='white')
            elif i % 2 == 0:
                cell.set_facecolor('#f8f9fa')
        
        # Add title
        plt.title(title, fontsize=14, weight='bold', pad=20)
        
        # Add note if rows truncated
        if len(df) > max_rows:
            plt.figtext(0.5, 0.01, f"Note: Showing first {max_rows} rows out of {len(df)} total rows", 
                       ha="center", fontsize=8, style='italic')
        
        # Convert to image
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=300, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        plt.close()
        
        return buf
    except Exception as e:
        st.error(f"Error creating table image: {str(e)}")
        return None

# Function to download image
def get_image_download_link(img_buffer, filename="table_image.png"):
    """Generate download link for image"""
    b64 = base64.b64encode(img_buffer.getvalue()).decode()
    href = f'<a href="data:image/png;base64,{b64}" download="{filename}">Download Image</a>'
    return href

# Title
st.markdown('<div class="main-header">🏢 Biometric Device Monitoring System PRO</div>', unsafe_allow_html=True)
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("📁 Data Upload")
    
    portal_file = st.file_uploader(
        "**Device Export File** (Excel)",
        type=['xlsx', 'xls'],
        help="Columns: Serial Number, Device Name, Area, Device IP, Last Activity"
    )
    
    master_file = st.file_uploader(
        "**Biometric Master File** (Excel)",
        type=['xlsx', 'xls'],
        help="Columns: Serial Number, Bio Metric Type, Zone, Ward, Device Name, Near Facility"
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
        1. **Ward NULL** → Status = Zone/Area value
        2. **Days ≤ {active_days} & Zone/Area ≠ 'Not Authorized'** → ✅ Active
        3. **Days > {active_days} & Zone/Area ≠ 'Not Authorized'** → ⚠️ Inactive
        4. **Zone/Area = 'Not Authorized'** → Not authorized
        """)
    
    # Export Section
    if st.session_state.processed_data is not None:
        st.markdown("---")
        st.header("📥 Export Options")
        
        col1, col2, col3 = st.columns(3)
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
        
        with col3:
            if st.button("🖼️ Download Table as Image", use_container_width=True):
                img_buffer = dataframe_to_image(st.session_state.processed_data, "Biometric Devices Report")
                if img_buffer:
                    href = get_image_download_link(img_buffer, "biometric_report.png")
                    st.markdown(href, unsafe_allow_html=True)

# Processing function
def process_biometric_data(portal_file, master_file, active_threshold=2):
    try:
        # Load files
        portal_df = pd.read_excel(portal_file)
        try:
            master_df = pd.read_excel(master_file, sheet_name="Master")
        except:
            master_df = pd.read_excel(master_file)
        
        # Display actual columns found
        with st.expander("🔍 Column Debug Information", expanded=False):
            st.markdown("**Device Export File Columns Found:**")
            st.write(list(portal_df.columns))
            st.markdown("**Biometric Master File Columns Found:**")
            st.write(list(master_df.columns))
            
            # Show sample data
            st.markdown("**Sample Device Export Data (First 3 rows):**")
            st.dataframe(portal_df.head(3))
            st.markdown("**Sample Master Data (First 3 rows):**")
            st.dataframe(master_df.head(3))
        
        # Rename columns to standard names for processing
        # Device Export File column mapping
        portal_column_map = {}
        for col in portal_df.columns:
            if col == 'Serial Number':
                portal_column_map[col] = 'Serial Number'
            elif col == 'Device Name':
                portal_column_map[col] = 'Device Name'
            elif col == 'Area':
                portal_column_map[col] = 'Area'
            elif col == 'Device IP':
                portal_column_map[col] = 'Device IP'
            elif col == 'Last Activity':
                portal_column_map[col] = 'Last Activity'
        
        # Biometric Master File column mapping
        master_column_map = {}
        for col in master_df.columns:
            if col == 'Serial Number':
                master_column_map[col] = 'Serial Number'
            elif col == 'Bio Metric Type':
                master_column_map[col] = 'Bio Metric Type'
            elif col == 'Zone':
                master_column_map[col] = 'Zone'
            elif col == 'Ward':
                master_column_map[col] = 'Ward'
            elif col == 'Device Name':
                master_column_map[col] = 'Device Name Master'
            elif col == 'Near Facility':
                master_column_map[col] = 'Near Facility'
        
        # Apply renaming
        portal_df = portal_df.rename(columns=portal_column_map)
        master_df = master_df.rename(columns=master_column_map)
        
        # Check for required columns
        required_portal = ['Serial Number', 'Last Activity']
        required_master = ['Serial Number']
        
        missing_portal = [col for col in required_portal if col not in portal_df.columns]
        missing_master = [col for col in required_master if col not in master_df.columns]
        
        if missing_portal:
            st.error(f"❌ Missing columns in Device Export file: {missing_portal}")
            return None, None
        if missing_master:
            st.error(f"❌ Missing columns in Master file: {missing_master}")
            return None, None
        
        # Ensure Serial Number is string for proper merging
        portal_df['Serial Number'] = portal_df['Serial Number'].astype(str).str.strip()
        master_df['Serial Number'] = master_df['Serial Number'].astype(str).str.strip()
        
        # Merge dataframes
        merged = master_df.merge(portal_df, on="Serial Number", how="left")
        
        # Process dates
        merged['Last Activity Date'] = pd.to_datetime(merged['Last Activity'], errors='coerce').dt.normalize()
        
        # Calculate days inactive
        max_date = merged['Last Activity Date'].max()
        if pd.isna(max_date):
            merged['Days Inactive'] = 0
        else:
            merged['Days Inactive'] = (max_date - merged['Last Activity Date']).dt.days
            merged['Days Inactive'] = merged['Days Inactive'].fillna(0)
        
        # Fill missing values in important columns
        # For Device Name - prioritize master file Device Name, fallback to portal file
        if 'Device Name Master' in merged.columns:
            merged['Device Name'] = merged['Device Name Master'].fillna('Not Available')
        elif 'Device Name' in merged.columns:
            merged['Device Name'] = merged['Device Name'].fillna('Not Available')
        else:
            merged['Device Name'] = 'Not Available'
        
        # For other columns
        if 'Device IP' not in merged.columns:
            merged['Device IP'] = 'Not Available'
        else:
            merged['Device IP'] = merged['Device IP'].fillna('Not Available')
        
        if 'Bio Metric Type' not in merged.columns:
            merged['Bio Metric Type'] = 'Not Available'
        else:
            merged['Bio Metric Type'] = merged['Bio Metric Type'].fillna('Not Available')
        
        if 'Near Facility' not in merged.columns:
            merged['Near Facility'] = 'Not Available'
        else:
            merged['Near Facility'] = merged['Near Facility'].fillna('Not Available')
        
        # Handle Zone/Area - use Zone from master or Area from portal
        if 'Zone' in merged.columns:
            merged['Area'] = merged['Zone'].fillna('Not Available')
        elif 'Area' in merged.columns:
            merged['Area'] = merged['Area'].fillna('Not Available')
        else:
            merged['Area'] = 'Not Available'
        
        if 'Ward' not in merged.columns:
            merged['Ward'] = 'Not Available'
        else:
            merged['Ward'] = merged['Ward'].fillna('Not Available')
        
        # Replace empty strings and NaN with 'Not Available'
        for col in ['Device Name', 'Device IP', 'Bio Metric Type', 'Near Facility', 'Area', 'Ward']:
            if col in merged.columns:
                merged[col] = merged[col].replace(['', 'nan', 'NaN', 'None', ' '], 'Not Available')
        
        # Determine status
        def determine_status(row):
            ward = str(row.get('Ward', '')).strip()
            ward_null = ward in ['', 'Not Available', 'nan', 'NaN', 'None']
            
            if ward_null:
                ward_val = row.get('Ward', 'Unknown')
                return str(ward_val) if ward_val != 'Not Available' else 'Unknown'
            
            area = str(row.get('Area', '')).strip()
            days = row.get('Days Inactive', 0)
            
            if area == 'Not Authorized':
                return 'Not authorized'
            elif days <= active_threshold:
                return '✅ Active'
            else:
                return '⚠️ Inactive'
        
        merged['Status'] = merged.apply(determine_status, axis=1)
        
        # Create summary
        summary = merged['Status'].value_counts().reset_index()
        summary.columns = ['Status', 'Count']
        summary['Percentage'] = (summary['Count'] / summary['Count'].sum() * 100).round(1)
        
        # Define display columns in desired order
        display_cols = ['Serial Number', 'Near Facility', 'Device Name', 'Device IP', 'Area', 'Ward', 'Bio Metric Type', 'Days Inactive', 'Status', 'Last Activity']
        
        # Ensure all columns exist
        for col in display_cols:
            if col not in merged.columns:
                merged[col] = 'Not Available'
        
        # Create result dataframe
        result_df = merged[display_cols].copy()
        
        # Sort by status (Active first, then Inactive, then Not authorized)
        status_order = {'✅ Active': 0, '⚠️ Inactive': 1, 'Not authorized': 2}
        result_df['Status Order'] = result_df['Status'].map(status_order).fillna(3)
        result_df = result_df.sort_values('Status Order').drop('Status Order', axis=1)
        
        # Add processed timestamp
        result_df['Processed'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Show column mapping success
        st.success(f"✅ Processing complete! Found {len(result_df)} devices")
        
        # Show data quality in sidebar
        with st.sidebar:
            with st.expander("📊 Data Quality Report", expanded=False):
                for col in ['Serial Number', 'Device Name', 'Device IP', 'Near Facility', 'Area', 'Ward', 'Bio Metric Type']:
                    if col in result_df.columns:
                        non_na = result_df[col][result_df[col] != 'Not Available'].count()
                        pct = (non_na/len(result_df)*100) if len(result_df) > 0 else 0
                        st.write(f"**{col}:** {non_na}/{len(result_df)} ({pct:.1f}%)")
        
        return result_df, summary
        
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
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
                    'blocked_count': len(processed_df[processed_df['Status'] == 'Not authorized'])
                })
                
                # Alert check
                inactive_devices = processed_df[processed_df['Status'] == '⚠️ Inactive']
                long_inactive = inactive_devices[inactive_devices['Days Inactive'] > st.session_state.alerts_config['inactive_threshold']]
                
                if len(long_inactive) > 0:
                    st.warning(f"⚠️ Alert: {len(long_inactive)} devices inactive > {st.session_state.alerts_config['inactive_threshold']} days!")
                
                st.success("✅ Processing complete!")
                st.balloons()

# Show kaleido warning if needed
if not KALEIDO_AVAILABLE and st.session_state.processed_data is not None:
    st.info("💡 **Tip:** Install 'kaleido' package to enable Plotly chart image exports: `pip install -U kaleido`")

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
            not_authorized_count = len(df[df['Status'] == 'Not authorized'])
            not_authorized_pct = (not_authorized_count/total_devices*100) if total_devices > 0 else 0
            st.metric("❌ Not authorized", f"{not_authorized_count}", delta=f"{not_authorized_pct:.1f}%")
        
        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Status Distribution")
            fig1 = px.pie(summary, values='Count', names='Status', hole=0.3, 
                          color_discrete_sequence=['#2ecc71', '#e74c3c', '#95a5a6'])
            fig1.update_traces(textposition='inside', textinfo='percent+label')
            fig1.update_layout(height=400)
            st.plotly_chart(fig1, use_container_width=True)
            
            # Download chart as image button
            if st.button("📸 Download Chart as Image", key="download_pie"):
                href = export_plotly_as_image(fig1, "status_distribution.png", width=800, height=500)
                st.markdown(href, unsafe_allow_html=True)
        
        with col2:
            st.subheader("Inactive Days Distribution")
            # Create days groups
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
                area_options = [x for x in df['Area'].unique() if x not in ['Not Available', 'Unknown']]
                if area_options:
                    area_filter = st.multiselect("Filter by Area/Zone", options=area_options, 
                                                 default=area_options, key="filter2")
                else:
                    area_filter = []
                    st.info("No Area/Zone data available")
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
            elif 'Not authorized' in str(val):
                return 'background-color: #D3D3D3'
            return ''
        
        styled_df = filtered_df.style.map(color_status, subset=['Status'])
        st.dataframe(styled_df, use_container_width=True, height=500)
        st.caption(f"Showing {len(filtered_df)} of {len(df)} records")
        
        # Export options for filtered data
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📥 Export Filtered CSV"):
                csv = filtered_df.to_csv(index=False)
                b64 = base64.b64encode(csv.encode()).decode()
                href = f'<a href="data:file/csv;base64,{b64}" download="filtered_data.csv">Download CSV</a>'
                st.markdown(href, unsafe_allow_html=True)
        
        with col2:
            if st.button("🖼️ Download Table as Image", key="download_table_image"):
                img_buffer = dataframe_to_image(filtered_df, f"Filtered Biometric Data - {len(filtered_df)} Records")
                if img_buffer:
                    href = get_image_download_link(img_buffer, "filtered_biometric_data.png")
                    st.markdown(href, unsafe_allow_html=True)
        
        # Top inactive devices
        st.markdown("---")
        st.subheader("⚠️ Inactive Devices (⚠️ Inactive Status Only)")
        
        # Filter only devices with status '⚠️ Inactive'
        inactive_only_df = df[df['Status'] == '⚠️ Inactive']
        
        if len(inactive_only_df) > 0:
            top_inactive = inactive_only_df.nlargest(100, 'Days Inactive')[['Serial Number', 'Device Name', 'Near Facility', 'Area', 'Device IP', 'Days Inactive', 'Status']]
            st.dataframe(top_inactive, use_container_width=True)
            st.caption(f"Showing {len(top_inactive)} inactive devices out of {len(inactive_only_df)} total inactive devices")
            
            # Download inactive devices table as image
            if st.button("🖼️ Download Inactive Devices Table as Image"):
                img_buffer = dataframe_to_image(top_inactive, f"Inactive Devices Report - {len(top_inactive)} Devices")
                if img_buffer:
                    href = get_image_download_link(img_buffer, "inactive_devices.png")
                    st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("No inactive devices found!")
    
    # ==================== TAB 3: ANALYTICS ====================
    with tab3:
        st.subheader("Advanced Analytics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Status by Near Facility")
            if 'Near Facility' in df.columns and len(df['Near Facility'].unique()) > 1:
                # Filter out 'Not Available' for better visualization
                plot_df = df[df['Near Facility'] != 'Not Available']
                if len(plot_df) > 0:
                    area_status = pd.crosstab(plot_df['Near Facility'], plot_df['Status'])
                    fig3 = px.imshow(area_status, text_auto=True, aspect="auto", 
                                     title="Heatmap: Status by Near Facility", color_continuous_scale='Viridis')
                    fig3.update_layout(height=1500)
                    st.plotly_chart(fig3, use_container_width=True)
                else:
                    st.info("No valid Near Facility data for heatmap")
            else:
                st.info("Insufficient Near Facility data for heatmap visualization")
        
        with col2:
            st.markdown("#### Status by Bio Metric Type")
            if 'Bio Metric Type' in df.columns and len(df['Bio Metric Type'].unique()) > 1:
                plot_df = df[df['Bio Metric Type'] != 'Not Available']
                if len(plot_df) > 0:
                    bio_status = pd.crosstab(plot_df['Bio Metric Type'], plot_df['Status'])
                    fig4 = px.bar(bio_status, title='Status Distribution by Bio Metric Type', barmode='group')
                    fig4.update_layout(height=500)
                    st.plotly_chart(fig4, use_container_width=True)
                else:
                    st.info("No valid Bio Metric Type data")
            else:
                st.info("Insufficient Bio Metric Type data")
        
        # Cumulative distribution
        st.markdown("#### Cumulative Distribution of Inactive Days")
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
            'Metric': ['Mean Inactive Days', 'Median Inactive Days', 'Std Deviation', 'Min Days', 'Max Days', 'Total Devices'],
            'Value': [
                f"{df['Days Inactive'].mean():.1f}",
                f"{df['Days Inactive'].median():.1f}",
                f"{df['Days Inactive'].std():.1f}",
                f"{df['Days Inactive'].min()}",
                f"{df['Days Inactive'].max()}",
                f"{len(df)}"
            ]
        })
        st.dataframe(stats_df, use_container_width=True)
        
        # Download statistics table as image
        if st.button("🖼️ Download Statistics Table as Image"):
            img_buffer = dataframe_to_image(stats_df, "Statistical Summary")
            if img_buffer:
                href = get_image_download_link(img_buffer, "statistics_summary.png")
                st.markdown(href, unsafe_allow_html=True)
    
    # ==================== TAB 4: HISTORY ====================
    with tab4:
        st.subheader("Processing History")
        
        if st.session_state.processing_history:
            history_df = pd.DataFrame(st.session_state.processing_history)
            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
            history_df = history_df.sort_values('timestamp', ascending=False)
            
            display_history = history_df[['timestamp', 'file_name', 'total_devices', 'active_count', 'inactive_count', 'blocked_count']].copy()
            display_history.columns = ['Date & Time', 'File Name', 'Total', 'Active', 'Inactive', 'Not authorized']
            st.dataframe(display_history, use_container_width=True)
            
            # Download history table as image
            if st.button("🖼️ Download History Table as Image"):
                img_buffer = dataframe_to_image(display_history, "Processing History Report")
                if img_buffer:
                    href = get_image_download_link(img_buffer, "processing_history.png")
                    st.markdown(href, unsafe_allow_html=True)
            
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
                        'Metric': ['Total', 'Active', 'Inactive', 'Not authorized'],
                        r1['timestamp'].strftime('%Y-%m-%d'): [r1['total_devices'], r1['active_count'], r1['inactive_count'], r1['blocked_count']],
                        r2['timestamp'].strftime('%Y-%m-%d'): [r2['total_devices'], r2['active_count'], r2['inactive_count'], r2['blocked_count']],
                        'Change': [
                            r2['total_devices'] - r1['total_devices'],
                            r2['active_count'] - r1['active_count'],
                            r2['inactive_count'] - r1['inactive_count'],
                            r2['blocked_count'] - r1['blocked_count']
                        ]
                    })
                    st.dataframe(comparison, use_container_width=True)
                    
                    # Download comparison table as image
                    if st.button("🖼️ Download Comparison Table as Image"):
                        img_buffer = dataframe_to_image(comparison, "Report Comparison")
                        if img_buffer:
                            href = get_image_download_link(img_buffer, "report_comparison.png")
                            st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("No processing history yet. Process some data to see history here!")
    
    # ==================== TAB 5: SAVED REPORTS ====================
    with tab5:
        st.subheader("Saved Reports")
        
        # Save current report button
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Current Report", use_container_width=True):
                report_name = f"Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                st.session_state.saved_reports.append({
                    'name': report_name,
                    'date': datetime.now(),
                    'data': st.session_state.processed_data.copy(),
                    'summary': st.session_state.summary_data.copy() if st.session_state.summary_data is not None else None
                })
                st.success(f"Report '{report_name}' saved!")
                st.rerun()
        
        with col2:
            if st.session_state.processed_data is not None:
                if st.button("🖼️ Download Current Report as Image", use_container_width=True):
                    img_buffer = dataframe_to_image(st.session_state.processed_data, f"Biometric Report {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                    if img_buffer:
                        href = get_image_download_link(img_buffer, f"biometric_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                        st.markdown(href, unsafe_allow_html=True)
        
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
                        not_auth = len(report['data'][report['data']['Status'] == 'Not authorized'])
                        st.metric("Not authorized", not_auth)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button(f"📊 Load Report", key=f"load_{idx}"):
                            st.session_state.processed_data = report['data']
                            st.session_state.summary_data = report['summary']
                            st.success("Report loaded!")
                            st.rerun()
                    with col2:
                        if st.button(f"🖼️ Download as Image", key=f"img_{idx}"):
                            img_buffer = dataframe_to_image(report['data'], f"{report['name']}")
                            if img_buffer:
                                href = get_image_download_link(img_buffer, f"{report['name']}.png")
                                st.markdown(href, unsafe_allow_html=True)
                    with col3:
                        if st.button(f"🗑️ Delete Report", key=f"del_{idx}"):
                            st.session_state.saved_reports.pop(len(st.session_state.saved_reports) - 1 - idx)
                            st.rerun()
        else:
            st.info("No saved reports. Click 'Save Current Report' to store the current analysis!")

else:
    # Welcome screen
    st.info("""
    ### 👋 Welcome to Biometric Device Monitoring System PRO!
    
    **File Requirements:**
    
    **Device Export File** should contain:
    - Serial Number
    - Device Name
    - Area
    - Device IP
    - Last Activity
    
    **Biometric Master File** should contain:
    - Serial Number
    - Bio Metric Type
    - Zone
    - Ward
    - Device Name
    - Near Facility
    
    **Get started:**
    1. Upload both Excel files
    2. Click **Process Data** button
    3. Explore the interactive dashboard!
    
    **Features:**
    - ✅ Interactive Dashboard with KPI cards
    - 📋 Sortable and filterable device data
    - 📈 Advanced analytics and trends
    - 📜 Processing history with comparisons
    - 💾 Save and load reports
    - 📥 Export to CSV/Excel/Images
    """)

# Footer
st.markdown("---")
st.markdown(
    f"<p style='text-align: center; color: gray;'>🏢 Biometric Device Monitor PRO | v4.0 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
    unsafe_allow_html=True
)
