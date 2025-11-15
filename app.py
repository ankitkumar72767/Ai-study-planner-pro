# app.py — AI Study Planner Pro (Premium Blue Dashboard)
import streamlit as st
import datetime
import time
import io
import re
from textwrap import wrap
import pandas as pd
import plotly.express as px
from openai import OpenAI

# Optional PDF export
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    REPORTLAB = True
except Exception:
    REPORTLAB = False

# ---------------- Page config ----------------
st.set_page_config(page_title="AI Study Planner Pro", page_icon="📘", layout="wide")

# ---------------- Session init ----------------
def init_session():
    st.session_state.setdefault("plans", [])
    st.session_state.setdefault("last_plan_html", None)
    st.session_state.setdefault("last_plan_raw", None)
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("timetable", None)
    st.session_state.setdefault("progress", {})
    st.session_state.setdefault("weak_topics", {})
    st.session_state.setdefault("streak", 0)
init_session()

# ---------------- Helpers ----------------
def export_pdf(text, title="Study Plan"):
    if not REPORTLAB:
        return None
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    margin = 40
    y = h - margin
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, title)
    y -= 22
    c.setFont("Helvetica", 11)
    for line in text.splitlines():
        for part in wrap(line, 95):
            if y < 60:
                c.showPage()
                c.setFont("Helvetica", 11)
                y = h - margin
            c.drawString(margin, y, part)
            y -= 14
    c.save()
    buf.seek(0)
    return buf

def sanitize_text(s: str) -> str:
    # Remove harmful tags and stray control chars
    s = re.sub(r"<[^a-zA-Z/][^>]*>", "", s)
    s = s.replace("< ", "&lt; ").replace(" >", " &gt;")
    return s.strip()

def convert_markdown_table_to_html(md: str) -> str:
    """Convert simple markdown tables and headings/lists to HTML blocks."""
    if not md:
        return ""
    lines = md.splitlines()
    html = ""
    inside = False
    for raw in lines:
        line = raw.rstrip()
        # skip separator rows
        if re.match(r"^\|?\s*-[-\s|]*\|?$", line.strip()):
            continue
        if line.strip().startswith("|") and line.strip().endswith("|"):
            cols = [c.strip() for c in line.strip().split("|")[1:-1]]
            if not inside:
                inside = True
                html += "<table class='tbl'><thead><tr>"
                html += "".join([f"<th>{c}</th>" for c in cols])
                html += "</tr></thead><tbody>"
            else:
                html += "<tr>" + "".join([f"<td>{c}</td>" for c in cols]) + "</tr>"
        else:
            if inside:
                inside = False
                html += "</tbody></table><br>"
            if line.strip().startswith("### "):
                html += f"<h3>{line.strip()[4:]}</h3>"
            elif line.strip().startswith("## "):
                html += f"<h2>{line.strip()[3:]}</h2>"
            elif line.strip().startswith("- "):
                html += f"<li>{line.strip()[2:]}</li>"
            elif line.strip():
                html += f"<p>{line.strip()}</p>"
    if inside:
        html += "</tbody></table>"
    return html

