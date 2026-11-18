"""Run one actor followed by two monitors; API or manual-paste per role."""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import UTC, datetime
from getpass import getpass
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph


HERE = Path(__file__).resolve().parent
for env_path in (
    HERE / ".venv" / ".env",
    HERE / ".env",
    HERE.parent / ".env",
    HERE.parent.parent / ".env",
):
    if env_path.exists():
        load_dotenv(env_path, override=True)
        break
PACKAGED_PROMPTS = HERE.parent / "prompts" / "experiment-prompts.md"
STANDALONE_PROMPTS = HERE / "experiment-prompts.md"
PROMPT_PACK = PACKAGED_PROMPTS if PACKAGED_PROMPTS.exists() else STANDALONE_PROMPTS
END_MARKER = "<<<END RESPONSE>>>"
GROQ_MODEL_DEFAULT = "openai/gpt-oss-20b"


class EvalState(TypedDict, total=False):
    run_id: str
    run_dir: str
    packet: str
    actor_prompt: str
    monitor_prompt: str
    actor_mode: str
    actor_label: str
    monitor_1_mode: str
    monitor_1_label: str
    monitor_2_mode: str
    monitor_2_label: str
    actor_response: str
    monitor_1_response: str
    monitor_2_response: str
    actor_call_metadata: dict[str, object]
    monitor_1_call_metadata: dict[str, object]
    monitor_2_call_metadata: dict[str, object]


def fenced_block(section: str) -> str:
    """Return the first fenced text block from a Markdown section."""
    marker = "```text"
    if marker not in section:
        raise ValueError("Expected a ```text block in the prompt pack.")
    content = section.split(marker, 1)[1].split("```", 1)[0]
    return content.strip()


def section_between(document: str, start: str, end: str) -> str:
    try:
        section = document.split(start, 1)[1]
    except IndexError as exc:
        raise ValueError(f"Prompt section not found: {start}") from exc
    if end:
        try:
            section = section.split(end, 1)[0]
        except IndexError as exc:
            raise ValueError(f"End heading not found: {end}") from exc
    return section


def load_prompts() -> tuple[str, str, str]:
    text = PROMPT_PACK.read_text(encoding="utf-8")
    packet_section = section_between(
        text, "## A2.", "## B. Actor prompt"
    )
    actor_section = section_between(
        text, "## B. Actor prompt", "## C. Monitor prompt"
    )
    monitor_section = section_between(
        text, "## C. Monitor prompt", "## Original planned run order"
    )
    return (
        fenced_block(packet_section),
        fenced_block(actor_section),
        fenced_block(monitor_section),
    )


API_KEY_NAMES = {
    "groq_api": ("GROQ_API_KEY", ("groq_api_key",)),
    "openai_api": ("OPENAI_API_KEY", ("open_api_key", "openai_api_key")),
    "google_api": ("GOOGLE_API_KEY", ("google_api_key", "gemini_api_key")),
}


def ensure_api_key(mode: str) -> None:
    canonical_name, aliases = API_KEY_NAMES[mode]
    if os.getenv(canonical_name):
        return
    for alias in aliases:
        value = os.getenv(alias)
        if value:
            os.environ[canonical_name] = value
            return
    os.environ[canonical_name] = getpass(
        f"{canonical_name} (input hidden): "
    ).strip()


DEFAULT_ROLE_SETTINGS = {
    "ACTOR": ("groq_api", "openai/gpt-oss-20b"),
    "MONITOR_1": ("google_api", "gemini-3.5-flash-lite"),
    "MONITOR_2": ("groq_api", "openai/gpt-oss-120b"),
}


def role_settings(role: str) -> tuple[str, str]:
    default_mode, default_label = DEFAULT_ROLE_SETTINGS[role]
    mode = os.getenv(f"{role}_MODE", default_mode).strip().lower()
    label = os.getenv(f"{role}_LABEL", default_label).strip()
    if mode not in {"manual", *API_KEY_NAMES}:
        allowed = ", ".join(["manual", *API_KEY_NAMES])
        raise ValueError(f"{role}_MODE must be one of: {allowed}.")
    if mode != "manual":
        ensure_api_key(mode)
    return mode, label


def response_text(message: object) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    return json.dumps(content, ensure_ascii=False, indent=2)


def invoke_model(mode: str, label: str, prompt: str) -> tuple[str, dict[str, object]]:
    if mode == "manual":
        print("\n" + "=" * 78)
        print(f"Paste this prompt into: {label}\n")
        print(prompt)
        print("\nPaste the complete model response below.")
        print(f"Finish by entering {END_MARKER} on a line by itself.")
        lines: list[str] = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == END_MARKER:
                break
            lines.append(line)
        response = "\n".join(lines).strip()
        if not response:
            raise ValueError(f"No response was entered for {label}.")
        return response, {"mode": mode, "configured_model_label": label}

    if mode == "groq_api":
        from langchain_groq import ChatGroq

        model = ChatGroq(model=label or GROQ_MODEL_DEFAULT, temperature=0, max_tokens=4096)
    elif mode == "openai_api":
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(model=label)
    elif mode == "google_api":
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = ChatGoogleGenerativeAI(model=label)
    else:
        raise ValueError(f"Unsupported model mode: {mode}")

    message = model.invoke(prompt)
    metadata = getattr(message, "response_metadata", {}) or {}
    usage = getattr(message, "usage_metadata", None)
    call_metadata: dict[str, object] = {
        "mode": mode,
        "configured_model_label": label,
        "returned_model_label": metadata.get("model_name") or metadata.get("model"),
    }
    if usage:
        call_metadata["usage"] = usage
    elif metadata.get("token_usage"):
        call_metadata["usage"] = metadata["token_usage"]
    return response_text(message), call_metadata


