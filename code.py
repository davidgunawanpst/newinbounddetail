import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import base64

# -- CONFIGURE YOUR GOOGLE SHEET HERE --
SHEET_ID = "1viV03CJxPsK42zZyKI6ZfaXlLR62IbC0O3Lbi_hfGRo"
SHEET_NAME = "Master"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"

@st.cache_data
def load_po_data():
    df = pd.read_csv(CSV_URL)
    po_dict = {}
    for _, row in df.iterrows():
        db = row['Database']
        po = str(row['Nomor PO'])
        item = row['Item']
        if db not in po_dict:
            po_dict[db] = {}
        if po not in po_dict[db]:
            po_dict[db][po] = []
        po_dict[db][po].append(item)
    return po_dict

database_data = load_po_data()

# -- Replace with your actual script deployment URLs --
DRIVE_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyds4um-AHIqGc32-92SbGw1FOfufUPF5QnfqE9CZUpjrw_iAinLwpZgJK8KhFhnUzAsg/exec"
SHEET_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbya11RAnvYCr334dO5M0dl51D40JlGpkEB6kXkg0hPbmzmnbngh3feFlr1GPqZtZQYB1w/exec"

# --- UI ---
st.title("Inbound Monitoring Form")

selected_db = st.selectbox("Select Database:", list(database_data.keys()))
po_options = list(database_data[selected_db].keys())
selected_po = st.selectbox("Select PO Number:", po_options)
item_options = database_data[selected_db][selected_po]
selected_items = st.multiselect("Select items received:", item_options)

qty_dict = {}
for item in selected_items:
    qty = st.number_input(f"Qty received for {item}", min_value=0, step=1, key=f"qty_{item}")
    qty_dict[item] = qty

uploaded_files = st.file_uploader("Upload photos (unlimited):", accept_multiple_files=True, type=["jpg", "jpeg", "png"])

if st.button("Submit"):
    if len(qty_dict) == 0 or all(q == 0 for q in qty_dict.values()):
        st.error("Please enter quantity for at least one item.")
    else:
        timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d_%H-%M-%S")
        folder_name = f"{selected_db}_{selected_po}_{timestamp}"

        # Step 1: Upload to Drive - only if there are files
        drive_payload = {
            "folder_name": folder_name,
            "images": [
                {
                    "filename": file.name,
                    "content": base64.b64encode(file.read()).decode("utf-8")
                }
                for file in uploaded_files
            ] if uploaded_files else []
        }

        try:
            drive_response = requests.post(DRIVE_WEBHOOK_URL, json=drive_payload)
            if drive_response.status_code == 200:
                drive_json = drive_response.json()
                folder_url = drive_json.get("folderUrl", "")
                st.write(f"Drive upload folder URL: {folder_url}")  # Debug info

                # Step 2: Submit to Sheet
                entries = [
                    {
                        "timestamp": timestamp,
                        "database": selected_db,
                        "po_number": selected_po,
                        "item": item,
                        "quantity": qty,
                        "folder_url": folder_url
                    }
                    for item, qty in qty_dict.items() if qty > 0
                ]

                sheet_payload = {"entries": entries}

                sheet_response = requests.post(SHEET_WEBHOOK_URL, json=sheet_payload, headers={"Content-Type": "application/json"})

                # Debug responses
                st.write(f"Sheet POST status code: {sheet_response.status_code}")
                st.write(f"Sheet POST response text: {sheet_response.text}")

                if sheet_response.status_code == 200:
                    st.success("Data and photos submitted successfully!")
                else:
                    st.error(f"Sheet Error: {sheet_response.status_code} - {sheet_response.text}")
            else:
                st.error(f"Drive Error: {drive_response.status_code} - {drive_response.text}")
        except Exception as e:
            st.error(f"Submission failed: {e}")
