"""Light scientific workspace UI for PROTACXtend."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import sqlite3
import sys
import textwrap
import uuid
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from protacxtend.backend.main import run_workflow_from_request, summarize_state
from protacxtend.backend.schemas import model_to_dict
from protacxtend.tools.protac_toolbox import RDKIT_AVAILABLE
from protacxtend.tools.report_generator import generate_candidate_table
from protacxtend.tools.tool_registry import ToolRegistry


APP_NAME = "PROTACXtend"
CHAT_DB_PATH = PROJECT_ROOT / "protacxtend" / "memory" / "chat_history.sqlite3"
HERO_BG_PATH = PROJECT_ROOT / "protacxtend" / "app" / "assets" / "protac_degradation_hero_bg.png"
CHALLENGE_INFOGRAPHIC_PATH = PROJECT_ROOT / "protacxtend" / "app" / "assets" / "protac_challenge_infographic.png"

EXAMPLE_QUERIES = [
    "Design CRBN-based PROTAC candidates for a kinase target with low DC50 and high Dmax priority.",
    "Rank these imported PROTAC SMILES by degradation plausibility and ADME/Tox risk.",
    "Explain why candidate 4 was rejected.",
    "Compare CRBN versus VHL strategy for this target.",
    "Generate a report for the current local session.",
]
EXAMPLE_CARDS = [
    ("Kinase · CRBN · endpoint priority", "Generate candidates with low DC50, high Dmax, and explicit ranking basis."),
    ("Imported PROTAC SMILES", "Normalize, annotate, and rank imported molecules against developability signals."),
    ("Rejected candidate review", "Inspect rejection reasons and tool availability for a saved run."),
]

AGENT_COUNT = len(list((PROJECT_ROOT / "protacxtend" / "agents").glob("*_agent.py")))

TECHNICAL_MODULES = [
    "Target tractability",
    "Warhead binder evidence",
    "E3 ligase context",
    "Linker geometry",
    "Ternary-complex feasibility",
    "DC50 / Dmax ranking",
    "Hook-effect risk",
    "ADME/Tox filters",
    "Synthetic feasibility",
    "Workflow provenance",
]

WORKFLOW_STEPS = [
    (
        "Target and disease-context definition",
        "Define the therapeutic hypothesis using target identity, disease relevance, expression context, dependency evidence, tractability, available structures, known binders, and degradation rationale.",
        ["Disease relevance", "Target expression", "Cellular localization", "Tractability", "Structure availability", "Known binder evidence"],
    ),
    (
        "Warhead and binder selection",
        "Prioritize target binders using affinity evidence, selectivity, exit-vector availability, SAR confidence, structure support, and compatibility with linker attachment.",
        ["Affinity or activity evidence", "Selectivity", "SAR confidence", "Exit-vector quality", "Crystal or docking pose support", "Linker-attachment compatibility"],
    ),
    (
        "E3 ligase strategy",
        "Select CRBN, VHL, IAP, MDM2, DCAF, or other E3 contexts using tissue expression, subcellular co-localization, ligand chemistry, clinical precedent, and toxicity risk.",
        ["E3 expression in disease tissue", "Target-E3 co-localization", "Ligand chemistry", "Clinical precedent", "Resistance risk", "Toxicity risk"],
    ),
    (
        "Linker and geometry optimization",
        "Evaluate linker length, rigidity, polarity, rotatable bonds, exit-vector orientation, and the geometric feasibility of productive target-PROTAC-E3 ternary complex formation.",
        ["Linker length", "PEG / alkyl / aromatic linker class", "Rotatable bonds", "Polarity", "Exit-vector orientation", "Ternary-complex geometry"],
    ),
    (
        "Degradation-aware candidate ranking",
        "Rank candidates using DC50, Dmax, degradation window, hook-effect risk, cooperativity, cell permeability, target engagement confidence, and E3-dependent plausibility.",
        ["Lower DC50", "Higher Dmax", "Degradation window", "Hook-effect risk", "Cooperativity", "Target engagement", "E3-dependent plausibility"],
    ),
    (
        "ADME/Tox and developability filtering",
        "Filter candidates using PROTAC-aware molecular property ranges, solubility, permeability, hERG/CYP risk, hepatotoxicity alerts, PAINS/reactive group checks, metabolic liability, and synthetic accessibility.",
        ["Molecular weight awareness", "cLogP / TPSA balance", "Solubility", "Permeability", "hERG / CYP alerts", "Hepatotoxicity risk", "Synthetic accessibility"],
    ),
    (
        "Reproducible workflow trace",
        "Store design briefs, generated candidates, imported libraries, tool calls, scoring outputs, rejection reasons, ranked tables, and reports in a local SQLite-backed research session.",
        ["Input design brief", "Candidate table", "Tool-call history", "Rejection reasons", "Ranking rationale", "Exportable reports", "Local SQLite history"],
    ),
]

CHAT_SUPPORT = [
    "Natural-language PROTAC design briefs",
    "Target + E3 + linker constraint parsing",
    "Candidate generation or candidate import",
    "SMILES validation and normalization",
    "Warhead/E3/linker annotation",
    "DC50 and Dmax-aware ranking",
    "Ternary-complex feasibility checks",
    "ADME/Tox and developability filtering",
    "Synthetic feasibility scoring",
    "Rejection-reason explanation",
    "Ranked candidate table retrieval",
    "Workflow trace inspection",
    "Report generation",
    "Session history retrieval from local SQLite",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _html(container: Any, html_block: str) -> None:
    """Render intended HTML after removing Python indentation.

    Indented triple-quoted HTML can be interpreted by Markdown as a code block,
    which exposes raw tags in the UI. Always route decorative HTML through here.
    """

    dedented = textwrap.dedent(html_block).strip()
    normalized = "\n".join(line.lstrip() for line in dedented.splitlines())
    container.markdown(normalized, unsafe_allow_html=True)


def _asset_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{payload}"


def _db() -> sqlite3.Connection:
    CHAT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CHAT_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db() -> None:
    with _db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS run_details (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                request TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                rows_json TEXT NOT NULL,
                state_json TEXT NOT NULL,
                report TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
            );
            """
        )


def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 180_000)
    return digest.hex()


def _create_user(username: str, password: str) -> tuple[bool, str]:
    username = username.strip().lower()
    if len(username) < 3:
        return False, "Use a username with at least 3 characters."
    if len(password) < 6:
        return False, "Use a password with at least 6 characters."
    salt = uuid.uuid4().hex
    try:
        with _db() as conn:
            conn.execute(
                "INSERT INTO users (id, username, salt, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, username, salt, _hash_password(password, salt), _now()),
            )
        return True, "Account created. Sign in to continue."
    except sqlite3.IntegrityError:
        return False, "That username already exists."


def _authenticate(username: str, password: str) -> dict[str, str] | None:
    with _db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
    if not row:
        return None
    candidate = _hash_password(password, row["salt"])
    if hmac.compare_digest(candidate, row["password_hash"]):
        return {"id": row["id"], "username": row["username"]}
    return None


def _new_chat(user_id: str, title: str = "New PROTAC brief") -> str:
    chat_id = uuid.uuid4().hex
    with _db() as conn:
        conn.execute(
            "INSERT INTO chats (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (chat_id, user_id, title, _now(), _now()),
        )
    return chat_id


def _list_chats(user_id: str) -> list[sqlite3.Row]:
    with _db() as conn:
        return conn.execute(
            "SELECT * FROM chats WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()


def _messages(chat_id: str) -> list[dict[str, str]]:
    with _db() as conn:
        rows = conn.execute("SELECT role, content FROM messages WHERE chat_id = ? ORDER BY created_at ASC", (chat_id,)).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def _current_messages(chat_id: str) -> list[dict[str, str]]:
    if st_messages := st_session_messages(chat_id):
        return st_messages
    return []


def st_session_messages(chat_id: str) -> list[dict[str, str]]:
    # Streamlit is imported inside main, so access session state through the module at call time.
    import streamlit as st

    return st.session_state.setdefault("visible_chat_messages", {}).setdefault(chat_id, [])


def _latest_run(chat_id: str) -> dict[str, Any] | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM run_details WHERE chat_id = ? ORDER BY created_at DESC LIMIT 1",
            (chat_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "summary": json.loads(row["summary_json"]),
        "rows": json.loads(row["rows_json"]),
        "state": json.loads(row["state_json"]),
        "report": row["report"],
        "request": row["request"],
        "created_at": row["created_at"],
    }


def _save_message(chat_id: str, role: str, content: str) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO messages (id, chat_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, chat_id, role, content, _now()),
        )
        conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (_now(), chat_id))
    try:
        import streamlit as st

        visible = st.session_state.setdefault("visible_chat_messages", {}).setdefault(chat_id, [])
        visible.append({"role": role, "content": content})
    except Exception:
        pass


def _save_run(chat_id: str, request: str, state: Any, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    title = request.strip().replace("\n", " ")
    title = title[:58] + ("..." if len(title) > 58 else "")
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO run_details (id, chat_id, request, summary_json, rows_json, state_json, report, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                chat_id,
                request,
                json.dumps(summary, ensure_ascii=True),
                json.dumps(rows, ensure_ascii=True),
                json.dumps(model_to_dict(state), ensure_ascii=True),
                state.report,
                _now(),
            ),
        )
        conn.execute("UPDATE chats SET title = ?, updated_at = ? WHERE id = ?", (title or "PROTAC design run", _now(), chat_id))


