Biometric Device Monitoring & Analytics System
🔗 Project Overview
A production-ready data analytics platform designed to monitor, analyze, and automate reporting for biometric devices across multiple operational locations.
This system transforms raw device logs into actionable insights, real-time dashboards, and automated reports, reducing manual effort and improving operational visibility.
🎯 Problem Statement
Organizations managing biometric devices face:
❌ Manual tracking of device activity
❌ Lack of real-time monitoring
❌ Inconsistent and messy Excel data
❌ Delayed reporting and poor visibility
👉 This project solves these challenges by building a centralized analytics system with automation and real-time insights.
🏗️ System Architecture (Conceptual Flow)

Device Export Data (Excel)
            +
Master Data (Excel)
            ↓
     Data Ingestion (Pandas)
            ↓
   Data Cleaning & Validation
            ↓
    ETL Transformation Logic
            ↓
   Status Classification Engine
            ↓
 Interactive Dashboard (Streamlit + Plotly)
            ↓
 Export Layer (Excel / Image / Google Sheets API)
            ↓
     Reporting & Monitoring
⚙️ Key Features
📊 1. Data Processing & ETL
Automated ingestion of multiple Excel datasets
Data cleaning (NaN, format normalization, validation)
Merging master + device data using primary keys (Serial Number)
Derived metrics:
Days Inactive
Device Status classification
🧠 2. Business Logic Engine
Rule-based classification:
✅ Active
⚠️ Inactive
❌ Not Authorized
Configurable thresholds (dynamic inactivity logic)
Handles edge cases (missing ward, null values, invalid timestamps)
📈 3. Interactive Analytics Dashboard
Built using Streamlit + Plotly
Real-time KPIs:
Total Devices
Active / Inactive ratio
Compliance %
Visualizations:
Status distribution (Pie)
Inactive trend (Bar)
Heatmaps (Facility vs Status)
🔌 4. API Integration (Google Sheets Automation)
Integrated Google Apps Script (REST API)
Enables:
Real-time export to Google Sheets
Centralized reporting
Data sharing across teams
📸 5. Advanced Export System
Export reports as:
CSV / Excel
PNG / JPEG / PDF (custom styled tables)
Customization:
Filters, sorting, colors, fonts
Built using Matplotlib + dynamic UI controls
⚙️ 6. Persistent Configuration System
JSON-based configuration storage
Stores:
API endpoints
Processing rules
Display preferences
Auto-loads settings across sessions
🚨 7. Alert & Monitoring System
Detects devices inactive beyond threshold
Configurable alert rules
Designed for integration with email/notification systems
🗂️ 8. Report Management
Save and reload processed reports
Maintain processing history logs
Enables audit and tracking of analytics runs
🛠️ Tech Stack
Category
Tools / Technologies
Programming
Python
Data Processing
Pandas, NumPy
Visualization
Plotly, Matplotlib
Dashboard
Streamlit
Integration
REST API, Google Apps Script
Data Sources
Excel
Config Management
JSON
📊 Key Outcomes / Impact
🚀 Reduced manual reporting effort significantly
📉 Improved device monitoring efficiency and visibility
⚡ Enabled real-time analytics and decision-making
🔄 Automated data pipeline from ingestion to reporting
👉 (Add real numbers here if possible — this will make it very powerful)
Example:
Processed 500+ devices daily
Reduced reporting time by 70%
🧪 Challenges & Solutions
Challenge
Solution
Inconsistent Excel data
Built robust data cleaning pipeline
Missing / null values
Implemented fallback logic & validation
JSON serialization issues
Custom cleaning function for API export
Real-time export reliability
Added retry + error handling for API
🔮 Future Enhancements
Real-time streaming data integration (IoT-based devices)
Email/SMS alert automation
Role-based access dashboard
Database integration (PostgreSQL / MySQL)
Deployment on cloud (AWS / Streamlit Cloud)
📷 Screenshots (Add in GitHub)
👉 Add:
Dashboard view
Device table
Charts
Export feature
🧑‍💻 Author
Vasanthaprakash E
Data Analyst | Automation | API Integration
Skilled in Python, SQL, Power BI
