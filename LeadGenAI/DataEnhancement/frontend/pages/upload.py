import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="📤 Upload CSV & Normalize", layout="wide")
st.title("📤 Upload & Normalize Lead Data")
st.markdown("""
Welcome! This tool allows you to upload a CSV file and normalize its structure 
to match our standard format, and enrich it with LinkedIn data.
""")

if "normalized_df" not in st.session_state:
    st.session_state.normalized_df = None
if "confirmed_selection_df" not in st.session_state:
    st.session_state.confirmed_selection_df = None

STANDARD_COLUMNS = [
    'Company', 'City', 'State', 'First Name', 'Last Name', 'Email', 'Title', 'Website',
    'LinkedIn URL', 'Industry ', 'Revenue', 'Product/Service Category',
    'Business Type (B2B, B2B2C) ', 'Employees count', 'Employees range', 'Rev Source', 'Year Founded',
    "Owner's LinkedIn", 'Owner Age', 'Phone Number', 'Additional Notes', 'Score',
    'Email customization #1', 'Subject Line #1', 'Email Customization #2', 'Subject Line #2',
    'LinkedIn Customization #1', 'LinkedIn Customization #2', 'Reasoning for r//y/g'
]

st.markdown("### 📎 Step 1: Upload Your CSV")
uploaded_file = st.file_uploader("Choose a CSV file to upload", type=["csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        st.success("✅ File uploaded successfully!")

        st.markdown("### ✅ Step 2: Select Rows to Enhance")
        st.markdown("Check the companies you want to enhance. Maximum **10 rows** allowed.")

        df['Select Row'] = False
        edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic", key="editable_df", disabled=df.columns[:-1].tolist())
        selected_df = pd.DataFrame(edited_df)
        rows_to_enhance = selected_df[selected_df['Select Row'] == True].drop(columns=['Select Row'])

        selected_count = len(rows_to_enhance)
        st.markdown(f"**🧮 Selected Rows: `{selected_count}` / 10**")

        if selected_count > 10:
            st.error("❌ You can only select up to 10 rows for enhancement.")
            st.button("✅ Confirm Selected Rows", disabled=True)
        else:
            if st.button("✅ Confirm Selected Rows"):
                if selected_count > 0:
                    st.session_state.confirmed_selection_df = rows_to_enhance.copy()
                    st.success(f"{selected_count} rows confirmed for normalization and enrichment.")
                else:
                    st.session_state.confirmed_selection_df = df.copy()
                    st.info("No rows selected. Defaulting to all rows.")

    except Exception as e:
        st.error(f"❌ Failed to process file: {e}")

if st.session_state.confirmed_selection_df is not None:
    data_for_mapping = st.session_state.confirmed_selection_df.copy()

    st.markdown("### 🛠 Step 3: Map Your Columns")
    auto_mapping = {col: col for col in STANDARD_COLUMNS if col in data_for_mapping.columns}
    column_mapping = {}

    st.markdown("#### 🔗 Map your CSV columns to our standard format:")
    for target in STANDARD_COLUMNS:
        st.markdown(f"<div style='margin-bottom: -0.5rem; margin-top: 1rem; font-weight: 600;'>{target}</div>", unsafe_allow_html=True)
        col1, col2 = st.columns([1, 2])
        with col1:
            st.text("From your file")
        with col2:
            default = auto_mapping.get(target, "-- None --")
            selected = st.selectbox(" ", ["-- None --"] + list(data_for_mapping.columns), index=(["-- None --"] + list(data_for_mapping.columns)).index(default) if default != "-- None --" else 0, key=target, label_visibility="collapsed")
        column_mapping[target] = selected if selected != "-- None --" else None

    if st.button("🔄 Normalize CSV"):
        normalized_df = pd.DataFrame()
        selected_cols = []

        for col in STANDARD_COLUMNS:
            if column_mapping[col] and column_mapping[col] in data_for_mapping.columns:
                normalized_df[col] = data_for_mapping[column_mapping[col]]
                selected_cols.append(col)
            else:
                normalized_df[col] = ""

        # Add extra columns that were not mapped
        mapped_input_columns = set(column_mapping.values())
        extra_columns = [col for col in data_for_mapping.columns if col not in mapped_input_columns and col != "Select Row"]
        for col in extra_columns:
            normalized_df[col] = data_for_mapping[col]

        st.session_state.normalized_df = normalized_df.copy()

        st.markdown("### ✅ Normalized Data Preview (Selected Rows with Standard + Extra Columns)")
        preview_df = normalized_df.astype(str)
        st.dataframe(preview_df.head(), use_container_width=True)

        csv_download = normalized_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Normalized CSV", data=csv_download, file_name="normalized_leads.csv", mime="text/csv")

if st.session_state.normalized_df is not None and st.session_state.confirmed_selection_df is not None:
    if st.button("🚀 Enhance with LinkedIn Data"):
        st.markdown("⏳ Please wait while we enrich company data...")
        progress_bar = st.progress(0)
        status_text = st.empty()

        base_df = st.session_state.normalized_df.copy()
        confirmed_df = st.session_state.confirmed_selection_df.copy()

        enhanced_df = base_df.copy()
        mask = base_df["Company"].isin(confirmed_df["Company"])
        rows_to_update = enhanced_df[mask].copy()

        # 👇 Safe JSON payload
        linkedin_payload = [
            {
                "company": str(row.get("Company", "") or ""),
                "city": str(row.get("City", "") or ""),
                "state": str(row.get("State", "") or ""),
                "website": str(row.get("Website", "") or "")
            }
            for _, row in rows_to_update.iterrows()
        ]

        linkedin_response = requests.post("http://localhost:5000/api/linkedin-info-batch", json=linkedin_payload)
        linkedin_lookup = {r.get("company"): r for r in linkedin_response.json() if "company" in r}

        for i, (idx, row) in enumerate(rows_to_update.iterrows()):
            domain = row["Company"]
            linkedin = linkedin_lookup.get(domain, {})

            revenue = ""
            try:
                growjo_response = requests.get("http://localhost:5000/api/get-revenue", params={"company": domain})
                if growjo_response.status_code == 200:
                    revenue = growjo_response.json().get("estimated_revenue", "")
            except:
                revenue = ""

            if not row["Revenue"].strip():
                rows_to_update.at[idx, "Revenue"] = revenue
            if not row["Year Founded"].strip():
                rows_to_update.at[idx, "Year Founded"] = linkedin.get("Founded", "")
            if not row["Website"].strip():
                website_response = requests.get("http://localhost:5000/api/find-website", params={"company": domain})
                if website_response.status_code == 200:
                    rows_to_update.at[idx, "Website"] = website_response.json().get("website", "")
            if not row["LinkedIn URL"].strip():
                rows_to_update.at[idx, "LinkedIn URL"] = linkedin.get("LinkedIn Link", "")
            if not row["Industry "].strip():
                rows_to_update.at[idx, "Industry "] = linkedin.get("Industry", "")
            if not row["Employees count"].strip():
                rows_to_update.at[idx, "Employees count"] = linkedin.get("Company Size", "")
            if not row["Product/Service Category"].strip():
                rows_to_update.at[idx, "Product/Service Category"] = linkedin.get("Specialties", "")

            progress_bar.progress((i + 1) / len(rows_to_update))
            status_text.text(f"Enhanced {i + 1} of {len(rows_to_update)} rows")

        enhanced_df.update(rows_to_update)

        st.success("✅ Enrichment complete!")
        st.dataframe(enhanced_df.astype(str).head(), use_container_width=True)
        csv = enhanced_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Enhanced CSV", csv, file_name="linkedin_enriched.csv", mime="text/csv")