def _inject_css(st: Any, is_authenticated: bool = False) -> None:
    hero_bg = _asset_data_uri(HERO_BG_PATH)
    app_background = (
        "linear-gradient(180deg, rgba(244,241,235,0.18) 0%, rgba(244,241,235,0.80) 52%, rgba(238,233,223,0.98) 100%), "
        f"url('{hero_bg}') center top / cover no-repeat, "
        "var(--background)"
        if hero_bg and not is_authenticated
        else (
            "linear-gradient(180deg, rgba(244,241,235,0.76) 0%, rgba(238,233,223,0.94) 62%, rgba(244,241,235,0.98) 100%), "
            f"url('{hero_bg}') center top / cover no-repeat, "
            "var(--background)"
            if hero_bg
            else "radial-gradient(circle at 12% 0%, rgba(245, 147, 0, 0.13), transparent 28%), radial-gradient(circle at 88% 2%, rgba(224, 127, 41, 0.10), transparent 31%), linear-gradient(180deg, var(--background) 0%, var(--muted) 100%)"
        )
    )
    css = """
        <style>
        :root {
            --primary: #F59300;
            --primary-foreground: #FFFFFF;
            --secondary: #E07F29;
            --secondary-foreground: #FFFFFF;
            --accent: #F59300;
            --muted: #EEE9DF;
            --muted-foreground: #666666;
            --background: #F4F1EB;
            --card: #FFFFFF;
            --card-foreground: #212121;
            --border: #E3DED4;
            --radius-lg: 22px;
            --radius-md: 16px;
            --radius-sm: 12px;
            --shadow-soft: 0 20px 48px rgba(33, 33, 33, 0.08);
            --shadow-tight: 0 10px 24px rgba(33, 33, 33, 0.06);
        }
        .stApp {
            background: __APP_BACKGROUND__;
            color: var(--card-foreground);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        header[data-testid="stHeader"] {
            background: rgba(244, 241, 235, 0.82);
            border-bottom: 1px solid var(--border);
            backdrop-filter: blur(18px);
        }
        #MainMenu, footer, div[data-testid="stToolbar"], div[data-testid="stDecoration"], div[data-testid="stStatusWidget"] { display: none !important; }
        header[data-testid="stHeader"] { height: 0; min-height: 0; visibility: hidden; }
        .block-container {
            max-width: 1480px;
            padding: 1.15rem 1.6rem 2.5rem;
        }
        .element-container:has(a.anchor-link) { display: none !important; }
        a.anchor-link { display: none !important; }
        section[data-testid="stSidebar"] {
            background: rgba(255, 255, 255, 0.92);
            border-right: 1px solid var(--border);
            box-shadow: 10px 0 30px rgba(33, 33, 33, 0.04);
        }
        section[data-testid="stSidebar"] * { color: var(--card-foreground); }
        section[data-testid="stSidebar"] .stButton button {
            justify-content: flex-start;
            min-height: 42px;
            white-space: normal;
        }
        .pa-login {
            max-width: 1240px;
            margin: 2.2vh auto 0;
            display: grid;
            grid-template-columns: minmax(0, 1.18fr) 410px;
            gap: 24px;
            align-items: stretch;
        }
        .pa-pathway-hero {
            border: 1px solid var(--border);
            border-radius: 26px;
            background: var(--card);
            box-shadow: 0 28px 70px rgba(33, 33, 33, 0.10);
            overflow: hidden;
            position: relative;
            margin: 6px auto 24px;
            max-width: 1240px;
        }
        .pa-pathway-hero img,
        .pa-infographic-panel img {
            width: 100%;
            display: block;
            height: auto;
        }
        .pa-pathway-caption {
            max-width: 1240px;
            margin: -10px auto 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 14px;
            color: var(--card-foreground);
            font-size: 1.08rem;
            font-weight: 760;
        }
        .pa-pathway-caption::before,
        .pa-pathway-caption::after {
            content: "";
            width: min(160px, 18vw);
            height: 1px;
            background: var(--border);
        }
        .pa-infographic-panel {
            max-width: 1240px;
            margin: 0 auto 24px;
            border: 1px solid var(--border);
            border-radius: 26px;
            background: var(--card);
            box-shadow: var(--shadow-soft);
            overflow: hidden;
        }
        .pa-pathway-title {
            color: var(--card-foreground);
            font-size: clamp(1.85rem, 3vw, 2.65rem);
            line-height: 1.04;
            font-weight: 880;
            margin: 10px 0 12px;
        }
        .pa-pathway-sub {
            color: var(--muted-foreground);
            font-size: 0.95rem;
            line-height: 1.55;
        }
        .pa-brand-system {
            margin-top: 18px;
            display: grid;
            grid-template-columns: minmax(210px, 0.72fr) minmax(220px, 1fr);
            gap: 14px;
        }
        .pa-mini-card {
            border: 1px solid var(--border);
            background: rgba(255,255,255,0.84);
            border-radius: var(--radius-md);
            padding: 15px;
            box-shadow: var(--shadow-tight);
        }
        .pa-science-icon-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-top: 12px;
        }
        .pa-science-icon {
            display: grid;
            place-items: center;
            gap: 7px;
            color: var(--muted-foreground);
            font-size: 0.78rem;
            text-align: center;
        }
        .pa-science-icon svg {
            width: 46px;
            height: 38px;
            display: block;
        }
        .pa-pill-chip-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
        }
        .pa-pill-chip {
            display: inline-flex;
            align-items: center;
            gap: 7px;
            border: 1px solid var(--border);
            background: var(--card);
            border-radius: 999px;
            padding: 9px 12px;
            color: var(--card-foreground);
            font-size: 0.84rem;
            box-shadow: 0 6px 16px rgba(33,33,33,0.04);
        }
        .pa-pill-dot {
            width: 9px;
            height: 9px;
            border-radius: 999px;
            background: var(--primary);
            display: inline-block;
        }
        .pa-orbital-strip {
            height: 78px;
            margin-top: 12px;
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            background:
                radial-gradient(circle at 20% 44%, var(--primary) 0 4px, transparent 5px),
                radial-gradient(circle at 72% 30%, var(--secondary) 0 4px, transparent 5px),
                radial-gradient(circle at 54% 70%, var(--border) 0 6px, transparent 7px),
                linear-gradient(135deg, rgba(255,255,255,0.80), rgba(238,233,223,0.54));
            position: relative;
            overflow: hidden;
        }
        .pa-orbital-strip::before,
        .pa-orbital-strip::after {
            content: "";
            position: absolute;
            width: 150px;
            height: 52px;
            border: 2px dashed var(--border);
            border-radius: 50%;
            transform: rotate(-18deg);
            left: 20px;
            top: 12px;
        }
        .pa-orbital-strip::after {
            width: 118px;
            height: 42px;
            left: auto;
            right: 20px;
            transform: rotate(18deg);
        }
        .pa-panel,
        .pa-topbar,
        .pa-message,
        .pa-results,
        .pa-stat,
        .pa-warning,
        .pa-feature-card,
        .pa-example-card,
        .pa-science-card,
        .pa-starter {
            border: 1px solid var(--border);
            background: rgba(255, 255, 255, 0.94);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-soft);
            backdrop-filter: blur(14px);
        }
        .pa-panel { padding: 32px; }
        .pa-hero-panel {
            background:
                linear-gradient(135deg, rgba(255,255,255,0.98), rgba(238,233,223,0.70)),
                linear-gradient(90deg, rgba(245,147,0,0.08), rgba(224,127,41,0.05));
        }
        .pa-logo-row { display: flex; align-items: center; gap: 14px; margin-bottom: 22px; }
        .pa-brand-mark {
            width: 62px;
            height: 62px;
            border: 1px solid var(--border);
            border-radius: 18px;
            background: var(--card);
            box-shadow: var(--shadow-tight);
            display: flex;
            align-items: center;
            justify-content: center;
            flex: 0 0 auto;
        }
        .pa-brand-mark svg { width: 52px; height: 52px; display: block; }
        .pa-brand-lockup {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .pa-brand-word {
            font-size: 1.02rem;
            font-weight: 850;
            letter-spacing: 0;
            color: var(--card-foreground);
        }
        .pa-brand-sub {
            color: var(--muted-foreground);
            font-size: 0.82rem;
        }
        .pa-kicker {
            color: var(--secondary);
            font-size: 0.75rem;
            font-weight: 800;
            letter-spacing: 0.04em;
        }
        .pa-title {
            font-size: clamp(2.05rem, 3.8vw, 3.15rem);
            line-height: 1.08;
            letter-spacing: 0;
            margin: 12px 0 14px;
            color: var(--card-foreground);
            max-width: 780px;
            font-weight: 850;
        }
        .pa-copy { color: var(--muted-foreground); font-size: 0.98rem; line-height: 1.65; max-width: 780px; }
        .pa-chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px; }
        .pa-chip {
            border: 1px solid var(--border);
            background: var(--card);
            color: var(--secondary);
            border-radius: 999px;
            padding: 7px 12px;
            font-size: 0.78rem;
            font-weight: 760;
            box-shadow: 0 5px 14px rgba(33, 33, 33, 0.04);
        }
        .pa-feature-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(190px, 1fr));
            gap: 12px;
            margin-top: 22px;
        }
        .pa-feature-card {
            padding: 17px;
            box-shadow: none;
            background: rgba(255,255,255,0.82);
            border-radius: var(--radius-md);
        }
        .pa-feature-card h3 {
            margin: 0 0 7px;
            color: var(--card-foreground);
            font-size: 1rem;
        }
        .pa-feature-card p {
            margin: 0;
            color: var(--muted-foreground);
            font-size: 0.86rem;
            line-height: 1.45;
        }
        .pa-science-card {
            padding: 20px;
            margin-top: 18px;
            background: linear-gradient(135deg, var(--card), rgba(238,233,223,0.66));
            border-radius: var(--radius-md);
        }
        .pa-science-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 14px;
        }
        .pa-science-label {
            color: var(--muted-foreground);
            font-size: 0.8rem;
        }
        .pa-schematic {
            display: grid;
            grid-template-columns: 1fr 96px 1fr;
            gap: 12px;
            align-items: center;
        }
        .pa-node {
            min-height: 82px;
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 13px;
            background: var(--card);
            position: relative;
            overflow: hidden;
        }
        .pa-node::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 5px;
            background: var(--primary);
        }
        .pa-node strong { display:block; color: var(--card-foreground); font-size: 0.92rem; }
        .pa-node span { color: var(--muted-foreground); font-size: 0.78rem; }
        .pa-linker {
            height: 8px;
            border-radius: 999px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            position: relative;
        }
        .pa-linker::before,
        .pa-linker::after {
            content: "";
            position: absolute;
            top: -6px;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: var(--card);
            border: 4px solid var(--primary);
        }
        .pa-linker::before { left: -2px; }
        .pa-linker::after { right: -2px; border-color: var(--secondary); }
        .pa-login-note {
            color: var(--muted-foreground);
            font-size: 0.82rem;
            line-height: 1.45;
            margin-top: 12px;
            padding: 10px 12px;
            border: 1px solid var(--border);
            background: var(--muted);
            border-radius: var(--radius-sm);
        }
        .pa-topbar {
            padding: 22px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
            margin-bottom: 16px;
        }
        .pa-topbar h1 { margin: 0; font-size: 2rem; color: var(--card-foreground); }
        .pa-subtle { color: var(--muted-foreground); font-size: 0.88rem; }
        .pa-status {
            border: 1px solid var(--border);
            background: var(--muted);
            color: var(--secondary);
            border-radius: 999px;
            padding: 8px 12px;
            white-space: nowrap;
            font-size: 0.78rem;
            font-weight: 750;
        }
        .pa-quick-row {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: 12px;
        }
        .pa-quick-chip {
            color: var(--muted-foreground);
            border: 1px solid var(--border);
            background: var(--card);
            border-radius: 999px;
            padding: 6px 10px;
            font-size: 0.78rem;
        }
        .pa-message {
            padding: 14px 16px;
            margin: 9px 0;
            color: var(--card-foreground);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-tight);
        }
        .pa-message.user {
            background: linear-gradient(135deg, var(--card), var(--muted));
            border-color: var(--border);
        }
        .pa-message.assistant {
            background: var(--card);
        }
        .pa-role {
            display: inline-flex;
            color: var(--secondary);
            background: var(--muted);
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 3px 8px;
            letter-spacing: 0.04em;
            font-size: 0.68rem;
            font-weight: 850;
            margin-bottom: 8px;
        }
        .pa-stat-grid {
            display: grid;
            grid-template-columns: repeat(6, minmax(120px, 1fr));
            gap: 10px;
            margin: 12px 0;
        }
        .pa-stat { padding: 14px; }
        .pa-stat .label {
            color: var(--muted-foreground);
            font-size: 0.72rem;
            letter-spacing: 0.08em;
        }
        .pa-stat .value {
            color: var(--card-foreground);
            font-size: 1.35rem;
            font-weight: 850;
            margin-top: 5px;
        }
        .pa-results { padding: 16px; margin-top: 14px; }
        .pa-warning {
            border-color: var(--border);
            background: var(--muted);
            color: var(--secondary);
            padding: 10px 12px;
            margin: 8px 0;
        }
        .pa-table-wrap {
            max-height: 460px;
            overflow: auto;
            border: 1px solid var(--border);
            border-radius: 14px;
            background: var(--card);
        }
        .pa-results-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.84rem;
        }
        .pa-results-table th {
            position: sticky;
            top: 0;
            z-index: 1;
            background: var(--muted);
            color: var(--card-foreground);
            padding: 11px 10px;
            border-bottom: 1px solid var(--border);
            text-align: left;
            white-space: nowrap;
        }
        .pa-results-table td {
            color: var(--card-foreground);
            padding: 10px;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }
        .pa-results-table tr:hover td { background: var(--muted); }
        .pa-score-cell { display: flex; align-items: center; gap: 9px; min-width: 155px; }
        .pa-score-track {
            width: 90px;
            height: 7px;
            border-radius: 999px;
            background: var(--muted);
            overflow: hidden;
        }
        .pa-score-fill { height: 100%; background: linear-gradient(90deg, var(--primary), var(--secondary)); }
        .pa-example-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(180px, 1fr));
            gap: 12px;
            margin-bottom: 14px;
        }
        .pa-example-card {
            padding: 15px 15px 13px;
            text-align: left;
            min-height: 112px;
            background: linear-gradient(135deg, var(--card), rgba(238,233,223,0.58));
            border-radius: var(--radius-md);
            transition: transform 120ms ease, box-shadow 120ms ease;
        }
        .pa-example-card:hover {
            transform: translateY(-1px);
            box-shadow: 0 18px 38px rgba(33, 33, 33, 0.08);
        }
        .pa-example-title {
            color: var(--card-foreground);
            font-weight: 780;
            font-size: 0.95rem;
            margin-bottom: 7px;
        }
        .pa-example-body {
            color: var(--muted-foreground);
            font-size: 0.82rem;
            line-height: 1.4;
        }
        .pa-starter {
            padding: 20px;
            margin-top: 14px;
            background: linear-gradient(135deg, var(--card), rgba(238,233,223,0.55));
        }
        .pa-template {
            margin-top: 12px;
            padding: 14px;
            border-radius: 14px;
            border: 1px dashed var(--border);
            background: var(--card);
            color: var(--muted-foreground);
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.86rem;
            line-height: 1.65;
            white-space: pre-wrap;
        }
        .stButton button,
        .stDownloadButton button,
        .stFormSubmitButton button {
            border-radius: 12px !important;
            border: 1px solid var(--border) !important;
            background: var(--card) !important;
            color: var(--card-foreground) !important;
            font-weight: 760 !important;
            box-shadow: var(--shadow-tight);
        }
        .stButton button[kind="primary"],
        .stFormSubmitButton button[kind="primary"] {
            background: linear-gradient(135deg, var(--primary), var(--secondary)) !important;
            color: var(--primary-foreground) !important;
            border: 0 !important;
            box-shadow: 0 14px 28px rgba(245, 147, 0, 0.20);
        }
        .stButton button:hover,
        .stDownloadButton button:hover,
        .stFormSubmitButton button:hover {
            border-color: var(--primary) !important;
            color: var(--secondary) !important;
            transform: translateY(-1px);
        }
        span[data-baseweb="tag"] {
            background: linear-gradient(135deg, var(--primary), var(--secondary)) !important;
            color: #fff !important;
        }
        textarea, input {
            border-radius: 12px !important;
            border-color: var(--border) !important;
            color: var(--card-foreground) !important;
            background: var(--card) !important;
        }
        div[data-testid="stTabs"] button p {
            color: var(--card-foreground);
            font-weight: 750;
        }
        div[data-testid="stChatInput"] {
            background: rgba(244, 241, 235, 0.88);
            border-top: 1px solid var(--border);
            backdrop-filter: blur(14px);
        }
        div[data-testid="stMarkdownContainer"] p {
            color: inherit;
        }
        code {
            background: var(--muted) !important;
            color: var(--card-foreground) !important;
            border-radius: 8px;
        }
        @media (max-width: 1000px) {
            .pa-login { grid-template-columns: 1fr; margin-top: 2vh; }
            .pa-stat-grid { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
            .pa-example-grid,
            .pa-feature-grid { grid-template-columns: 1fr; }
            .pa-topbar { align-items: flex-start; flex-direction: column; }
        }
        .pa-site-header {
            position: sticky;
            top: 0;
            z-index: 50;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
            padding: 12px 0 18px;
            background: linear-gradient(180deg, rgba(244,241,235,0.96), rgba(244,241,235,0.78));
            backdrop-filter: blur(18px);
        }
        .pa-site-header .pa-brand-mark {
            width: 44px;
            height: 44px;
            border-radius: 14px;
        }
        .pa-site-header .pa-brand-mark svg { width: 38px; height: 38px; }
        .pa-login-anchor {
            display: flex;
            justify-content: flex-end;
            align-items: center;
        }
        .pa-landing-shell {
            display: grid;
            gap: 22px;
            padding-bottom: 28px;
        }
        .pa-pathway-hero,
        .pa-infographic-panel {
            max-width: 1240px;
            margin: 8px auto 18px;
            border: 1px solid rgba(33,33,33,0.10);
            border-radius: 24px;
            background: rgba(255,255,255,0.86);
            box-shadow: 0 28px 70px rgba(33,33,33,0.10);
            overflow: hidden;
        }
        .pa-pathway-hero img,
        .pa-infographic-panel img {
            display: block;
            width: 100%;
            height: auto;
        }
        .pa-pathway-caption {
            max-width: 980px;
            margin: 0 auto 22px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 14px;
            color: var(--card-foreground);
            font-size: 1rem;
            font-weight: 820;
            text-align: center;
        }
        .pa-pathway-caption::before,
        .pa-pathway-caption::after {
            content: "";
            width: min(180px, 18vw);
            height: 1px;
            background: var(--border);
        }
        .pa-landing-hero {
            display: grid;
            grid-template-columns: minmax(0, 1fr);
            gap: 30px;
            align-items: center;
            max-width: 1120px;
            margin: 0 auto;
        }
        .pa-hero-copy {
            padding: 18px 0 8px;
            text-align: center;
        }
        .pa-hero-copy .pa-title {
            font-size: clamp(2.7rem, 5vw, 4.8rem);
            line-height: 0.98;
            max-width: 980px;
            margin-left: auto;
            margin-right: auto;
            margin-bottom: 18px;
        }
        .pa-subtitle {
            color: var(--card-foreground);
            font-size: clamp(1.18rem, 2.1vw, 1.8rem);
            line-height: 1.24;
            font-weight: 760;
            max-width: 860px;
            margin-bottom: 18px;
            margin-left: auto;
            margin-right: auto;
        }
        .pa-product-line {
            display: inline-flex;
            align-items: center;
            margin: 22px 0;
            padding: 10px 14px;
            border: 1px solid rgba(245,147,0,0.35);
            border-radius: 999px;
            color: var(--card-foreground);
            background: rgba(255,255,255,0.70);
            font-weight: 860;
            box-shadow: var(--shadow-tight);
        }
        .pa-action-row {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin: 10px 0 22px;
        }
        .pa-module-row {
            display: flex;
            flex-wrap: wrap;
            gap: 9px;
            max-width: 1040px;
            justify-content: center;
            margin: 0 auto;
        }
        .pa-module-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            border: 1px solid rgba(33,33,33,0.10);
            background: rgba(255,255,255,0.76);
            color: var(--card-foreground);
            border-radius: 999px;
            padding: 8px 11px;
            font-size: 0.78rem;
            box-shadow: 0 8px 22px rgba(33,33,33,0.045);
        }
        .pa-module-badge::before {
            content: "";
            width: 7px;
            height: 7px;
            border-radius: 999px;
            background: var(--secondary);
        }
        .pa-degradation-visual {
            min-height: 620px;
            border: 1px solid rgba(33,33,33,0.10);
            border-radius: 28px;
            position: relative;
            overflow: hidden;
            background:
                linear-gradient(180deg, rgba(255,255,255,0.62), rgba(244,241,235,0.76)),
                url('__HERO_BG__') center / cover no-repeat,
                radial-gradient(circle at 70% 18%, rgba(245,147,0,0.24), transparent 24%),
                linear-gradient(145deg, rgba(255,255,255,0.95), rgba(238,233,223,0.84));
            box-shadow: 0 30px 80px rgba(33, 33, 33, 0.12);
        }
        .pa-degradation-visual::after {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(90deg, rgba(255,255,255,0.66), rgba(255,255,255,0.12) 42%, rgba(244,241,235,0.52));
            pointer-events: none;
        }
        .pa-visual-svg {
            position: absolute;
            inset: 22px;
            z-index: 1;
        }
        .pa-score-tags,
        .pa-visual-labels {
            position: absolute;
            z-index: 2;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            left: 22px;
            right: 22px;
        }
        .pa-visual-labels { top: 22px; }
        .pa-score-tags { bottom: 22px; }
        .pa-visual-label,
        .pa-score-tag {
            border: 1px solid rgba(33,33,33,0.12);
            background: rgba(255,255,255,0.82);
            color: var(--card-foreground);
            border-radius: 999px;
            padding: 7px 10px;
            font-size: 0.76rem;
            font-weight: 760;
            box-shadow: 0 10px 24px rgba(33,33,33,0.05);
        }
        .pa-score-tag {
            background: rgba(33,33,33,0.86);
            color: #fff;
            border-color: rgba(33,33,33,0.40);
        }
        .pa-section {
            padding: 34px 0;
        }
        .pa-section h2 {
            margin: 0 0 12px;
            color: var(--card-foreground);
            font-size: clamp(1.9rem, 3vw, 3rem);
            line-height: 1.02;
            letter-spacing: 0;
        }
        .pa-section-intro {
            color: var(--muted-foreground);
            font-size: 1rem;
            line-height: 1.62;
            max-width: 890px;
            margin-bottom: 22px;
        }
        .pa-workflow-list {
            display: grid;
            gap: 16px;
            position: relative;
        }
        .pa-workflow-card {
            display: grid;
            grid-template-columns: 76px minmax(0, 1fr);
            gap: 18px;
            border: 1px solid rgba(33,33,33,0.10);
            border-radius: 20px;
            background: rgba(255,255,255,0.82);
            box-shadow: var(--shadow-tight);
            padding: 20px;
        }
        .pa-step-index {
            width: 52px;
            height: 52px;
            border-radius: 18px;
            display: grid;
            place-items: center;
            color: #fff;
            font-weight: 880;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            box-shadow: 0 16px 30px rgba(245,147,0,0.20);
        }
        .pa-workflow-card h3,
        .pa-premium-card h3 {
            margin: 0 0 8px;
            color: var(--card-foreground);
            font-size: 1.16rem;
        }
        .pa-workflow-card p,
        .pa-premium-card p {
            margin: 0;
            color: var(--muted-foreground);
            line-height: 1.55;
            font-size: 0.93rem;
        }
        .pa-signal-row {
            display: flex;
            flex-wrap: wrap;
            gap: 7px;
            margin-top: 12px;
        }
        .pa-signal {
            border: 1px solid rgba(224,127,41,0.20);
            background: rgba(245,147,0,0.08);
            color: var(--card-foreground);
            border-radius: 999px;
            padding: 6px 9px;
            font-size: 0.74rem;
        }
        .pa-card-grid-2,
        .pa-card-grid-4 {
            display: grid;
            gap: 16px;
        }
        .pa-card-grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .pa-card-grid-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
        .pa-premium-card {
            border: 1px solid rgba(33,33,33,0.10);
            border-radius: 20px;
            background: linear-gradient(145deg, rgba(255,255,255,0.88), rgba(238,233,223,0.58));
            box-shadow: var(--shadow-tight);
            padding: 20px;
            min-height: 172px;
        }
        .pa-chat-capabilities {
            columns: 2;
            column-gap: 26px;
            padding: 22px;
            border: 1px solid rgba(33,33,33,0.10);
            border-radius: 20px;
            background: rgba(255,255,255,0.76);
            box-shadow: var(--shadow-tight);
        }
        .pa-chat-capabilities div {
            break-inside: avoid;
            margin: 0 0 9px;
            color: var(--card-foreground);
            font-size: 0.92rem;
        }
        .pa-footer-line {
            border-top: 1px solid var(--border);
            color: var(--muted-foreground);
            padding: 26px 0 8px;
            text-align: center;
        }
        .pa-login-panel {
            max-width: 520px;
            margin-left: auto;
            border: 1px solid rgba(33,33,33,0.10);
            border-radius: 22px;
            padding: 22px;
            background: rgba(255,255,255,0.88);
            box-shadow: var(--shadow-soft);
        }
        .pa-workspace-grid {
            display: grid;
            grid-template-columns: minmax(240px, 0.75fr) minmax(520px, 1.6fr) minmax(260px, 0.78fr);
            gap: 16px;
            align-items: start;
        }
        .pa-workspace-panel,
        .pa-constraint-panel {
            border: 1px solid var(--border);
            border-radius: 20px;
            background: rgba(255,255,255,0.84);
            box-shadow: var(--shadow-tight);
            padding: 18px;
        }
        .pa-mode-shell {
            max-width: 1480px;
            margin: 0 auto;
        }
        .pa-chat-full {
            display: grid;
            grid-template-columns: minmax(220px, 0.58fr) minmax(620px, 1.5fr) minmax(260px, 0.7fr);
            gap: 16px;
            align-items: start;
        }
        .pa-chat-shell {
            max-width: 1120px;
            margin: 18px auto 0;
            border: 1px solid var(--border);
            border-radius: 24px;
            background: rgba(255,255,255,0.86);
            box-shadow: var(--shadow-soft);
            padding: 22px;
        }
        .pa-chat-empty {
            min-height: 420px;
            display: grid;
            place-items: center;
            text-align: center;
            color: var(--muted-foreground);
        }
        .pa-login-inline {
            max-width: 540px;
            margin: 10px auto 24px;
        }
        .pa-side-nav-title {
            color: var(--card-foreground);
            font-weight: 820;
            margin: 14px 0 8px;
        }
        .pa-side-nav-item {
            display: flex;
            justify-content: space-between;
            gap: 10px;
            border: 1px solid var(--border);
            border-radius: 13px;
            background: rgba(255,255,255,0.70);
            padding: 10px 11px;
            color: var(--card-foreground);
            margin-bottom: 8px;
            font-size: 0.86rem;
        }
        .pa-tool-call {
            border: 1px solid rgba(224,127,41,0.24);
            background: rgba(245,147,0,0.07);
            border-radius: 14px;
            padding: 12px;
            margin: 10px 0;
            color: var(--card-foreground);
        }
        .pa-constraint-kv {
            display: grid;
            grid-template-columns: 1fr;
            gap: 9px;
        }
        .pa-constraint-kv div {
            border-bottom: 1px solid var(--border);
            padding-bottom: 9px;
            color: var(--muted-foreground);
            font-size: 0.84rem;
            overflow-wrap: anywhere;
        }
        .pa-constraint-kv strong {
            display: block;
            color: var(--card-foreground);
            font-size: 0.9rem;
            margin-bottom: 3px;
        }
        @media (max-width: 1180px) {
            .pa-landing-hero,
            .pa-workspace-grid,
            .pa-card-grid-4 { grid-template-columns: 1fr; }
            .pa-degradation-visual { min-height: 520px; }
        }
        @media (max-width: 780px) {
            .block-container { padding: 0.9rem 1rem 2rem; }
            .pa-card-grid-2 { grid-template-columns: 1fr; }
            .pa-chat-capabilities { columns: 1; }
            .pa-workflow-card { grid-template-columns: 1fr; }
            .pa-hero-copy .pa-title { font-size: 3rem; }
            .pa-degradation-visual { min-height: 430px; }
        }
        </style>
        f"""
    _html(st, css.replace("__APP_BACKGROUND__", app_background).replace("__HERO_BG__", hero_bg))


