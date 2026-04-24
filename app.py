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

if st.sidebar.button("♻️ Reset Entire App"):
    for key in st.session_state.keys():
        del st.session_state[key]
    st.rerun()

st.title("🔐 Advanced Lorenz Chaos Audio Encryption")

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
input_method = st.radio("Choose source:", ["Upload File", "Record Microphone"], horizontal=True)

voice, fs = None, 44100

if input_method == "Upload File":
    uploaded_file = st.file_uploader("Upload Audio", type=["wav", "mp3", "flac", "ogg", "m4a"])
    if uploaded_file:
        with st.spinner("Loading..."):
            voice, _ = librosa.load(uploaded_file, sr=fs, mono=True)
        st.audio(uploaded_file)

elif input_method == "Record Microphone":
    st.info("Manual Toggle: Click once to start, once more to stop.")
    audio_bytes = audio_recorder(
        text="", icon_size="2x", neutral_color="#6aa36f", recording_color="#e83838",
        energy_threshold=(-1.0, 1.0), pause_threshold=60.0 
    )
    if audio_bytes:
        with st.spinner("Processing..."):
            voice, _ = librosa.load(io.BytesIO(audio_bytes), sr=fs, mono=True)
            if np.max(np.abs(voice)) > 0: voice = voice / np.max(np.abs(voice))
        st.success("✓ Recording captured!")
        st.audio(audio_bytes, format="audio/wav")

# ===============================
# PIPELINE EXECUTION
# ===============================
if voice is not None:
    if st.button("🚀 Run Cryptography Pipeline", type="primary"):
        with st.spinner("Executing Chaotic Math..."):
            steps = len(voice)
            
            # 1. ENCRYPTION KEYS
            xs, ys, zs = generate_chaos(steps + 6000, x0, y0, z0)
            seed_x, seed_y = derive_seeds(x0, y0, z0)
            cx_key = nist_pipeline(xs, ys, zs, seed=seed_x, target_len=steps)
            cy_key = nist_pipeline(ys, zs, xs, seed=seed_y, target_len=steps)
            
            # 2. ENCRYPTION
            block_size = 500
            num_blocks = steps // block_size
            voice_trimmed = voice[:num_blocks * block_size]
            voice_blocks = voice_trimmed.reshape(num_blocks, block_size)
            
            block_perm = np.argsort(xs[5000:5000 + steps:block_size][:num_blocks])
            shuffled = voice_blocks[block_perm].flatten()
            
            mask = np.sin(cy_key[:len(shuffled)] * 10)
            encrypted = shuffled * (1 + 0.05 * mask) + (0.15 * mask)
            encrypted_norm = np.clip(encrypted, -1.0, 1.0).astype(np.float32)
            
            # 3. HACKER ATTEMPT
            xs_h, ys_h, zs_h = generate_chaos(steps + 6000, h_x0, h_y0, h_z0)
            _, seed_hy = derive_seeds(h_x0, h_y0, h_z0)
            cy_key_h = nist_pipeline(ys_h, zs_h, xs_h, seed=seed_hy, target_len=steps)
            
            mask_h = np.sin(cy_key_h[:len(encrypted)] * 10)
            unmixed_h = (encrypted - (0.15 * mask_h)) / (1 + 0.05 * mask_h)
            
            block_perm_h = np.argsort(xs_h[5000:5000 + steps:block_size][:num_blocks])
            inv_map_h = np.zeros_like(block_perm_h); inv_map_h[block_perm_h] = np.arange(len(block_perm_h))
            decrypted_h = np.clip(unmixed_h.reshape(num_blocks, block_size)[inv_map_h].flatten(), -1.0, 1.0)

            # 4. SYSTEM BASELINE
            inv_map = np.zeros_like(block_perm); inv_map[block_perm] = np.arange(len(block_perm))
            unmixed_c = (encrypted - (0.15 * mask)) / (1 + 0.05 * mask)
            decrypted_c = np.clip(unmixed_c.reshape(num_blocks, block_size)[inv_map].flatten(), -1.0, 1.0)

        hacker_success = (h_x0 == x0 and h_y0 == y0 and h_z0 == z0)
        
        st.markdown("### 🎧 Results & Playback")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.warning("🔒 Encrypted Audio")
            st.audio(create_audio_download(encrypted_norm, fs), format="audio/wav")
        with c2:
            if hacker_success: st.success("🟢 Hacker: Match!") 
            else: st.error("🔴 Hacker: Fail")
            st.audio(create_audio_download(decrypted_h.astype(np.float32), fs), format="audio/wav")
        with c3:
            st.info("🔵 System Baseline")
            st.audio(create_audio_download(decrypted_c.astype(np.float32), fs), format="audio/wav")

        # ===============================
        # DYNAMIC SIGNAL ANALYSIS (SMART PLOTTING)
        # ===============================
        total_samples = len(shuffled)
        duration = total_samples / fs
        
        # Target ~30k points for smooth interactivity
        plot_step = max(1, total_samples // 30000)
        
        # Build dynamic time axis in seconds
        time_axis = np.linspace(0, duration, total_samples)[::plot_step]

        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.07,
                           subplot_titles=("1. Original Input", "2. Encrypted (Chaos Mask)", "3. Hacker Decryption Attempt", "4. Correct System Baseline"))
        
        # decimated data for performance
        fig.add_trace(go.Scatter(x=time_axis, y=voice[:total_samples][::plot_step], line=dict(color='#5c92c2', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=time_axis, y=encrypted_norm[::plot_step], line=dict(color='#ff8c00', width=1)), row=2, col=1)
        fig.add_trace(go.Scatter(x=time_axis, y=decrypted_h[::plot_step], line=dict(color=('#28a745' if hacker_success else '#dc3545'), width=1)), row=3, col=1)
        fig.add_trace(go.Scatter(x=time_axis, y=decrypted_c[::plot_step], line=dict(color='#007bff', width=1)), row=4, col=1)
        
        fig.update_layout(height=1000, template="plotly_dark", showlegend=False, 
                          plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        fig.update_yaxes(title_text="Amp", range=[-1.1, 1.1])
        fig.update_xaxes(title_text="Time (Seconds)", row=4, col=1)
        
        st.plotly_chart(fig, use_container_width=True, config={'displaylogo': False})
