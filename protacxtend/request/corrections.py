"""Session-aware conversation state and corrections (requirement 4).

Follow-up corrections update state: if the system asked about \"EFRG\" and the
user replies \"EGFR target of interest...\", the resolver's verified result
replaces the unresolved target slot, the pending clarification is cleared,
and the original action resumes. The state before and after the update is
logged. An explicit correction never competes with an earlier token.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from protacxtend.request.model import RequestUnderstanding, TargetResolution


class ConversationState:
    def __init__(self, conversation_id: str = "default"):
        self.conversation_id = conversation_id
        self.resolved_target: Optional[TargetResolution] = None
        self.unresolved_mentions: list[str] = []
        self.pending_clarification: Optional[str] = None
        self.action: str = "plan"
        self.intent: str = "plan_protac_strategy"
        self.history: list[dict[str, Any]] = []   # before/after logs per correction

    # ------------------------------------------------------------------
    def apply_correction(self, previous: RequestUnderstanding, current: RequestUnderstanding) -> None:
        """Latest explicit correction wins: a now-verified target replaces the
        unresolved slot; pending clarification clears; action/intent resume from
        the ORIGINAL utterance (kept on the session)."""
        before = previous.to_snapshot() if previous else {}
        if current.primary_target and current.primary_target.status == "verified":
            self.resolved_target = current.primary_target
            self.unresolved_mentions = [m for m in self.unresolved_mentions
                                        if m.upper() != current.primary_target.symbol.upper()]
            self.pending_clarification = None
            if not current.raw_text.lower().startswith("/"):
                # resume the original command action unless the correction is itself a command
                if current.action in ("plan",) or not current.raw_text.strip().startswith("/"):
                    current.action = self.action or previous.action if previous else current.action
        # Only GENUINELY unresolved mentions join the unresolved list: a
        # mention that resolved (even tentatively, e.g. constrained typo) must
        # never be remembered as an open question.
        self.unresolved_mentions = list(dict.fromkeys(self.unresolved_mentions + [
            m.raw for m in current.target_mentions
            if (m.resolution is None or m.resolution.status in ("unknown", "ambiguous", "unresolved"))
            and (current.primary_target is None or m.raw.upper() != current.primary_target.symbol.upper())
        ]))
        after = current.to_snapshot()
        self.history.append({
            "conversation_id": self.conversation_id,
            "event": "correction" if before and before.get("target") != after.get("target") else "utterance",
            "state_before": before,
            "state_after": after,
        })
        current.state_before = before
        current.state_after = after

    def log(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump({"conversation_id": self.conversation_id, "history": self.history}, f, indent=1, default=str)


_SESSIONS: dict[str, ConversationState] = {}


def get_conversation(conversation_id: str = "default") -> ConversationState:
    if conversation_id not in _SESSIONS:
        _SESSIONS[conversation_id] = ConversationState(conversation_id)
    return _SESSIONS[conversation_id]


def reset_conversation(conversation_id: str = "default") -> None:
    _SESSIONS.pop(conversation_id, None)