def _brand_mark() -> str:
    return textwrap.dedent("""
    <div class="pa-brand-mark" aria-label="PROTACXtend brand mark">
        <svg viewBox="0 0 96 96" role="img">
            <defs>
                <linearGradient id="pa-orange-link" x1="24" y1="48" x2="72" y2="48" gradientUnits="userSpaceOnUse">
                    <stop offset="0" stop-color="#F59300"/>
                    <stop offset="1" stop-color="#E07F29"/>
                </linearGradient>
            </defs>
            <path d="M73.5 19.5A34 34 0 0 0 18.5 61.5" fill="none" stroke="#212121" stroke-width="7.5" stroke-linecap="round"/>
            <path d="M22.5 75.5A34 34 0 0 0 77.5 34.5" fill="none" stroke="#212121" stroke-width="7.5" stroke-linecap="round"/>
            <path d="M66 28A27 27 0 0 0 29 35" fill="none" stroke="#EEE9DF" stroke-width="6" stroke-linecap="round"/>
            <path d="M30 68A27 27 0 0 0 67 61" fill="none" stroke="#EEE9DF" stroke-width="6" stroke-linecap="round"/>
            <circle cx="76" cy="25" r="8.5" fill="#FFFFFF" stroke="#E07F29" stroke-width="5"/>
            <circle cx="20" cy="73" r="8.5" fill="#FFFFFF" stroke="#E07F29" stroke-width="5"/>
            <path d="M32 48H64" fill="none" stroke="url(#pa-orange-link)" stroke-width="10" stroke-linecap="round"/>
            <circle cx="29" cy="48" r="11" fill="#F59300"/>
            <circle cx="67" cy="48" r="11" fill="#E07F29"/>
        </svg>
    </div>
    """).strip()


