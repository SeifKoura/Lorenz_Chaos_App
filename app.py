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

st.set_page_config(page_title="Lorenz Audio Cryptography", layout="wide")

st.markdown("""
    <style>
    button, div[role="button"], .stNumberInput button {
        cursor: pointer !important;
    }
    </style>
""", unsafe_allow_html=True)

if st.sidebar.button("Reset Entire App"):
    for key in st.session_state.keys():
        del st.session_state[key]
    st.rerun()

st.markdown("<h4 style='opacity: 0.6; margin-bottom: -20px; font-weight: 400;'>House Of Waves</h4>", unsafe_allow_html=True)
st.title("Advanced Lorenz Chaos Audio Encryption")

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

# ─────────────────────────────────────────────
# SMTP provider registry
# Each entry: (display_name, host, port, use_ssl, sender_hint, pass_hint)
# use_ssl=True  → smtplib.SMTP_SSL  (implicit TLS from the start, e.g. port 465)
# use_ssl=False → smtplib.SMTP + STARTTLS (explicit upgrade, e.g. port 587)
# ─────────────────────────────────────────────
PROVIDERS = {
    "Gmail": {
        "host": "smtp.gmail.com", "port": 587, "ssl": False,
        "sender_hint": "yourname@gmail.com",
        "pass_hint":   "16-char App Password (Google Account → Security → App Passwords)",
    },
    "Outlook / Hotmail": {
        "host": "smtp-mail.outlook.com", "port": 587, "ssl": False,
        "sender_hint": "yourname@outlook.com",
        "pass_hint":   "Your regular Outlook password",
    },
    "Yahoo Mail": {
        "host": "smtp.mail.yahoo.com", "port": 465, "ssl": True,
        "sender_hint": "yourname@yahoo.com",
        "pass_hint":   "App Password (Yahoo Account Security → Generate app password)",
    },
    "Mailtrap Sandbox (testing)": {
        "host": "sandbox.smtp.mailtrap.io", "port": 587, "ssl": False,
        "sender_hint": "noreply@houseofwaves.io",
        "pass_hint":   "Mailtrap SMTP password from sandbox inbox → SMTP Settings",
    },
    "Custom SMTP": {
        "host": "", "port": 587, "ssl": False,
        "sender_hint": "you@yourdomain.com",
        "pass_hint":   "Your SMTP password",
    },
}

