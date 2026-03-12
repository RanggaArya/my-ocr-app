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

st.markdown("""
    <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
        <h4 style="margin-top: 0px;">📱 Cara Penggunaan di HP:</h4>
        1. Klik area <b>Drag and drop file here</b> atau <b>Browse files</b> di bawah.<br>
        2. Pilih opsi <b>Kamera</b> (Take Photo) yang muncul di layar HP kamu.<br>
        3. Arahkan kamera secara <i>Full-Screen</i> ke dokumen, pastikan fokus dan terang.<br>
        4. Jepret, dan AI akan langsung memprosesnya!
    </div>
""", unsafe_allow_html=True)

@st.cache_resource
def load_reader():
    return easyocr.Reader(['id', 'en'], gpu=False)

reader = load_reader()

# Cukup gunakan satu uploader ini. Di HP, ini otomatis bisa jadi tombol pemanggil Kamera Bawaan.
img_file = st.file_uploader("📸 Scan Dokumen (Klik di sini)", type=["jpg", "png", "jpeg"])

if img_file:
    # Tampilkan preview gambar yang sudah diambil
    image = Image.open(img_file)
    st.image(image, caption="Gambar yang akan diproses", use_column_width=True)
    
    img_array = np.array(image)
    
    # --- Pre-processing Gambar agar lebih mudah dibaca OCR ---
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    
    with st.spinner('Sedang memproses teks dokumen...'):
        # OCR Process (tambahkan paragraph=True agar baca kalimat lebih baik)
        result = reader.readtext(gray, detail=0, paragraph=True)
        
        if result:
            info = extract_info(result)
            
            st.subheader("Konfirmasi Data")
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
            st.warning("Teks tidak terdeteksi. Silakan coba foto ulang.")