def _site_header(st: Any, login_visible: bool = True) -> None:
    left, right = st.columns([1, 0.16], vertical_alignment="center")
    with left:
        _html(
            st,
            f"""
            <div class="pa-site-header">
                <div class="pa-brand-lockup">
                    {_brand_mark()}
                    <div>
                        <div class="pa-brand-word">PROTACXtend</div>
                    </div>
                </div>
            </div>
            """,
        )
    with right:
        if login_visible and st.button("Login", width="stretch"):
            st.session_state["show_login"] = True
            st.rerun()


def _module_badges(items: list[str]) -> str:
    return "".join(f"<span class='pa-module-badge'>{escape(item)}</span>" for item in items)


def _signal_tags(items: list[str]) -> str:
    return "".join(f"<span class='pa-signal'>{escape(item)}</span>" for item in items)


def _degradation_visual() -> str:
    labels = ["Target binder", "Linker", "E3 ligand", "Ubiquitination", "Proteasome"]
    scores = ["DC50", "Dmax", "Cooperativity", "ADME/Tox", "Hook-effect risk"]
    return f"""
    <div class="pa-degradation-visual">
        <div class="pa-visual-labels">{''.join(f'<span class="pa-visual-label">{escape(label)}</span>' for label in labels)}</div>
        <svg class="pa-visual-svg" viewBox="0 0 720 620" role="img" aria-label="PROTAC degradation mechanism schematic">
            <defs>
                <linearGradient id="paBridge" x1="210" y1="284" x2="510" y2="284" gradientUnits="userSpaceOnUse">
                    <stop offset="0" stop-color="#F59300"/>
                    <stop offset="1" stop-color="#E07F29"/>
                </linearGradient>
                <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="16" stdDeviation="16" flood-color="#212121" flood-opacity="0.12"/>
                </filter>
            </defs>
            <path d="M130 252C88 206 86 148 132 112C185 70 268 99 286 169C303 237 218 295 130 252Z" fill="#fff8ed" stroke="#212121" stroke-width="5" filter="url(#softShadow)"/>
            <path d="M117 166C150 136 205 130 235 168M128 218C162 244 218 236 250 201" fill="none" stroke="#E07F29" stroke-width="5" stroke-linecap="round" opacity="0.72"/>
            <text x="116" y="318" fill="#212121" font-size="20" font-weight="800">Target protein</text>
            <path d="M578 260C636 225 637 151 584 112C527 70 439 107 438 183C437 247 510 301 578 260Z" fill="#fff8ed" stroke="#212121" stroke-width="5" filter="url(#softShadow)"/>
            <path d="M484 164C522 137 573 143 600 179M470 217C505 246 564 240 599 204" fill="none" stroke="#F59300" stroke-width="5" stroke-linecap="round" opacity="0.72"/>
            <text x="478" y="318" fill="#212121" font-size="20" font-weight="800">E3 ligase</text>
            <path d="M230 254C285 216 438 215 492 254" fill="none" stroke="url(#paBridge)" stroke-width="13" stroke-linecap="round"/>
            <circle cx="230" cy="254" r="20" fill="#F59300" stroke="#ffffff" stroke-width="6"/>
            <circle cx="492" cy="254" r="20" fill="#E07F29" stroke="#ffffff" stroke-width="6"/>
            <circle cx="360" cy="226" r="18" fill="#212121" stroke="#ffffff" stroke-width="5"/>
            <text x="317" y="200" fill="#212121" font-size="18" font-weight="800">PROTAC bridge</text>
            <path d="M564 118C565 82 596 57 630 67C666 78 676 119 652 144C627 169 585 154 564 118Z" fill="#fff" stroke="#E07F29" stroke-width="4"/>
            <path d="M609 70C608 42 631 20 658 27C687 35 696 68 676 89" fill="none" stroke="#212121" stroke-width="4" stroke-linecap="round"/>
            <circle cx="633" cy="62" r="12" fill="#F59300"/>
            <circle cx="665" cy="33" r="10" fill="#E07F29"/>
            <circle cx="681" cy="86" r="11" fill="#F59300"/>
            <text x="520" y="50" fill="#212121" font-size="17" font-weight="800">Ubiquitin chain</text>
            <path d="M255 460C310 412 417 411 471 461L454 536H272Z" fill="#212121" opacity="0.92" filter="url(#softShadow)"/>
            <path d="M282 472H444M289 494H438M296 516H431" stroke="#F59300" stroke-width="5" stroke-linecap="round"/>
            <text x="298" y="578" fill="#212121" font-size="20" font-weight="800">Proteasome-mediated degradation</text>
            <path d="M548 275C560 344 506 398 453 438" fill="none" stroke="#E07F29" stroke-width="5" stroke-dasharray="10 10" stroke-linecap="round"/>
            <path d="M174 277C180 356 236 409 290 440" fill="none" stroke="#F59300" stroke-width="5" stroke-dasharray="10 10" stroke-linecap="round"/>
        </svg>
        <div class="pa-score-tags">{''.join(f'<span class="pa-score-tag">{escape(tag)}</span>' for tag in scores)}</div>
    </div>
    """