def save_text(run_dir: Path, filename: str, value: str) -> None:
    (run_dir / filename).write_text(value.rstrip() + "\n", encoding="utf-8")


def actor_node(state: EvalState) -> dict[str, object]:
    run_dir = Path(state["run_dir"])
    prompt = f"{state['packet']}\n\n{state['actor_prompt']}"
    save_text(run_dir, "actor-prompt.md", prompt)
    response, call_metadata = invoke_model(state["actor_mode"], state["actor_label"], prompt)
    save_text(run_dir, "actor-response.md", response)
    return {"actor_response": response, "actor_call_metadata": call_metadata}


def monitor_node(state: EvalState, index: int) -> dict[str, object]:
    run_dir = Path(state["run_dir"])
    response_key = f"monitor_{index}_response"
    mode_key = f"monitor_{index}_mode"
    label_key = f"monitor_{index}_label"
    prompt = (
        f"{state['packet']}\n\n"
        "Actor response under review (verbatim):\n"
        f"{state['actor_response']}\n\n"
        f"{state['monitor_prompt']}"
    )
    save_text(run_dir, f"monitor-{index}-prompt.md", prompt)
    response, call_metadata = invoke_model(state[mode_key], state[label_key], prompt)
    save_text(run_dir, f"monitor-{index}-response.md", response)
    metadata_key = f"monitor_{index}_call_metadata"
    return {response_key: response, metadata_key: call_metadata}


def monitor_1_node(state: EvalState) -> dict[str, object]:
    return monitor_node(state, 1)


def monitor_2_node(state: EvalState) -> dict[str, object]:
    return monitor_node(state, 2)


def finalize_node(state: EvalState) -> dict[str, str]:
    run_dir = Path(state["run_dir"])
    metadata = {
        "run_id": state["run_id"],
        "created_at_utc": datetime.now(UTC).isoformat(),
        "condition": "A2",
        "actor": {
            "mode": state["actor_mode"],
            "label": state["actor_label"],
            **state.get("actor_call_metadata", {}),
        },
        "monitor_1": {
            "mode": state["monitor_1_mode"],
            "label": state["monitor_1_label"],
            **state.get("monitor_1_call_metadata", {}),
        },
        "monitor_2": {
            "mode": state["monitor_2_mode"],
            "label": state["monitor_2_label"],
            **state.get("monitor_2_call_metadata", {}),
        },
        "complete": all(
            state.get(key)
            for key in ("actor_response", "monitor_1_response", "monitor_2_response")
        ),
    }
    (run_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {}


def build_graph():
    graph = StateGraph(EvalState)
    graph.add_node("actor", actor_node)
    graph.add_node("monitor_1", monitor_1_node)
    graph.add_node("monitor_2", monitor_2_node)
    graph.add_node("finalize", finalize_node)
    graph.add_edge(START, "actor")
    graph.add_edge("actor", "monitor_1")
    graph.add_edge("monitor_1", "monitor_2")
    graph.add_edge("monitor_2", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def main() -> int:
    if not PROMPT_PACK.exists():
        print(f"Prompt pack not found: {PROMPT_PACK}", file=sys.stderr)
        return 2

    packet, actor_prompt, monitor_prompt = load_prompts()
    actor_mode, actor_label = role_settings("ACTOR")
    monitor_1_mode, monitor_1_label = role_settings("MONITOR_1")
    monitor_2_mode, monitor_2_label = role_settings("MONITOR_2")
    print("Selected models:")
    print(f"  Actor: {actor_mode} / {actor_label}")
    print(f"  Monitor 1: {monitor_1_mode} / {monitor_1_label}")
    print(f"  Monitor 2: {monitor_2_mode} / {monitor_2_label}")

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    runs_root = (HERE / os.getenv("RUNS_DIR", "runs")).resolve()
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    state: EvalState = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "packet": packet,
        "actor_prompt": actor_prompt,
        "monitor_prompt": monitor_prompt,
        "actor_mode": actor_mode,
        "actor_label": actor_label,
        "monitor_1_mode": monitor_1_mode,
        "monitor_1_label": monitor_1_label,
        "monitor_2_mode": monitor_2_mode,
        "monitor_2_label": monitor_2_label,
    }
    print(f"Run ID: {run_id}")
    result = build_graph().invoke(state)
    print(f"\nComplete. Outputs saved under: {run_dir}")
    print("Review the files before sharing or committing them.")
    return 0 if result.get("monitor_2_response") else 1


if __name__ == "__main__":
    raise SystemExit(main())
