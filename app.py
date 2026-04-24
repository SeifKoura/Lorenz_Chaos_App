import streamlit as st
import numpy as np
import soundfile as sf
import librosa
import io
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from audio_recorder_streamlit import audio_recorder

# ===============================
# PAGE CONFIGURATION
# ===============================
st.set_page_config(page_title="Lorenz Audio Cryptography", layout="wide")
st.title("🔐 Advanced Lorenz Chaos Audio Encryption")
st.markdown("Secure your audio files using block-permutation and non-linear diffusion driven by chaotic attractors.")

# ===============================
# MATH & ENCRYPTION FUNCTIONS
# ===============================
sigma = 10
rho = 28
beta = 2.667
dt = 0.001

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

def create_audio_download(audio_array, fs, filename):
    buffer = io.BytesIO()
    sf.write(buffer, audio_array, fs, format='WAV')
    return buffer.getvalue()

# ===============================
# UI COMPONENTS
# ===============================
st.sidebar.header("🔑 1. Encryption Key (True Password)")
x0 = st.sidebar.number_input("Enter x0:", value=0.100000, format="%.6f", step=0.000001)
y0 = st.sidebar.number_input("Enter y0:", value=0.000000, format="%.6f", step=0.000001)
z0 = st.sidebar.number_input("Enter z0:", value=0.000000, format="%.6f", step=0.000001)

st.sidebar.markdown("---")
st.sidebar.header("🕵️ 2. Hacker Mode (Decryption Test)")
h_x0 = st.sidebar.number_input("Hacker x0:", value=x0 + 0.000001, format="%.6f", step=0.000001)
h_y0 = st.sidebar.number_input("Hacker y0:", value=y0, format="%.6f", step=0.000001)
h_z0 = st.sidebar.number_input("Hacker z0:", value=z0, format="%.6f", step=0.000001)

# ===============================
# AUDIO INPUT HANDLING
# ===============================
st.markdown("### 🎙️ Audio Input")
input_method = st.radio("Choose how to provide audio:", ["Upload File", "Record Microphone"], horizontal=True)

voice = None
fs = None
TARGET_SR = 44100 

if input_method == "Upload File":
    uploaded_file = st.file_uploader("Upload an audio file (WAV, MP3, FLAC, OGG, M4A)", type=["wav", "mp3", "flac", "ogg", "m4a"])
    if uploaded_file is not None:
        with st.spinner("Processing uploaded file..."):
            voice, fs = librosa.load(uploaded_file, sr=TARGET_SR, mono=True)
        st.success("✓ File loaded successfully!")
        st.audio(uploaded_file)

elif input_method == "Record Microphone":
    st.info("Click the microphone icon below to start recording. Click again to stop.")
    audio_bytes = audio_recorder(text="", icon_size="2x", neutral_color="#6aa36f", recording_color="#e83838")
    if audio_bytes:
        with st.spinner("Processing recording..."):
            voice, fs = librosa.load(io.BytesIO(audio_bytes), sr=TARGET_SR, mono=True)
        st.success("✓ Recording captured successfully!")
        preview_audio = create_audio_download(voice, fs, "preview.wav")
        st.audio(preview_audio, format="audio/wav")