def _premium_card(title: str, body: str) -> str:
    return f"""
    <div class="pa-premium-card">
        <h3>{escape(title)}</h3>
        <p>{escape(body)}</p>
    </div>
    """


def _workflow_card(index: int, title: str, body: str, signals: list[str]) -> str:
    return f"""
    <div class="pa-workflow-card">
        <div class="pa-step-index">{index:02d}</div>
        <div>
            <h3>{escape(title)}</h3>
            <p>{escape(body)}</p>
            <div class="pa-signal-row">{_signal_tags(signals)}</div>
        </div>
    </div>
    """


def _render_login(st: Any) -> None:
    hero_image = _asset_data_uri(HERO_BG_PATH)
    challenge_image = _asset_data_uri(CHALLENGE_INFOGRAPHIC_PATH)
    _site_header(st, login_visible=True)
    _html(st, "<div class='pa-landing-shell'>")
    if st.session_state.get("show_login"):
        _html(st, "<div class='pa-login-inline'>")
        _html(
            st,
            """
            <div class="pa-login-panel">
                <div class="pa-kicker">Workspace access</div>
                <h2 style="margin:8px 0 10px;color:var(--card-foreground);font-size:1.45rem;">Sign in</h2>
                <div class="pa-copy">Local account storage preserves chat history, candidate tables, traces, and reports.</div>
            </div>
            """,
        )
        mode = st.radio("Access", ["Sign in", "Create account"], horizontal=True, label_visibility="collapsed", key="landing_access_mode")
        username = st.text_input("Username", placeholder="researcher", key="landing_username")
        password = st.text_input("Password", type="password", placeholder="Local password", key="landing_password")
        if mode == "Sign in":
            if st.button("Enter workspace", type="primary", width="stretch", key="landing_enter_workspace"):
                user = _authenticate(username, password)
                if user:
                    st.session_state["user"] = user
                    chats = _list_chats(user["id"])
                    st.session_state["chat_id"] = chats[0]["id"] if chats else _new_chat(user["id"])
                    st.rerun()
                st.error("Invalid username or password.")
        else:
            if st.button("Create local workspace", type="primary", width="stretch", key="landing_create_workspace"):
                ok, message = _create_user(username, password)
                if ok:
                    st.success(message)
                else:
                    st.error(message)
        _html(st, "</div>")
    if hero_image:
        _html(
            st,
            f"""
            <div class="pa-pathway-hero">
                <img src="{hero_image}" alt="Targeted protein degradation pathway illustration">
            </div>
            <div class="pa-pathway-caption">
                <span>Harnessing PROTACs to eliminate disease-driving proteins</span>
            </div>
            """,
        )
    if challenge_image:
        _html(
            st,
            f"""
            <div class="pa-infographic-panel">
                <img src="{challenge_image}" alt="Designing PROTACs is challenging infographic">
            </div>
            """,
        )
    _html(
        st,
        f"""
        <div class="pa-landing-hero">
            <div class="pa-hero-copy">
                <div class="pa-kicker">Local degrader-engineering workspace</div>
                <div class="pa-title">PROTACXtend</div>
                <div class="pa-subtitle">From target hypothesis to clinically relevant degrader candidates.</div>
                <div class="pa-copy" style="margin-left:auto;margin-right:auto;">
                    A local, traceable research workspace for designing and prioritizing bifunctional degraders through target tractability, warhead evidence, E3 ligase context, linker geometry, ternary-complex feasibility, degradation endpoint ranking, and ADME/Tox-aware filtering.
                </div>
                <div class="pa-product-line">Design. Rank. Trace. Report.</div>
            </div>
        </div>
        """,
    )
    c1, c2, c3 = st.columns([0.36, 0.28, 0.36])
    with c1:
        if st.button("Start local session", type="primary", width="stretch"):
            st.session_state["show_login"] = True
            st.rerun()
    with c2:
        if st.button("Open chat workspace", width="stretch"):
            st.session_state["show_login"] = True
            st.rerun()
    _html(st, f"<div class='pa-module-row'>{_module_badges(TECHNICAL_MODULES)}</div>")

    _html(
        st,
        """
        <div class="pa-section">
            <h2>Clinically relevant degrader design workflow</h2>
            <div class="pa-section-intro">A vertical research engine for moving from biological hypothesis to ranked degrader hypotheses while retaining provenance and limitations.</div>
        </div>
        """,
    )
    _html(st, "<div class='pa-workflow-list'>" + "".join(_workflow_card(i, *step) for i, step in enumerate(WORKFLOW_STEPS, start=1)) + "</div>")

    _html(
        st,
        """
        <div class="pa-section">
            <h2>One backend. Two ways to work.</h2>
            <div class="pa-section-intro">
                PROTACXtend exposes the same degrader-design engine through both a structured workspace and a chat interface. The chat is not a separate demo layer; it uses the same local session, candidate tables, tool registry, ranking logic, workflow trace, and report archive.
            </div>
            <div class="pa-card-grid-2">
        """
        + _premium_card(
            "Structured workspace",
            "Use guided forms to define target biology, E3 ligase context, linker constraints, ADME/Tox filters, and ranking objectives. Best for controlled candidate design and reproducible screening.",
        )
        + _premium_card(
            "Chat research interface",
            "Use natural-language prompts to ask the same backend to generate candidates, explain ranking decisions, inspect rejected molecules, compare E3 strategies, summarize reports, or retrieve prior workflow history.",
        )
        + "</div></div>",
    )

    _html(
        st,
        "<div class='pa-section'><h2>PROTACXtend research capabilities</h2>"
        + "<div class='pa-section-intro'>Use natural language to drive the same local degrader-design workflow, inspect saved evidence, and retrieve session outputs without leaving the research workspace.</div>"
        + "<div class='pa-chat-capabilities'>"
        + "".join(f"<div>{escape(item)}</div>" for item in CHAT_SUPPORT)
        + "</div></div>",
    )

    premium_cards = [
        ("Design briefs", "Define the target, disease context, E3 ligase preference, linker constraints, desired degradation profile, and ADME/Tox boundaries in one structured local session."),
        ("Candidate construction", "Generate or import PROTAC-like candidates, normalize structures, annotate warhead-linker-E3 components, and calculate degrader-relevant molecular properties."),
        ("Degradation-aware ranking", "Prioritize candidates using DC50, Dmax, ternary-complex plausibility, E3 compatibility, hook-effect risk, linker quality, ADME/Tox liability, and synthetic feasibility."),
        ("Traceable reports", "Preserve candidate tables, tool calls, scoring outputs, rejection reasons, ranking rationale, and final summaries in a local SQLite-backed report archive."),
    ]
    _html(
        st,
        "<div class='pa-section'><div class='pa-card-grid-4'>"
        + "".join(_premium_card(title, body) for title, body in premium_cards)
        + "</div></div>",
    )
    _html(st, "<div class='pa-footer-line'>Built for local, reproducible PROTAC research workflows - from molecular design to ranked degrader hypotheses.</div></div>")


