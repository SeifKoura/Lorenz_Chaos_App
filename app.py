import streamlit as st
import numpy as np
import soundfile as sf
import librosa
import io
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from audio_recorder_streamlit import audio_recorder

# ===============================
# PAGE CONFIGURATION & CSS
# ===============================
st.set_page_config(page_title="Lorenz Audio Cryptography", layout="wide")

st.markdown("""
    <style>
    button, div[role="button"], .stNumberInput button {
        cursor: pointer !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- BRANDING ---
st.markdown("<h4 style='opacity: 0.6; margin-bottom: -20px; font-weight: 400;'>House Of Waves</h4>", unsafe_allow_html=True)
st.title("Advanced Lorenz Chaos Audio Encryption")

# ===============================
# EMAIL LOGIC (THE FREE WAY)
# ===============================
def send_email(recipient_email, audio_data, filename):
    # --- CONFIGURATION (Use Streamlit Secrets in production!) ---
    SENDER_EMAIL = "your-email@gmail.com" 
    SENDER_PASSWORD = "your-app-password" # 16 chars from Google App Passwords
    
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email
        msg['Subject'] = "House Of Waves: Authorized Audio Signal"

        body = "The encrypted signal has been processed. Attached is the Authorized (Decrypted) Output."
        msg.attach(MIMEText(body, 'plain'))

        part = MIMEBase('application', 'octet-stream')
        part.set_payload(audio_data)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename= {filename}")
        msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Mail Error: {e}")
        return False

# ===============================
# MATH & ENCRYPTION FUNCTIONS
# ===============================
sigma, rho, beta, dt = 10, 28, 2.667, 0.001

@st.cache_data
def generate_chaos(steps, x0, y0, z0):
    x, y, z = x0, y0, z0
    xs, ys, zs = [], [], []
    for _ in range(steps):
        dx = sigma * (y - x)
        dy = x * (rho - z) - y
        dz = x * y - beta * z
        x += dx * dt
        y += dy * dt
        z += dz * dt
        xs.append(x)
        ys.append(y)
        zs.append(z)
    return np.array(xs), np.array(ys), np.array(zs)

@st.cache_data
def nist_pipeline(xs, ys, zs, seed, target_len):
    rng = np.random.default_rng(seed)
    xs, ys, zs = xs[5000:], ys[5000:], zs[5000:]
    signal = np.mod(xs * ys + zs, 1)
    signal = (signal - np.min(signal)) / (np.max(signal) - np.min(signal))
    signal = np.mod(signal * 1e5, 1)
    signal = signal[::5]
    signal = np.mod(signal + np.roll(signal, 1), 1)
    signal = np.mod(signal + np.roll(signal, 7), 1)
    rng.shuffle(signal)
    key = np.uint16(signal * 65535)
    key = np.bitwise_xor(key, np.right_shift(key, 3))
    key = np.bitwise_xor(key, np.left_shift(key, 5))
    while len(key) < target_len:
        key = np.tile(key, 2)
    return key[:target_len].astype(np.float64) / 65535.0

def derive_seeds(rx, ry, rz):
    seed_x = int(abs(rx * 1e6 + ry * 1e3 + rz) * 1000) % (2**32)
    return seed_x, seed_x + 1

def create_audio_download(audio_array, fs):
    buffer = io.BytesIO()
    sf.write(buffer, audio_array, fs, format='WAV')
    return buffer.getvalue()

# ===============================
# SIDEBAR UI
# ===============================
st.sidebar.header("1. Encryption Key")
x0 = st.sidebar.number_input("Enter x0:", value=0.100000, format="%.6f", step=0.000001, key="true_x")
y0 = st.sidebar.number_input("Enter y0:", value=0.000000, format="%.6f", step=0.000001, key="true_y")
z0 = st.sidebar.number_input("Enter z0:", value=0.000000, format="%.6f", step=0.000001, key="true_z")

st.sidebar.markdown("---")
st.sidebar.header("2. Hacker Mode")
h_x0 = st.sidebar.number_input("Hacker x0:", value=x0 + 0.000001, format="%.6f", step=0.000001, key="hacker_x")

st.sidebar.markdown("---")
st.sidebar.header("3. Secure Delivery")
dest_email = st.sidebar.text_input("Recipient Email:", placeholder="agent@agency.com")

if st.sidebar.button("Reset Entire App"):
    for key in st.session_state.keys(): del st.session_state[key]
    st.rerun()

# ===============================
# AUDIO INPUT
# ===============================
st.markdown("### Audio Input")
input_method = st.radio("Choose source:", ["Upload File", "Record Microphone"], horizontal=True)

voice, fs = None, 44100
if input_method == "Upload File":
    uploaded_file = st.file_uploader("Upload Audio", type=["wav", "mp3", "flac"])
    if uploaded_file:
        voice, _ = librosa.load(uploaded_file, sr=fs, mono=True)
        st.audio(uploaded_file)
elif input_method == "Record Microphone":
    audio_bytes = audio_recorder(text="", icon_size="2x", neutral_color="#6aa36f")
    if audio_bytes:
        voice, _ = librosa.load(io.BytesIO(audio_bytes), sr=fs, mono=True)
        st.audio(audio_bytes, format="audio/wav")

# ===============================
# EXECUTION
# ===============================
if voice is not None:
    if st.button("Encrypt & Analyze Signal", type="primary"):
        with st.spinner("Processing..."):
            steps = len(voice)
            xs, ys, zs = generate_chaos(steps + 6000, x0, y0, z0)
            seed_x, seed_y = derive_seeds(x0, y0, z0)
            cx_key = nist_pipeline(xs, ys, zs, seed=seed_x, target_len=steps)
            cy_key = nist_pipeline(ys, zs, xs, seed=seed_y, target_len=steps)
            
            block_size = 500
            num_blocks = steps // block_size
            voice_trimmed = voice[:num_blocks * block_size]
            voice_blocks = voice_trimmed.reshape(num_blocks, block_size)
            
            block_perm = np.argsort(xs[5000:5000 + steps:block_size][:num_blocks])
            shuffled = voice_blocks[block_perm].flatten()
            
            mask = np.sin(cy_key[:len(shuffled)] * 10)
            encrypted = shuffled * (1 + 0.05 * mask) + (0.15 * mask)
            encrypted_norm = np.clip(encrypted, -1.0, 1.0).astype(np.float32)
            
            # AUTHORIZED DECRYPTION
            inv_map = np.zeros_like(block_perm); inv_map[block_perm] = np.arange(len(block_perm))
            unmixed_c = (encrypted - (0.15 * mask)) / (1 + 0.05 * mask)
            decrypted_c = np.clip(unmixed_c.reshape(num_blocks, block_size)[inv_map].flatten(), -1.0, 1.0)
            
            # Store in session so the email button can find it
            st.session_state.final_audio = create_audio_download(decrypted_c.astype(np.float32), fs)

        st.markdown("### Results")
        col1, col2 = st.columns(2)
        with col1:
            st.warning("Encrypted Signal")
            st.audio(create_audio_download(encrypted_norm, fs))
        with col2:
            st.info("Authorized Output")
            st.audio(st.session_state.final_audio)

        if dest_email:
            if st.button("📧 Dispatch to Authorized Recipient"):
                with st.spinner("Sending secure mail..."):
                    success = send_email(dest_email, st.session_state.final_audio, "authorized_output.wav")
                    if success: st.success(f"Signal sent to {dest_email}")