def send_audio_email(
    host: str,
    port: int,
    use_ssl: bool,
    smtp_user: str,
    smtp_pass: str,
    sender: str,
    recipient: str,
    audio_bytes: bytes,
    filename: str = "authorized_output.wav",
) -> tuple[bool, str]:
    """
    Generic SMTP sender. Works with any provider — real inboxes or Mailtrap sandbox.
    use_ssl=True  → implicit TLS (SMTP_SSL, port 465 style)
    use_ssl=False → STARTTLS upgrade (port 587 style)
    """
    try:
        msg = MIMEMultipart()
        msg["From"]    = sender
        msg["To"]      = recipient
        msg["Subject"] = "Lorenz Chaos — Authorized Decrypted Audio"

        body = (
            "Hello,\n\n"
            "Please find the authorized decrypted audio output attached.\n"
            "This file was produced by the Lorenz Chaos Audio Encryption system.\n\n"
            "— House Of Waves"
        )
        msg.attach(MIMEText(body, "plain"))

        part = MIMEBase("audio", "wav")
        part.set_payload(audio_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

        if use_ssl:
            # Implicit TLS — connection is encrypted from byte 1
            with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.sendmail(sender, recipient, msg.as_string())
        else:
            # STARTTLS — start plain, upgrade to TLS, re-identify
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()   # must re-identify after TLS upgrade
                server.login(smtp_user, smtp_pass)
                server.sendmail(sender, recipient, msg.as_string())

        return True, f"✅ Email delivered to {recipient}!"

    except smtplib.SMTPAuthenticationError:
        return False, (
            "Authentication failed. "
            "For Gmail use an App Password, not your regular password. "
            "For Outlook use your normal password. Check the hint in the sidebar."
        )
    except smtplib.SMTPConnectError as e:
        return False, f"Could not connect to {host}:{port} — {e}"
    except smtplib.SMTPRecipientsRefused:
        return False, f"Recipient address rejected by server: {recipient}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


# ─────────────────────────────────────────────
# Sidebar — Encryption Key
# ─────────────────────────────────────────────
st.sidebar.header("1. Encryption Key (True Password)")
x0 = st.sidebar.number_input("Enter x0:", value=0.100000, format="%.6f", step=0.000001, key="true_x")
y0 = st.sidebar.number_input("Enter y0:", value=0.000000, format="%.6f", step=0.000001, key="true_y")
z0 = st.sidebar.number_input("Enter z0:", value=0.000000, format="%.6f", step=0.000001, key="true_z")

st.sidebar.markdown("---")
st.sidebar.header("2. Hacker Mode (Decryption Test)")
h_x0 = st.sidebar.number_input("Hacker x0:", value=x0 + 0.000001, format="%.6f", step=0.000001, key="hacker_x")
h_y0 = st.sidebar.number_input("Hacker y0:", value=y0, format="%.6f", step=0.000001, key="hacker_y")
h_z0 = st.sidebar.number_input("Hacker z0:", value=z0, format="%.6f", step=0.000001, key="hacker_z")

# ─────────────────────────────────────────────
# Sidebar — Email Configuration
# ─────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.header("3. Email Delivery")

selected_provider = st.sidebar.selectbox("Provider", list(PROVIDERS.keys()))
prov = PROVIDERS[selected_provider]

# Gmail / Yahoo note
if selected_provider == "Gmail":
    st.sidebar.info("Gmail requires an **App Password**, not your account password.\n\nGoogle Account → Security → 2-Step Verification → App Passwords.")
elif selected_provider == "Yahoo Mail":
    st.sidebar.info("Yahoo requires an **App Password**.\n\nYahoo Account Security → Generate app password.")

# Custom SMTP: let user enter host/port/TLS
if selected_provider == "Custom SMTP":
    custom_host = st.sidebar.text_input("SMTP Host", placeholder="smtp.yourdomain.com")
    custom_port = st.sidebar.number_input("Port", value=587, min_value=1, max_value=65535)
    custom_ssl  = st.sidebar.checkbox("Use implicit SSL (port 465 style)", value=False)
    prov = {"host": custom_host, "port": int(custom_port), "ssl": custom_ssl,
            "sender_hint": prov["sender_hint"], "pass_hint": prov["pass_hint"]}

mt_user   = st.sidebar.text_input("SMTP Username / Email", placeholder=prov["sender_hint"])
mt_pass   = st.sidebar.text_input("Password", placeholder=prov["pass_hint"], type="password")
mt_sender = st.sidebar.text_input("From address", value=prov["sender_hint"])
mt_to     = st.sidebar.text_input("Send to (recipient)", placeholder="recipient@example.com")


# ─────────────────────────────────────────────
# Audio input
# ─────────────────────────────────────────────
st.markdown("### Audio Input")
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
            if np.max(np.abs(voice)) > 0:
                voice = voice / np.max(np.abs(voice))
        st.success("✓ Recording captured!")
        st.audio(audio_bytes, format="audio/wav")


# ─────────────────────────────────────────────
# Encrypt & Analyse
# ─────────────────────────────────────────────
if voice is not None:
    if st.button("Encrypt & Analyze Signal", type="primary"):
        with st.spinner("Executing Chaotic Math..."):
            steps = len(voice)

            xs, ys, zs = generate_chaos(steps + 6000, x0, y0, z0)
            seed_x, seed_y = derive_seeds(x0, y0, z0)
            cx_key = nist_pipeline(xs, ys, zs, seed=seed_x, target_len=steps)
            cy_key = nist_pipeline(ys, zs, xs, seed=seed_y, target_len=steps)

            block_size = 500
            num_blocks = steps // block_size
            voice_trimmed = voice[:num_blocks * block_size]
            voice_blocks  = voice_trimmed.reshape(num_blocks, block_size)

            block_perm = np.argsort(xs[5000:5000 + steps:block_size][:num_blocks])
            shuffled   = voice_blocks[block_perm].flatten()

            mask      = np.sin(cy_key[:len(shuffled)] * 10)
            encrypted = shuffled * (1 + 0.05 * mask) + (0.15 * mask)
            encrypted_norm = np.clip(encrypted, -1.0, 1.0).astype(np.float32)

            xs_h, ys_h, zs_h = generate_chaos(steps + 6000, h_x0, h_y0, h_z0)
            _, seed_hy = derive_seeds(h_x0, h_y0, h_z0)
            cy_key_h = nist_pipeline(ys_h, zs_h, xs_h, seed=seed_hy, target_len=steps)

            mask_h    = np.sin(cy_key_h[:len(encrypted)] * 10)
            unmixed_h = (encrypted - (0.15 * mask_h)) / (1 + 0.05 * mask_h)

            block_perm_h = np.argsort(xs_h[5000:5000 + steps:block_size][:num_blocks])
            inv_map_h    = np.zeros_like(block_perm_h)
            inv_map_h[block_perm_h] = np.arange(len(block_perm_h))
            decrypted_h  = np.clip(
                unmixed_h.reshape(num_blocks, block_size)[inv_map_h].flatten(), -1.0, 1.0
            )

            inv_map   = np.zeros_like(block_perm)
            inv_map[block_perm] = np.arange(len(block_perm))
            unmixed_c   = (encrypted - (0.15 * mask)) / (1 + 0.05 * mask)
            decrypted_c = np.clip(
                unmixed_c.reshape(num_blocks, block_size)[inv_map].flatten(), -1.0, 1.0
            )

        # Store authorized audio bytes in session state so the mail button can use them
        authorized_wav = create_audio_download(decrypted_c.astype(np.float32), fs)
        st.session_state["authorized_wav"] = authorized_wav

        hacker_success = (h_x0 == x0 and h_y0 == y0 and h_z0 == z0)

        st.markdown("### Results & Playback")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.warning("Encrypted Audio")
            st.audio(create_audio_download(encrypted_norm, fs), format="audio/wav")
        with c2:
            if hacker_success:
                st.success("Hacker: Match!")
            else:
                st.error("Hacker: Fail")
            st.audio(create_audio_download(decrypted_h.astype(np.float32), fs), format="audio/wav")
        with c3:
            st.info("Received (Authorized) Output")
            st.audio(authorized_wav, format="audio/wav")

        total_samples = len(shuffled)
        duration   = total_samples / fs
        plot_step  = max(1, total_samples // 30000)
        time_axis  = np.linspace(0, duration, total_samples)[::plot_step]

        fig = make_subplots(
            rows=4, cols=1, shared_xaxes=False, vertical_spacing=0.1,
            subplot_titles=(
                "1. Original Input", "2. Encrypted Signal",
                "3. Hacker Decryption Attempt", "4. Received (Authorized) Output"
            ),
        )
        fig.add_trace(go.Scatter(x=time_axis, y=voice[:total_samples][::plot_step], line=dict(color='#5c92c2', width=1), name="Original"),  row=1, col=1)
        fig.add_trace(go.Scatter(x=time_axis, y=encrypted_norm[::plot_step],        line=dict(color='#ff8c00', width=1), name="Encrypted"), row=2, col=1)
        fig.add_trace(go.Scatter(x=time_axis, y=decrypted_h[::plot_step],           line=dict(color=('#28a745' if hacker_success else '#dc3545'), width=1), name="Hacker"), row=3, col=1)
        fig.add_trace(go.Scatter(x=time_axis, y=decrypted_c[::plot_step],           line=dict(color='#007bff', width=1), name="Received"), row=4, col=1)

        fig.update_layout(height=1200, showlegend=False)
        for i in range(1, 5):
            fig.update_xaxes(title_text="Time (Seconds)", row=i, col=1, showgrid=True, gridwidth=0.5)
            fig.update_yaxes(title_text="Amp", range=[-1.1, 1.1], row=i, col=1, showgrid=True, gridwidth=0.5)

        st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

    # ─────────────────────────────────────────────
    # Email section  (shown once audio is ready)
    # ─────────────────────────────────────────────
    if "authorized_wav" in st.session_state:
        st.markdown("---")
        st.markdown("### 📧 Send Authorized Output via Email")

        all_filled = all([mt_user, mt_pass, mt_sender, mt_to, prov["host"]])

        if not all_filled:
            st.info("Fill in all email credentials in the sidebar to enable sending.")
        else:
            if st.button("Send Authorized Audio to Inbox", type="secondary"):
                with st.spinner(f"Connecting to {prov['host']}..."):
                    ok, result_msg = send_audio_email(
                        host        = prov["host"],
                        port        = prov["port"],
                        use_ssl     = prov["ssl"],
                        smtp_user   = mt_user,
                        smtp_pass   = mt_pass,
                        sender      = mt_sender,
                        recipient   = mt_to,
                        audio_bytes = st.session_state["authorized_wav"],
                    )
                if ok:
                    st.success(result_msg)
                else:
                    st.error(result_msg)