def _render_sidebar(st: Any) -> None:
    user = st.session_state["user"]
    _html(
        st.sidebar,
        f"""
        <div class="pa-brand-lockup">
            {_brand_mark()}
            <div>
                <div class="pa-brand-word">PROTACXtend</div>
                <div class="pa-brand-sub">Research workspace</div>
            </div>
        </div>
        """,
    )
    _html(st.sidebar, f"<span class='pa-chip'>Signed in: {escape(user['username'])}</span>")
    st.sidebar.write("")
    if st.sidebar.button("New session", type="primary", width="stretch"):
        st.session_state["chat_id"] = _new_chat(user["id"])
        st.rerun()
    _html(
        st.sidebar,
        f"""
        <div class="pa-side-nav-title">Session</div>
        <div class="pa-side-nav-item"><span>Candidate tables</span><span>rank</span></div>
        <div class="pa-side-nav-item"><span>Reports</span><span>md</span></div>
        <div class="pa-side-nav-item"><span>Trace</span><span>log</span></div>
        <div class="pa-side-nav-item"><span>Agents</span><span>{AGENT_COUNT}</span></div>
        """,
    )
    st.sidebar.markdown("#### Recent")
    for chat in _list_chats(user["id"])[:5]:
        label = chat["title"] or "Untitled chat"
        active = chat["id"] == st.session_state.get("chat_id")
        if st.sidebar.button(("● " if active else "") + label, key=f"chat-{chat['id']}", width="stretch"):
            st.session_state["chat_id"] = chat["id"]
            st.session_state.setdefault("visible_chat_messages", {})[chat["id"]] = _messages(chat["id"])
            st.session_state["last_run_chat_id"] = chat["id"]
            st.rerun()
    st.sidebar.divider()

    # ── LLM provider control (any API backend; Ollama default) ──
    _render_llm_provider_control(st)

    # ── HERUKA.AI channel (export/push auditable run bundles) ──
    _render_heruka_control(st)

    st.sidebar.divider()
    if st.sidebar.button("Log out", width="stretch"):
        for key in ["user", "chat_id"]:
            st.session_state.pop(key, None)
        st.rerun()


def _render_heruka_control(st: Any) -> None:
    """Sidebar widget: export/push the latest run to the HERUKA frontend."""
    import requests as _requests
    st.sidebar.markdown("#### HERUKA.AI channel")
    run_id = st.session_state.get("last_run_id", "")
    if not run_id:
        st.sidebar.caption("No run yet — run a design first.")
        return
    st.sidebar.caption(f"Run: `{run_id}`")
    col1, col2 = st.sidebar.columns(2)
    if col1.button("Export bundle", use_container_width=True):
        try:
            from protacxtend.integrations.heruka import export_bundle
            p = export_bundle(run_id)
            st.sidebar.success(f"Exported: {p.name}")
        except Exception as exc:
            st.sidebar.error(str(exc)[:100])
    if col2.button("Push to HERUKA", use_container_width=True):
        try:
            from protacxtend.integrations.heruka import push_bundle
            r = push_bundle(run_id)
            st.sidebar.success("Pushed" if r.get("ok") else f"Saved locally ({r.get('error', 'no endpoint')})")
        except Exception as exc:
            st.sidebar.error(str(exc)[:100])


def _render_llm_provider_control(st: Any) -> None:
    """Sidebar widget: switch the LLM provider (Ollama ↔ any API).

    Talks to the backend /llm endpoints; the same provider config drives
    the decision layer (llm/gateway.py). Falls back silently if the API
    is unreachable (local Ollama still works via env config).
    """
    import requests as _requests
    st.sidebar.markdown("#### LLM backend")
    api = st.session_state.get("api_base", "http://127.0.0.1:8000")
    try:
        r = _requests.get(f"{api}/llm/status", timeout=5)
        status = r.json() if r.ok else {}
        active = status.get("active", {})
        providers = status.get("providers", ["ollama"])
    except Exception:
        active, providers = {}, ["ollama"]
    st.sidebar.caption(
        f"Active: **{active.get('provider', 'ollama')}** / {active.get('model', 'gpt-oss:20b')}"
    )
    provider = st.sidebar.selectbox(
        "Provider", providers,
        index=providers.index(active.get("provider", "ollama")) if active.get("provider") in providers else 0,
        key="llm_provider_sel",
    )
    model = st.sidebar.text_input("Model", value=active.get("model", "gpt-oss:20b"), key="llm_model_sel")
    base_url = st.sidebar.text_input("Base URL (API)", value=active.get("base_url", ""), key="llm_base_sel")
    api_key = st.sidebar.text_input("API key", type="password", value="", key="llm_key_sel")
    col1, col2 = st.sidebar.columns(2)
    if col1.button("Apply", use_container_width=True):
        try:
            resp = _requests.post(
                f"{api}/llm/switch",
                json={"provider": provider, "model": model, "base_url": base_url, "api_key": api_key},
                timeout=10,
            )
            if resp.ok:
                st.sidebar.success(f"Switched to {provider}")
            else:
                st.sidebar.error(resp.json().get("detail", "switch failed"))
        except Exception as exc:
            st.sidebar.error(f"API unreachable: {exc}")
    if col2.button("Test", use_container_width=True):
        try:
            resp = _requests.post(
                f"{api}/llm/test",
                json={"provider": provider, "model": model, "base_url": base_url, "api_key": api_key},
                timeout=120,
            )
            j = resp.json()
            if j.get("ok"):
                st.sidebar.success("LLM responds with valid schema")
            else:
                st.sidebar.error(j.get("error", "test failed"))
        except Exception as exc:
            st.sidebar.error(f"test error: {exc}")


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _format_table_value(value: Any) -> str:
    if _is_missing(value):
        return ""
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return escape(str(value))