def pretty_split_plan(raw: str):
    """Attempt to split plan into Weekly / Daily / Tips. Fallbacks to raw."""
    if not raw:
        return "", "", ""
    lower = raw.lower()
    # heuristics for splitting
    start_weekly = raw.find("weekly")
    start_daily = raw.lower().find("daily")
    start_tips = raw.lower().find("tips")
    if start_daily != -1 and start_tips != -1:
        weekly = raw[:start_daily]
        daily = raw[start_daily:start_tips]
        tips = raw[start_tips:]
    elif start_daily != -1:
        weekly = raw[:start_daily]
        daily = raw[start_daily:]
        tips = ""
    elif start_tips != -1:
        weekly = raw[:start_tips]
        daily = ""
        tips = raw[start_tips:]
    else:
        # fallback: split into three equal parts (best-effort)
        parts = raw.splitlines()
        n = len(parts) or 1
        p1 = parts[:max(1, n//3)]
        p2 = parts[max(1, n//3):max(1, 2*n//3)]
        p3 = parts[max(1, 2*n//3):]
        weekly = "\n".join(p1)
        daily = "\n".join(p2)
        tips = "\n".join(p3)
    return weekly, daily, tips

# ---------------- UI helpers ----------------
def render_plan_card(name, weekly_html, daily_html, tips_html):
    return f"""
    <div style="background:white;padding:28px;border-radius:16px;
                box-shadow:0 14px 40px rgba(11,66,255,0.08);font-family:Inter;">
      <h1 style="font-size:34px;margin:6px 0 8px 0;color:#0b66ff;font-weight:800;text-align:center">
        📘 Weekly Study Plan — {name or 'Student'}
      </h1>
      <p style="text-align:center;color:#64748b;margin-bottom:20px">AI-generated personalized plan</p>

      <h2 style="color:#0b66ff;font-size:20px;margin-bottom:6px">📅 Weekly Overview</h2>
      <div style="padding:14px;border-left:6px solid #0b66ff;background:#f5f9ff;border-radius:10px;margin-bottom:18px;">{weekly_html}</div>

      <h2 style="color:#0b66ff;font-size:20px;margin-bottom:6px">🕒 Daily Breakdown</h2>
      <div style="padding:14px;border-left:6px solid #0284c7;background:#f0f7ff;border-radius:10px;margin-bottom:18px;">{daily_html}</div>

      <h2 style="color:#0b66ff;font-size:20px;margin-bottom:6px">💡 Study Tips</h2>
      <div style="padding:14px;border-left:6px solid #f59e0b;background:#fff8e6;border-radius:10px;margin-bottom:6px;">{tips_html}</div>
    </div>
    """

# ---------------- Smart timetable ----------------
def generate_smart_timetable(subjects, weekly_hours, deadline, intensity, progress):
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    slots = ["Morning (9-12)","Afternoon (1-4)","Evening (6-8)"]
    if not subjects:
        subjects = ["General"]
    weights = {s: 1 + progress.get(s, 0)*0.1 for s in subjects}
    total_weight = sum(weights.values()) or 1
    subject_hours = {s: round((weights[s]/total_weight) * weekly_hours, 2) for s in subjects}
    timetable = []
    subject_cycle = list(subjects) * 10
    idx = 0
    for d in days:
        for sl in slots:
            sb = subject_cycle[idx % len(subject_cycle)]
            hrs = round(subject_hours.get(sb, 0)/3 if sb in subject_hours else round(weekly_hours/21,2), 2)
            timetable.append([d, sl, sb, hrs])
            idx += 1
    df = pd.DataFrame(timetable, columns=["Day","Slot","Subject","Hours"])
    pivot = df.pivot(index="Slot", columns="Day", values="Subject")
    summary = "Weekly spaced revision recommended."
    return df, pivot, subject_hours, summary

# ---------------- Premium Blue CSS ----------------
st.markdown("""
<style>
/* typography */
body { font-family: Inter, system-ui, -apple-system, 'Segoe UI', Roboto, Arial; background:#f6f9ff; color:#0f1724; }

/* header */
h1.main-title { font-size:56px; font-weight:900; color:#0b66ff; text-align:center; margin:10px 0 6px 0;}
.main-sub { text-align:center; color:#475569; margin-bottom:18px; font-size:14px;}

/* cards */
.section { background:#ffffff; padding:18px; border-radius:12px; margin-bottom:18px;
          border-left:6px solid rgba(11,102,255,0.12); box-shadow:0 8px 30px rgba(15,23,36,0.04);}
.section:hover { transform: translateY(-4px); transition: all .18s ease; }

/* table style */
.tbl { width:100%; border-collapse:collapse; font-size:14px; border-radius:10px; overflow:hidden; box-shadow:0 8px 26px rgba(11,66,255,0.04); }
.tbl th { background: linear-gradient(90deg,#0b66ff,#00a3ff); color:white; padding:10px; text-align:left; }
.tbl td { background:white; padding:10px; border-bottom:1px solid #eef2ff; }

/* chat bubbles */
.chat-user { background:linear-gradient(90deg,#0b66ff,#00a3ff); color:white; padding:10px 12px; border-radius:14px; max-width:80%; margin:8px 0; }
.chat-ai { background:#eef6ff; color:#072146; padding:10px 12px; border-radius:14px; max-width:80%; margin:8px 0; }

/* buttons */
.stButton>button { background: linear-gradient(90deg,#0b66ff,#00a3ff); color:white !important; border:none; padding:8px 14px; border-radius:10px; font-weight:700; box-shadow:0 10px 30px rgba(11,102,255,0.12); }
.stButton>button:hover { transform: translateY(-3px); box-shadow:0 18px 36px rgba(11,102,255,0.16); }

/* inputs focus */
input, textarea, select { outline-color:#0b66ff !important; }

/* footer */
.footer { text-align:center; color:#94a3b8; margin-top:20px; font-size:13px; }
</style>
""", unsafe_allow_html=True)

# ---------------- Sidebar + Header ----------------
st.sidebar.title("AI Study Planner Pro")
page = st.sidebar.radio("Navigate", ["Planner","Dashboard","Chatbot","Calendar","History","About"])
st.markdown("<h1 class='main-title'>📘 AI Study Planner Pro</h1>", unsafe_allow_html=True)
st.markdown("<div class='main-sub'>Premium Blue Dashboard</div>", unsafe_allow_html=True)

# ---------------- Planner ----------------
if page == "Planner":
    left, right = st.columns([1,2], gap="large")

    with left:
        st.markdown("<div class='section'>", unsafe_allow_html=True)
        # student name default intentionally EMPTY
        student_name = st.text_input("Student name", "", help="Leave blank to keep as 'Student'")
        subjects_input = st.text_input("Subjects (comma separated)", "Math, DBMS, AI")
        weekly_hours = st.number_input("Weekly study hours", min_value=1, max_value=168, value=20)
        exam_date = st.date_input("Exam / Deadline date", datetime.date.today())
        intensity = st.slider("Focus intensity (1-10)", 1, 10, 6)
        include_revision = st.checkbox("Include revision in plan", True)
        include_tips = st.checkbox("Include study tips", True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='section'>", unsafe_allow_html=True)
        st.markdown("<div style='font-weight:700;color:#0b66ff;margin-bottom:6px'>Model & Options</div>", unsafe_allow_html=True)
        model_choice = st.selectbox("OpenAI Model", ["gpt-4o-mini","gpt-4o"])
        temp = st.slider("Temperature", 0.0, 1.0, 0.25)
        typing = st.checkbox("Typing animation (preview)", True)
        if st.button("Clear saved plans"):
            st.session_state["plans"] = []
            st.session_state["last_plan_html"] = None
            st.session_state["last_plan_raw"] = None
            st.success("Saved plans cleared.")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='section'>", unsafe_allow_html=True)
        st.markdown("<h2 style='color:#0b66ff;margin-bottom:6px'>AI Generated Study Plan</h2>", unsafe_allow_html=True)

        if st.button("Generate Plan"):
            subs = [s.strip() for s in subjects_input.split(",") if s.strip()]
            if not student_name:
                display_name = "Student"
            else:
                display_name = student_name.strip()

            # Prompt - keep concise and structured
            prompt = f"""Generate a clear, professional weekly study plan for a student.

Name: {display_name}
Subjects: {subs}
Weekly hours: {weekly_hours}
Deadline: {exam_date}
Intensity: {intensity}
Include revision: {include_revision}
Include tips: {include_tips}

Output 3 sections:
1) Weekly Overview (as a markdown table with columns: Day | Subject | Study Hours | Focus Area | Revision Hours)
2) Daily Breakdown with time blocks and tasks (clear bullet points)
3) Short Study Tips (3-6 items)
Keep language concise and professional.
"""

            client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", None))
            try:
                with st.spinner("Generating study plan..."):
                    res = client.chat.completions.create(
                        model=model_choice,
                        messages=[{"role":"system","content":"You generate clear, actionable study plans."},
                                  {"role":"user","content":prompt}],
                        temperature=temp
                    )
                raw = sanitize_text(res.choices[0].message.content)
            except Exception as e:
                st.error(f"OpenAI request failed: {e}")
                raw = ""

            # Parse into parts and convert to HTML
            weekly_raw, daily_raw, tips_raw = pretty_split_plan(raw)
            weekly_html = convert_markdown_table_to_html(weekly_raw)
            daily_html = convert_markdown_table_to_html(daily_raw)
            tips_html = convert_markdown_table_to_html(tips_raw)

            final_html = render_plan_card(display_name, weekly_html, daily_html, tips_html)

            # Save
            st.session_state["plans"].insert(0, {"name": display_name, "raw": raw, "html": final_html, "time": str(datetime.datetime.now())})
            st.session_state["last_plan_html"] = final_html
            st.session_state["last_plan_raw"] = raw

            # show with typing effect if requested
            if typing:
                ph = st.empty()
                out = ""
                for ch in final_html:
                    out += ch
                    ph.markdown(out, unsafe_allow_html=True)
                    time.sleep(0.001)
            else:
                st.markdown(final_html, unsafe_allow_html=True)

            # downloads
            if REPORTLAB and raw:
                pdf_buf = export_pdf(raw, title=f"{display_name} — Study Plan")
                st.download_button("📥 Download PDF", pdf_buf, file_name="study_plan.pdf")
            if raw:
                st.download_button("📥 Download TXT", raw, file_name="study_plan.txt")

        elif st.session_state["last_plan_html"]:
            st.markdown(st.session_state["last_plan_html"], unsafe_allow_html=True)
        else:
            st.info("Click 'Generate Plan' to create a study plan.")

        st.markdown("</div>", unsafe_allow_html=True)

# ---------------- Dashboard ----------------
# ---------------- Dashboard ----------------
elif page == "Dashboard":
    st.markdown("<div class='section'>", unsafe_allow_html=True)
    st.markdown("<h2 class='stitle'>📊 Dashboard • Progress</h2>", unsafe_allow_html=True)

    raw = st.session_state.get("last_plan_raw", "")

    if not raw:
        st.info("Generate a study plan first to populate the dashboard.")
        st.markdown("</div>", unsafe_allow_html=True)
       

    # ---------------- SMART TABLE PARSER ----------------
    subjects = {}

    for line in raw.splitlines():

        # Must contain markdown table pipes
        if "|" not in line:
            continue

        # Split the row
        parts = [p.strip() for p in line.split("|") if p.strip()]

        # We need at least 3 columns for Subject + Hours
        if len(parts) < 3:
            continue

        col1 = parts[0].lower()  # Possibilities: Day, Monday …
        col2 = parts[1]          # Subject
        col3 = parts[2]          # Study hours if numeric

        # Skip header row (non-numeric hrs column)
        if not col3.replace(".", "", 1).isdigit():
            continue

        # Extract subject + hours
        subject = col2
        hours = float(col3)

        subjects[subject] = subjects.get(subject, 0) + hours

    # ---------------- Fallback ----------------
    if not subjects:
        st.warning("Unable to detect study hours from the weekly overview table.")
        subjects = {"Math": 6, "DBMS": 6, "AI": 6}

    # ---------------- BUILD CHART ----------------
    df = pd.DataFrame({"Subject": list(subjects.keys()), "Hours": list(subjects.values())})

    fig = px.bar(
        df, x="Subject", y="Hours", text="Hours",
        title="Planned Hours by Subject"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Track completed hours")
    completed = {}

    for s in df["Subject"]:
        completed[s] = st.number_input(
            f"Completed hours — {s}",
            min_value=0.0,
            max_value=float(df[df["Subject"] == s]["Hours"].iloc[0]),
            value=float(st.session_state["progress"].get(s, 0.0)),
            step=0.5
        )
        st.session_state["progress"][s] = completed[s]

    total_planned = df["Hours"].sum()
    total_done = sum(completed.values())
    pct = min(1.0, total_done / (total_planned if total_planned else 1))

    st.progress(pct)
    st.markdown(f"Completed: {total_done:.1f} / {total_planned} hours — {pct*100:.1f}%")

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- Chatbot ----------------
elif page == "Chatbot":
    st.markdown("<div class='section'>", unsafe_allow_html=True)
    st.markdown("<h2 style='color:#0b66ff'>🤖 Study Assistant</h2>", unsafe_allow_html=True)

    mode = st.selectbox("Mode", ["Study Mode","Subject Mode","Motivation Mode"])
    subj = None
    if mode == "Subject Mode":
        subj = st.text_input("Subject (e.g., Math)", "Math")

    col1, col2 = st.columns([4,1])
    with col1:
        user_msg = st.text_input("Your message", "")
    with col2:
        send = st.button("Send")

    if send and user_msg.strip():
        if mode == "Study Mode":
            system = "You are a study expert. Provide structured study guidance and short examples."
        elif mode == "Motivation Mode":
            system = "You are a motivational coach. Give short energetic encouragement and quick study tips."
        else:
            system = f"You are an expert tutor in {subj}."

        client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", None))
        try:
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":system},{"role":"user","content":user_msg}],
                temperature=0.25
            )
            ai_msg = sanitize_text(res.choices[0].message.content)
        except Exception as e:
            ai_msg = f"Assistant error: {e}"

        st.session_state["chat"].append(("you", user_msg))
        st.session_state["chat"].append(("ai", ai_msg))
        st.rerun()


    # show chat
    for role, txt in st.session_state["chat"][-40:]:
        if role == "you":
            st.markdown(f"<div class='chat-user'>You: {txt}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='chat-ai'>AI: {txt}</div>", unsafe_allow_html=True)

    if st.button("Clear Chat"):
        st.session_state["chat"] = []
        st.rerun()


    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- Calendar ----------------
elif page == "Calendar":
    st.markdown("<div class='section'>", unsafe_allow_html=True)
    st.markdown("<h2 style='color:#0b66ff'>📅 Smart Timetable</h2>", unsafe_allow_html=True)

    subjects_input = st.text_input("Subjects for timetable", "Math, DBMS, AI", key="calendar_subjects")
    weekly_hours = st.number_input("Weekly hours", 1, 168, 20, key="calendar_hours")
    deadline = st.date_input("Deadline", datetime.date.today(), key="calendar_deadline")
    intensity = st.slider("Priority (1-10)", 1, 10, 5, key="calendar_intensity")

    if st.button("Generate Timetable"):
        subs = [s.strip() for s in subjects_input.split(",") if s.strip()]
        df, pivot, subj_hours, summary = generate_smart_timetable(subs, weekly_hours, deadline, intensity, st.session_state["progress"])
        st.session_state["timetable"] = df
        st.success("Timetable generated.")

    if st.session_state["timetable"] is not None:
        st.dataframe(st.session_state["timetable"])
        pivot = st.session_state["timetable"].pivot(index="Slot", columns="Day", values="Subject")
        st.subheader("Calendar View")
        st.table(pivot)
        csv = st.session_state["timetable"].to_csv(index=False)
        st.download_button("Export CSV", csv, "timetable.csv")
    else:
        st.info("Generate a timetable to view it.")

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- History ----------------
elif page == "History":
    st.markdown("<div class='section'>", unsafe_allow_html=True)
    st.markdown("<h2 style='color:#0b66ff'>📜 Plan History</h2>", unsafe_allow_html=True)

    if not st.session_state["plans"]:
        st.info("No saved plans yet.")
    else:
        for i, p in enumerate(st.session_state["plans"]):
            with st.expander(f"Plan #{i+1} — {p.get('name','Student')} — {p.get('time','')}"):
                st.markdown(p.get("html") or convert_markdown_table_to_html(p.get("raw","")), unsafe_allow_html=True)
                st.download_button(f"Download Plan #{i+1} (TXT)", p.get("raw",""), f"plan_{i+1}.txt")

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- About ----------------
else:
    st.markdown("<div class='section'>", unsafe_allow_html=True)
    st.markdown("<h2 style='color:#0b66ff'>ℹ About — AI Study Planner Pro</h2>", unsafe_allow_html=True)
    st.write("""
*AI Study Planner Pro — Premium Blue Dashboard*

A professional, production-friendly Streamlit app that:
- Generates AI-powered weekly & daily study plans
- Produces smart timetables and progress dashboards
- Offers an AI chat assistant for quick help & motivation
- Supports export to PDF (optional) and TXT, and timetable CSV
- Polished UI, responsive layout, and saveable plan history

> To use the OpenAI features: add your API key to Streamlit secrets as OPENAI_API_KEY or configure environment secrets.
""")
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- Footer ----------------
st.markdown("<div class='footer'>Made with ❤️ using Streamlit & OpenAI — Premium Blue Edition</div>", unsafe_allow_html=True)