import streamlit as st
import easyocr
import cv2
import numpy as np
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image

st.markdown("""
    <style>
    /* Memperbesar box kamera */
    div[data-testid="stCameraInput"] {
        width: 100% !important;
    }
    /* Memperbesar preview gambar agar memenuhi layar */
    div[data-testid="stCameraInput"] img {
        filter: contrast(1.1); /* Sedikit bantuan kontras untuk OCR */
        width: 100% !important;
        height: auto !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. KONEKSI GOOGLE SHEETS
# ==========================================
def save_to_google_sheets(info_dict):
    try:
        # 1. Ambil kredensial dari Streamlit Secrets dan jadikan dictionary
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # 2. PERBAIKAN KRUSIAL: Ganti teks literal "\n" menjadi karakter enter sesungguhnya
        creds_dict["private_key"] = creds_dict["private_key"].replace('\\n', '\n')
        
        # 3. Lanjut autentikasi seperti biasa
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Pastikan nama file sesuai
        sheet = client.open("ResultOcrLive").sheet1
        
        all_data = sheet.get_all_records()
        no_urut = len(all_data) + 1
        
        row = [no_urut, info_dict["Nomor"], info_dict["Tanggal"], info_dict["Perihal"], info_dict["Tujuan"]]
        sheet.append_row(row)
        return True
        
    except Exception as e:
        st.error(f"Gagal simpan ke Sheets: {e}")
        return False

# ==========================================
# 2. FUNGSI EKSTRAKSI (MODIFIKASI DARI KODEMU)
# ==========================================
def extract_info(text_list):
    info = {"Nomor": "-", "Tanggal": "-", "Perihal": "-", "Tujuan": "-"}
    full_text_raw = " ".join(text_list)
    
    no_match = re.search(r"(?i)(?:nomor|no)\s*[:.]?\s*([^\n\r]*)", full_text_raw)
    if no_match:
        clean_no = re.split(r"(?i)lamp", no_match.group(1))[0].strip()
        info["Nomor"] = clean_no

    bulan_regex = r"(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember|jan|feb|mar|apr|jun|jul|agu|sep|okt|nov|des)"
    tanggal_match = re.search(fr"(?i)\b(\d{{1,2}})\s+{bulan_regex}\s+(\d{{4}})\b", full_text_raw)
    if tanggal_match:
        info["Tanggal"] = tanggal_match.group(0).strip()

    hal_match = re.search(r"(?i)(?:hal|perihal)\s*[:.]?\s*(.*?)(?=(?:kepada|yth|$))", full_text_raw)
    if hal_match:
        info["Perihal"] = hal_match.group(1).strip()

    for i, line in enumerate(text_list):
        line_clean = line.lower()
        if "kepada" in line_clean or "yth" in line_clean:
            content = re.sub(r"(?i)kepada|yth|[:.]", "", line).strip()
            if len(content) > 3:
                info["Tujuan"] = content
            elif i + 1 < len(text_list):
                info["Tujuan"] = text_list[i+1].strip()
            break
    return info

# ==========================================
# 3. UI STREAMLIT
# ==========================================
st.set_page_config(page_title="OCR Scanner Surat", layout="centered")
st.title("📄 Pemindai Surat Otomatis")
st.write("Ambil foto dokumen, biarkan AI bekerja.")

@st.cache_resource
def load_reader():
    return easyocr.Reader(['id', 'en'], gpu=False)

reader = load_reader()

# Fitur Ambil Gambar dari Kamera HP
source = st.radio("Pilih Sumber Gambar:", ["Kamera", "Upload File"])

if source == "Kamera":
    img_file = st.camera_input("Ambil foto")
else:
    img_file = st.file_uploader("Pilih file gambar", type=["jpg", "png", "jpeg"])

if img_file:
    image = Image.open(img_file)
    img_array = np.array(image)
    
    # --- Tambahan Pre-processing ---
    # Ubah ke Grayscale dan naikkan kontras
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    # Upscaling jika gambar terlalu kecil
    resized = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    
    with st.spinner('Sedang memproses teks...'):
        result = reader.readtext(resized, detail=0, paragraph=True) # Tambah paragraph=True
        
        if result:
            info = extract_info(result)
            
            st.subheader("Konfirmasi Data")
            # User bisa edit jika ada yang salah sebelum simpan
            col1, col2 = st.columns(2)
            with col1:
                nomor = st.text_input("Nomor Surat", info["Nomor"])
                tanggal = st.text_input("Tanggal", info["Tanggal"])
            with col2:
                perihal = st.text_input("Perihal", info["Perihal"])
                tujuan = st.text_input("Tujuan", info["Tujuan"])
            
            data_final = {
                "Nomor": nomor,
                "Tanggal": tanggal,
                "Perihal": perihal,
                "Tujuan": tujuan
            }

            if st.button("🚀 Simpan ke Google Sheets"):
                success = save_to_google_sheets(data_final)
                if success:
                    st.success("Data berhasil masuk ke Google Sheets!")
                    st.balloons()
        else:
            st.warning("Teks tidak terdeteksi. Coba ambil foto lebih dekat dan terang.")