def _score_cell(value: Any) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return _format_table_value(value)
    if math.isnan(score):
        return ""
    clamped = min(max(score, 0.0), 1.0)
    label = f"{score:.3f}".rstrip("0").rstrip(".")
    return (
        "<div class='pa-score-cell'><div class='pa-score-track'>"
        f"<div class='pa-score-fill' style='width:{clamped * 100:.1f}%;'></div>"
        f"</div><span>{label}</span></div>"
    )


def _table_frame(pd: Any, rows: list[dict[str, Any]]) -> Any:
    compact_columns = [
        "Rank",
        "Tier",
        "Target",
        "E3 ligase",
        "Warhead name",
        "Linker class",
        "Predicted DC50 nM",
        "Predicted Dmax %",
        "hERG risk",
        "DILI risk",
        "Synthetic feasibility score",
        "Final priority score",
        "Warning flags",
    ]
    frame = pd.DataFrame(rows)
    return frame[[column for column in compact_columns if column in frame.columns]]


def _render_table(st: Any, frame: Any) -> None:
    score_columns = {"Synthetic feasibility score", "Final priority score"}
    header = "".join(f"<th>{escape(str(column))}</th>" for column in frame.columns)
    body_rows = []
    for row in frame.to_dict(orient="records"):
        cells = []
        for column in frame.columns:
            value = row.get(column)
            cells.append(f"<td>{_score_cell(value) if column in score_columns else _format_table_value(value)}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    _html(
        st,
        "<div class='pa-table-wrap'><table class='pa-results-table'>"
        f"<thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody>"
        "</table></div>",
    )


def _render_stats(st: Any, summary: dict[str, Any]) -> None:
    cards = [
        ("Target", summary.get("target", "-")),
        ("E3", summary.get("e3_ligase", "-")),
        ("Warheads", summary.get("warheads_selected", 0)),
        ("Linkers", summary.get("linkers_generated", 0)),
        ("Candidates", summary.get("valid_candidates", 0)),
        ("Top score", summary.get("top_score", "-")),
    ]
    html = ["<div class='pa-stat-grid'>"]
    for label, value in cards:
        html.append(f"<div class='pa-stat'><div class='label'>{escape(str(label))}</div><div class='value'>{escape(str(value))}</div></div>")
    html.append("</div>")
    _html(st, "".join(html))


def _constraint_panel(run: dict[str, Any] | None) -> str:
    if not run:
        values = {
            "Current design brief": "not_run",
            "Active constraints": "not_run",
            "Selected target": "not_run",
            "Selected E3 ligase": "not_run",
            "Linker preferences": "not_run",
            "ADME/Tox filters": "not_run",
            "Ranking objective": "not_run",
        }
    else:
        summary = run["summary"]
        state = run["state"]
        objective = state.get("parsed_objective", {})
        values = {
            "Current design brief": run.get("request", "not_available"),
            "Active constraints": json.dumps(objective.get("admet_constraints", {}) or {}, ensure_ascii=True) or "heuristic_only",
            "Selected target": summary.get("target") or "not_available",
            "Selected E3 ligase": summary.get("e3_ligase") or "not_available",
            "Linker preferences": ", ".join(objective.get("preferred_linker_types", []) or []) or "heuristic_only",
            "ADME/Tox filters": json.dumps(objective.get("admet_constraints", {}) or {}, ensure_ascii=True) or "heuristic_only",
            "Ranking objective": objective.get("optimization_objective") or "heuristic_only",
        }
    rows = "".join(f"<div><strong>{escape(key)}</strong>{escape(str(value))}</div>" for key, value in values.items())
    return f"""
    <div class="pa-constraint-panel">
        <div class="pa-kicker">Active research context</div>
        <h3 style="margin:8px 0 14px;color:var(--card-foreground);">Design brief controls</h3>
        <div class="pa-constraint-kv">{rows}</div>
    </div>
    """


def _tool_call_summary(state: dict[str, Any]) -> str:
    traces = state.get("workflow_log", [])
    if not traces:
        return "<div class='pa-tool-call'>Tool-call summaries: not_run</div>"
    rows = []
    for item in traces[-8:]:
        agent = item.get("agent", "workflow")
        action = item.get("action", "not_available")
        observation = item.get("observation", "")
        rows.append(
            f"<div class='pa-tool-call'><strong>{escape(str(agent))}</strong><br>"
            f"<span>{escape(str(action))}</span><br><span>{escape(str(observation))}</span></div>"
        )
    return "".join(rows)


def _visible_warnings(summary: dict[str, Any]) -> list[str]:
    warnings = summary.get("warnings", [])
    if RDKIT_AVAILABLE:
        return [warning for warning in warnings if "RDKit is not installed" not in warning]
    return warnings


def _registry_display_rows() -> list[dict[str, str]]:
    registry = ToolRegistry()
    if hasattr(registry, "as_display_rows"):
        return registry.as_display_rows()
    rows: list[dict[str, str]] = []
    for row in registry.as_rows():
        rows.append({key: json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list)) else str(value or "") for key, value in row.items()})
    return rows


def _run_design(st: Any, request: str) -> None:
    chat_id = st.session_state["chat_id"]
    _save_message(chat_id, "user", request)
    with st.spinner("Running PROTACXtend agent workflow..."):
        state = run_workflow_from_request(request)
    summary = summarize_state(state)
    rows = generate_candidate_table(state)
    tool_counts = summary.get("tool_status_counts", {})
    status_note = ", ".join(f"{key}: {value}" for key, value in sorted(tool_counts.items())) or "tool availability recorded"
    response = (
        f"PROTACXtend run complete: {summary.get('valid_candidates', 0)} candidate(s), "
        f"{summary.get('warheads_selected', 0)} selected warhead(s), top priority score {summary.get('top_score')}. "
        f"Synthesis feasibility, ADME/Tox signals, and ranking rationale are available below. Tool status: {status_note}."
    )
    _save_message(chat_id, "assistant", response)
    _save_run(chat_id, request, state, summary, rows)
    st.session_state["last_run_chat_id"] = chat_id


def _candidate_index_from_prompt(prompt: str) -> int | None:
    import re

    match = re.search(r"(?:candidate|rank)\s*(\d+)", prompt.lower())
    if not match:
        return None
    return int(match.group(1))


def _handle_chat_prompt(st: Any, prompt: str) -> None:
    chat_id = st.session_state["chat_id"]
    normalized = prompt.strip().lower()
    run = _latest_run(chat_id)
    retrieval_terms = ("report", "history", "trace", "workflow", "candidate table", "ranked table", "rejected", "rejection", "why candidate")
    if not any(term in normalized for term in retrieval_terms):
        _run_design(st, prompt)
        return

    _save_message(chat_id, "user", prompt)
    if not run:
        _save_message(
            chat_id,
            "assistant",
            "No saved run is available in this local session yet. Status: not_run. Submit a design brief or import candidates first.",
        )
        st.session_state["last_run_chat_id"] = chat_id
        return

    rows = run.get("rows", [])
    state = run.get("state", {})
    if "report" in normalized:
        response = (
            "The latest report is available in the Report tab and was generated by the saved backend report logic. "
            f"Report status: {'available' if run.get('report') else 'not_available'}."
        )
    elif "trace" in normalized or "workflow" in normalized or "history" in normalized:
        trace_count = len(state.get("workflow_log", []))
        response = f"The latest workflow trace has {trace_count} recorded tool/agent steps in local SQLite session history."
    elif "rejected" in normalized or "rejection" in normalized or "why candidate" in normalized:
        candidate_number = _candidate_index_from_prompt(prompt)
        if candidate_number and 1 <= candidate_number <= len(rows):
            candidate = rows[candidate_number - 1]
            reason = candidate.get("Reason for ranking") or "not_available"
            warnings = candidate.get("Warning flags") or "not_available"
            response = (
                f"Candidate {candidate_number} review: ranking rationale: {reason}. "
                f"Rejection or uncertainty flags: {warnings}. "
                "Experimental degradation is not claimed unless provided in the input data."
            )
        else:
            response = "I could not map that request to a saved candidate row. Status: not_available. Open the ranked table or specify a candidate/rank number."
    else:
        response = f"The latest ranked candidate table has {len(rows)} rows and is available in the Ranked candidates tab."
    _save_message(chat_id, "assistant", response)
    st.session_state["last_run_chat_id"] = chat_id


def _render_messages(st: Any, chat_id: str) -> None:
    for message in _messages(chat_id):
        role = message["role"]
        _html(
            st,
            f"""
            <div class="pa-message {escape(role)}">
                <div class="pa-role">{escape(role)}</div>
                <div>{escape(message["content"]).replace(chr(10), "<br>")}</div>
            </div>
            """,
        )