# ===============================
# PIPELINE EXECUTION
# ===============================
if voice is not None and fs is not None:
    steps = len(voice)
    
    if st.button("🚀 Run Cryptography Pipeline", type="primary"):
        with st.spinner("Executing Chaotic Math Pipeline..."):
            start_time = time.time()
            
            # --- 1. TRUE ENCRYPTION ---
            xs, ys, zs = generate_chaos(steps + 6000, x0, y0, z0)
            seed_x, seed_y = derive_seeds(x0, y0, z0)
            cx_key = nist_pipeline(xs, ys, zs, seed=seed_x, target_len=steps)
            cy_key = nist_pipeline(ys, zs, xs, seed=seed_y, target_len=steps)
            
            cx = xs[5000:5000 + steps]
            block_size = 500
            num_blocks = steps // block_size
            voice_blocks = voice[:num_blocks * block_size].reshape(num_blocks, block_size)
            
            block_chaos = cx[:num_blocks * block_size:block_size]
            block_perm = np.argsort(block_chaos)
            shuffled_blocks = voice_blocks[block_perm].flatten()
            
            mask = np.sin(cy_key[:len(shuffled_blocks)] * 10)
            encrypted = shuffled_blocks * (1 + 0.1 * mask) + (0.2 * mask)
            encrypted_norm = np.clip(encrypted, -1.0, 1.0).astype(np.float32)
            
            # --- 2. HACKER DECRYPTION ---
            xs_h, ys_h, zs_h = generate_chaos(steps + 6000, h_x0, h_y0, h_z0)
            seed_hx, seed_hy = derive_seeds(h_x0, h_y0, h_z0)
            cx_h = xs_h[5000:5000 + steps]
            cy_key_h = nist_pipeline(ys_h, zs_h, xs_h, seed=seed_hy, target_len=steps)
            
            mask_h = np.sin(cy_key_h[:len(encrypted)] * 10)
            unmixed_h = (encrypted - (0.2 * mask_h)) / (1 + 0.1 * mask_h)
            
            block_chaos_h = cx_h[:num_blocks * block_size:block_size]
            block_perm_h = np.argsort(block_chaos_h)
            inv_block_map_h = np.zeros_like(block_perm_h)
            inv_block_map_h[block_perm_h] = np.arange(len(block_perm_h))
            
            unmixed_blocks_h = unmixed_h[:num_blocks * block_size].reshape(num_blocks, block_size)
            decrypted_hacker = np.clip(unmixed_blocks_h[inv_block_map_h].flatten(), -1.0, 1.0).astype(np.float32)

            # --- 3. SYSTEM BASELINE ---
            inv_block_map = np.zeros_like(block_perm)
            inv_block_map[block_perm] = np.arange(len(block_perm))
            unmixed_blocks = unmixed_h if (h_x0 == x0 and h_y0 == y0 and h_z0 == z0) else (encrypted - (0.2 * mask)) / (1 + 0.1 * mask)
            decrypted_correct = np.clip(unmixed_blocks.reshape(num_blocks, block_size)[inv_block_map].flatten(), -1.0, 1.0).astype(np.float32)

        # Logic Check for UI
        hacker_success = (h_x0 == x0) and (h_y0 == y0) and (h_z0 == z0)

        # ===============================
        # UI RESULTS & PLAYERS
        # ===============================
        st.markdown("### 🎧 Results & Playback")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.warning("🔒 Encrypted Audio")
            enc_audio = create_audio_download(encrypted_norm, fs, "encrypted.wav")
            st.audio(enc_audio, format="audio/wav")

        with col2:
            if hacker_success: st.success("🟢 Hacker Test: SUCCESS (Key Matched!)")
            else: st.error("🔴 Hacker Test: FAILED (Wrong Key)")
            h_audio = create_audio_download(decrypted_hacker, fs, "hacker.wav")
            st.audio(h_audio, format="audio/wav")

        with col3:
            st.info("🔵 System Baseline (Perfect Key)")
            c_audio = create_audio_download(decrypted_correct, fs, "correct.wav")
            st.audio(c_audio, format="audio/wav")

        # ===============================
        # PLOTLY INTERACTIVE GRAPHS
        # ===============================
        n = min(num_blocks * block_size, 50000)
        t_axis = np.linspace(0, n / fs, n)

        fig = make_subplots(
            rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.07,
            subplot_titles=("1. Original Voice", "2. Encrypted", "3. Hacker Decryption", "4. System Baseline")
        )

        fig.add_trace(go.Scatter(x=t_axis, y=voice[:n], line=dict(color='#5c92c2', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=t_axis, y=encrypted_norm[:n], line=dict(color='#ff8c00', width=1)), row=2, col=1)
        fig.add_trace(go.Scatter(x=t_axis, y=decrypted_hacker[:n], line=dict(color=('#28a745' if hacker_success else '#dc3545'), width=1)), row=3, col=1)
        fig.add_trace(go.Scatter(x=t_axis, y=decrypted_correct[:n], line=dict(color='#007bff', width=1)), row=4, col=1)

        fig.update_layout(height=900, template="plotly_dark", showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        fig.update_yaxes(title_text="Amp", range=[-1.1, 1.1])
        fig.update_xaxes(title_text="Time (s)", row=4, col=1)
        st.plotly_chart(fig, use_container_width=True)