def _render_results(st: Any, pd: Any, run: dict[str, Any] | None) -> None:
    if not run:
        _html(
            st,
            """
            <div class="pa-starter">
                <span class="pa-status">Ready</span>
                <h2 style="margin:14px 0 8px;color:var(--card-foreground);font-size:1.25rem;">Start with a PROTAC design brief</h2>
                <div class="pa-copy">Use a compact template so the agent can parse target biology, degrader strategy, linker scope, and ranking constraints.</div>
                <div class="pa-template">Target:
E3 ligase:
Warhead / binder:
Linker preference:
Candidate count:
ADME/Tox constraints:
Additional notes:</div>
                <div class="pa-copy" style="margin-top:12px;">Example: Design CRBN-based PROTACs for BRD4 with PEG and triazole linkers, 30 candidates, low hERG risk, and balanced ADME.</div>
            </div>
            """,
        )
        if st.button("Use example brief", type="primary", width="stretch"):
            _run_design(st, EXAMPLE_QUERIES[0])
            st.rerun()
        return

    summary = run["summary"]
    rows = run["rows"]
    state = run["state"]
    _render_stats(st, summary)
    if summary.get("errors"):
        st.caption(f"{len(summary.get('errors', []))} workflow issue(s) saved in the report and trace.")

    tab_results, tab_detail, tab_workflow, tab_registry, tab_report = st.tabs(["Ranked candidates", "Candidate detail", "Workflow", "Tool registry", "Report"])
    with tab_results:
        if rows:
            frame = _table_frame(pd, rows)
            _render_table(st, frame)
            left, right = st.columns([1, 1])
            with left:
                st.download_button(
                    "Download candidates CSV",
                    pd.DataFrame(rows).to_csv(index=False),
                    "protacxtend_candidates.csv",
                    "text/csv",
                    width="stretch",
                    key=f"download-candidates-csv-{run['created_at']}",
                )
            with right:
                st.download_button(
                    "Download candidates JSON",
                    json.dumps(rows, indent=2),
                    "protacxtend_candidates.json",
                    "application/json",
                    width="stretch",
                    key=f"download-candidates-json-{run['created_at']}",
                )
        else:
            st.info("No candidates were generated for this run.")
    with tab_detail:
        if rows:
            options = [f"Rank {row['Rank']} | {row['Tier']} | {row['Warhead name']} | {row['Linker class']}" for row in rows]
            selected = st.selectbox("Candidate", options)
            detail = rows[options.index(selected)]
            cols = st.columns(4)
            cols[0].metric("Priority", detail.get("Final priority score"))
            cols[1].metric("DC50 nM", detail.get("Predicted DC50 nM"))
            cols[2].metric("Dmax %", detail.get("Predicted Dmax %"))
            cols[3].metric("Synthesis feasibility", detail.get("Synthetic feasibility score"))
            st.code(detail.get("Full PROTAC SMILES", ""), language="text")
            st.write(detail.get("Reason for ranking", ""))
    with tab_workflow:
        traces = state.get("workflow_log", [])
        st.dataframe(pd.DataFrame(traces), hide_index=True, width="stretch", height=360)
        st.caption("Trace is saved for review. This interface still requires expert validation before synthesis.")
    with tab_registry:
        st.dataframe(pd.DataFrame(_registry_display_rows()), hide_index=True, width="stretch", height=520)
    with tab_report:
        st.download_button(
            "Download Markdown report",
            run["report"],
            "protacxtend_report.md",
            "text/markdown",
            width="stretch",
            key=f"download-report-md-{run['created_at']}",
        )
        st.markdown(run["report"])


def _render_workspace(st: Any, pd: Any) -> None:
    user = st.session_state["user"]
    if "chat_id" not in st.session_state:
        chats = _list_chats(user["id"])
        st.session_state["chat_id"] = chats[0]["id"] if chats else _new_chat(user["id"])
    st.session_state.setdefault("workspace_mode", "Structured workspace")

    chat_id = st.session_state["chat_id"]
    _render_sidebar(st)
    _html(
        st,
        f"""
        <div class="pa-topbar">
            <div>
                <div class="pa-kicker">Local degrader-design cockpit</div>
                <h1>PROTACXtend</h1>
                <div class="pa-subtle">Structured workflow and chat interface share the same local session, backend workflow, candidate-ranking pipeline, trace history, and report-generation logic.</div>
                <div class="pa-quick-row">
                    <span class="pa-quick-chip">Design</span>
                    <span class="pa-quick-chip">Rank</span>
                    <span class="pa-quick-chip">Trace</span>
                    <span class="pa-quick-chip">Report</span>
                    <span class="pa-quick-chip">{AGENT_COUNT} agents</span>
                </div>
            </div>
            <div class="pa-status">RDKit {'active' if RDKIT_AVAILABLE else 'not active'} · Local backend online</div>
        </div>
        """,
    )

    run = _latest_run(chat_id)
    m1, m2, _ = st.columns([0.16, 0.2, 0.64])
    with m1:
        if st.button("Structured workspace", type="primary" if st.session_state["workspace_mode"] == "Structured workspace" else "secondary", width="stretch"):
            st.session_state["workspace_mode"] = "Structured workspace"
            st.rerun()
    with m2:
        if st.button("Chat research interface", type="primary" if st.session_state["workspace_mode"] == "Chat research interface" else "secondary", width="stretch"):
            st.session_state["workspace_mode"] = "Chat research interface"
            st.rerun()

    if st.session_state["workspace_mode"] == "Structured workspace":
        _html(
            st,
            """
            <div class="pa-mode-shell">
            <div class="pa-science-card">
                <div class="pa-science-head">
                    <div>
                        <div class="pa-kicker">Shared backend workflow</div>
                        <div class="pa-science-label">Guided form submissions call the same degrader-design engine as chat prompts.</div>
                    </div>
                    <span class="pa-status">one local session</span>
                </div>
                <div class="pa-schematic">
                    <div class="pa-node"><strong>Target hypothesis</strong><span>biology, binders, and tractability</span></div>
                    <div class="pa-linker"></div>
                    <div class="pa-node"><strong>Ranked candidates</strong><span>workflow trace and report archive</span></div>
                </div>
            </div>
            """,
        )
        with st.form("structured_design_form"):
            col_a, col_b, col_c = st.columns(3)
            target = col_a.text_input("Target or disease hypothesis", placeholder="BRD4, EGFR, kinase target...")
            e3 = col_b.selectbox("E3 ligase preference", ["CRBN", "VHL", "CRBN/VHL branch", "IAP", "MDM2", "DCAF", "Other"])
            candidate_count = col_c.number_input("Candidate count", min_value=1, max_value=200, value=30, step=5)
            linker = st.multiselect("Linker preferences", ["PEG", "alkyl", "piperazine", "triazole", "aromatic", "rigid", "polar"], default=["PEG", "alkyl", "triazole"])
            constraints = st.text_area(
                "ADME/Tox filters and ranking objective",
                placeholder="Low hERG risk, balanced cLogP/TPSA, low DC50, high Dmax, synthetic feasibility...",
                height=110,
            )
            submitted = st.form_submit_button("Start PROTACXtend run", type="primary", width="stretch")
        if submitted:
            brief = (
                f"Design {e3}-based PROTAC candidates for {target or 'the provided target hypothesis'}. "
                f"Generate {candidate_count} candidates using {', '.join(linker) or 'backend-selected'} linkers. "
                f"Optimize for {constraints or 'low DC50, high Dmax, ADME/Tox-aware filtering, synthetic feasibility, and traceable ranking'}."
            )
            _run_design(st, brief)
            st.rerun()
        display_run = run if st.session_state.get("last_run_chat_id") == chat_id else None
        _render_results(st, pd, display_run)
        _html(st, "</div>")

    else:
        _html(st, "<div class='pa-mode-shell'>")
        _html(st, "<div class='pa-chat-shell'>")
        messages = _current_messages(chat_id)
        display_run = run if st.session_state.get("last_run_chat_id") == chat_id else None
        if not messages and not display_run:
            _html(
                st,
                """
                <div class="pa-chat-empty">
                    <div>
                        <div class="pa-kicker">Chat research interface</div>
                        <h3 style="color:var(--card-foreground);margin:8px 0;">Ask PROTACXtend</h3>
                        <div>Describe a target and constraints, or paste PROTAC SMILES.</div>
                    </div>
                </div>
                """,
            )
        else:
            for message in messages:
                role = message["role"]
                _html(
                    st,
                    f"""
                    <div class="pa-message {escape(role)}">
                        <div class="pa-role">{escape(role)}</div>
                        <div>{escape(message["content"]).replace(chr(10), "<br>")}</div>
                    </div>
                    """,
                )
        if display_run:
            _render_results(st, pd, display_run)
        _html(st, "</div>")
        _html(st, "</div>")

    if st.session_state["workspace_mode"] == "Chat research interface":
        prompt = st.chat_input("Describe a target, E3 ligase preference, linker constraints, or paste candidate SMILES...")
        if prompt and prompt.strip():
            _handle_chat_prompt(st, prompt.strip())
            st.rerun()


def main() -> None:
    try:
        import pandas as pd
        import streamlit as st
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Install streamlit and pandas to run the UI.") from exc

    _init_db()
    st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="expanded")
    _inject_css(st, is_authenticated="user" in st.session_state)

    if "user" not in st.session_state:
        _render_login(st)
        return
    _render_workspace(st, pd)


if __name__ == "__main__":
    main()
