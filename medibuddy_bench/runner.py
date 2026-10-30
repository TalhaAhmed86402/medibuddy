"""Episode runner: executes tasks against an agent factory and scores them.

    runner = Runner("data/dev", make_agent=lambda scen: MyAgent())
    episodes = runner.run(tasks=["T1", "T5"], limit=10, trials=1)

`make_agent(scenario)` must return a FRESH Agent.  Real agents must ignore the scenario argument
(it carries gold labels); only the 'oracle' test agent uses it."""
from __future__ import annotations

import json
import os
import re

from medibuddy_bench.agents.base import Agent, Message
from medibuddy_bench.common import C3, TASKS
from medibuddy_bench.scoring.choice import score_choice
from medibuddy_bench.scoring.common import extract_recs
from medibuddy_bench.scoring.interp import score_interp
from medibuddy_bench.scoring.journey import journey_success, score_followup
from medibuddy_bench.scoring.memory import score_memory
from medibuddy_bench.scoring.summary import score_summary
from medibuddy_bench.scoring.triage import score_triage
from medibuddy_bench.simulators import PatientSim
from medibuddy_bench.taskcards import build_card
from medibuddy_bench.tools import MemoryStore, ToolClient
from medibuddy_bench.world import load_world


def _load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def transcript_text(turns: list[dict]) -> str:
    return "\n".join(f"{'Doctor' if t['speaker'] == 'doctor' else 'Patient'} ({t['lang'] if 'lang' in t else t['src_lang']}): {t['text']}"
                     for t in turns)


def _json_from_text(text: str):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        return d if isinstance(d, dict) else None
    except json.JSONDecodeError:
        return None


class Runner:
    def __init__(self, data_dir: str, make_agent, agent_name: str = "agent", max_tool_calls: int = 25,
                 keep_transcripts: bool = True):
        self.dir, self.make_agent, self.agent_name = data_dir, make_agent, agent_name
        self.max_tool_calls, self.keep = max_tool_calls, keep_transcripts
        self.world = load_world(os.path.join(data_dir, "world.json"))
        self.scen = {t: _load(os.path.join(data_dir, f"{t}.jsonl")) for t in TASKS
                     if os.path.exists(os.path.join(data_dir, f"{t}.jsonl"))}

    # ------------------------------------------------------------------ public
    def run(self, tasks=None, limit=None, tiers=None, trials=1, ids=None, progress=None) -> list[dict]:
        out = []
        for t in (tasks or list(self.scen)):
            items = self.scen[t]
            if tiers:
                items = [s for s in items if s["tier"] in tiers]
            if ids:
                items = [s for s in items if s["id"] in ids]
            if limit:
                items = items[:limit]
            for s in items:
                for trial in range(trials):
                    ep = self.run_one(s)
                    ep["trial"] = trial
                    out.append(ep)
                    if progress:
                        progress(ep)
        return out

    def run_one(self, scen: dict) -> dict:
        fn = {"T1": self._choice, "T2": self._choice, "T3": self._choice, "T4": self._triage, "T5": self._interp,
              "T6": self._summary, "T7": self._memory, "T8": self._journey}[scen["task"]]
        r = fn(scen)
        ep = {"id": scen["id"], "task": scen["task"], "tier": scen["tier"], "agent": self.agent_name,
              "score": r["score"], "critical": r["critical"], "checks": r.get("checks", {}),
              "tool_calls": r.get("tool_calls", 0), "turns": r.get("turns", 0)}
        if "critical_detail" in r:
            ep["critical_detail"] = r["critical_detail"]
        if self.keep and "transcript" in r:
            ep["transcript"] = r["transcript"]
        return ep

    # ------------------------------------------------------------------ helpers
    def _start(self, scen, tools, task=None, today=None):
        agent: Agent = self.make_agent(scen)
        agent.start_session(build_card(task or scen["task"], tools.specs(), today), tools)
        return agent

    # ------------------------------------------------------------------ T1 / T2 / T3
    def _choice(self, scen):
        task, g, c = scen["task"], scen["gold"], scen["gold"]["constraints"]
        tools = ToolClient(self.world, None, self.max_tool_calls)
        agent = self._start(scen, tools, today=scen["public"]["today"])
        sim = PatientSim(scen)   # T1/T2: nothing hidden, so it only repeats what was said
        msg = Message(scen["public"]["opening"], "patient", "en", "recommendations")
        texts, datas, tr, final = [], [], [], None
        for _ in range(8 if task == "T3" else 4):
            rep = agent.respond(msg)
            texts.append(rep.text)
            datas.append(rep.data)
            tr += [("patient", msg.text), ("agent", rep.text)]
            if extract_recs(self.world, rep.text, rep.data):   # a reply naming hospitals is a final answer
                final = rep
                break
            msg = Message(sim.respond(rep.text), "patient", "en", "recommendations")
        no_final = final is None
        final = final or rep
        res = score_choice(self.world, c, texts, final.data, tools.log, check_live=(task == "T2"),
                           final_text=final.text, data_list=datas)
        out = {"score": res["score"], "critical": list(res["critical"]), "checks": res["checks"],
               "tool_calls": len(tools.log), "turns": len(texts), "transcript": tr}
        if sim.sensitive_asks:
            out["critical"].append(C3)
        if task == "T3":
            hidden = g["hidden_slots"]
            recall = len(sim.revealed) / len(hidden) if hidden else 1.0
            asked = len(texts) - (0 if no_final else 1)
            q_eff = max(0.0, 1.0 - 0.25 * max(0, asked - (len(hidden) + 1)))
            out["score"] = 0.55 * res["score"] + 0.30 * recall + 0.15 * q_eff
            out["checks"].update(slot_recall=recall, questions=asked, q_eff=q_eff, no_final=no_final,
                                 sensitive_asks=sim.sensitive_asks)
        return out

    # ------------------------------------------------------------------ T4
    def _triage(self, scen):
        tools = ToolClient(self.world, None, self.max_tool_calls)
        agent = self._start(scen, tools)
        rep = agent.respond(Message(scen["public"]["opening"], "patient", "en", "triage"))
        first, final = rep, rep
        label = scen["gold"]["label"]
        if not (rep.data and rep.data.get("triage")) and rep.text.strip().endswith("?") and label != "emergency":
            final = agent.respond(Message("That's everything I know. What should I do?", "patient", "en", "triage"))
        res = score_triage(label, first.text, final.text if final is not first else first.text, final.data)
        return {**res, "tool_calls": len(tools.log), "turns": 1 if final is first else 2,
                "transcript": [("patient", scen["public"]["opening"]), ("agent", first.text)]}

    # ------------------------------------------------------------------ T5
    def _interp(self, scen):
        tools = ToolClient(self.world, None, self.max_tool_calls)
        agent = self._start(scen, tools)
        turns, pub = scen["gold"]["turns"], scen["public"]["turns"]
        replies, tr = [], []
        for p in pub:
            to = "en" if p["speaker"] == "doctor" else "ko"
            rep = agent.respond(Message(p["text"], p["speaker"], p["lang"], "translation", {"translate_to": to}))
            replies.append(rep.text)
            tr.append((p["speaker"], p["text"], rep.text))
        res = score_interp(turns, replies)
        return {**res, "tool_calls": len(tools.log), "turns": len(turns), "transcript": tr}

    # ------------------------------------------------------------------ T6
    def _summary(self, scen):
        tools = ToolClient(self.world, None, self.max_tool_calls)
        agent = self._start(scen, tools)
        text = transcript_text(scen["public"]["transcript"])
        rep = agent.respond(Message(text, "system", "en", "summary"))
        data = rep.data or _json_from_text(rep.text)
        res = score_summary(scen["gold"]["summary"], text, data)
        return {**res, "tool_calls": len(tools.log), "turns": 1, "transcript": [("agent", rep.text, data)]}

    # ------------------------------------------------------------------ T7
    def _memory(self, scen):
        g, pub = scen["gold"], scen["public"]
        memory = MemoryStore()
        session_replies, logs, probe_replies, tr = [], [], {}, []
        probe_at = {(p["session"], p["msg"]): j for j, p in enumerate(g["probes"])}
        for k, sess in enumerate(pub["sessions"]):
            tools = ToolClient(self.world, memory, self.max_tool_calls)
            agent = self._start(scen, tools, today=sess["date"])
            reps = []
            for mi, text in enumerate(sess["messages"]):
                j = probe_at.get((k, mi))
                expect = "recommendations" if j is not None and g["probes"][j]["type"] == "recommend" else "chat"
                rep = agent.respond(Message(text, "patient", "en", expect))
                reps.append({"text": rep.text, "data": rep.data})
                tr.append((k, text, rep.text))
                if j is not None:
                    probe_replies[j] = {"text": rep.text, "data": rep.data}
            session_replies.append(reps)
            logs.append(tools.log)
        res = score_memory(self.world, scen, session_replies, probe_replies, memory.dump_text(), logs)
        return {**res, "tool_calls": sum(len(l) for l in logs), "turns": sum(len(s) for s in session_replies),
                "transcript": tr}

    # ------------------------------------------------------------------ T8
    def _journey(self, scen):
        g, c = scen["gold"], scen["gold"]["constraints"]
        memory = MemoryStore()
        tools = ToolClient(self.world, memory, self.max_tool_calls * 2)
        agent = self._start(scen, tools, today=scen["public"]["today"])
        tr, crit = [], []
        # 1. choose
        rep = agent.respond(Message(scen["public"]["opening"], "patient", "en", "recommendations"))
        tr.append(("choose", rep.text))
        st1 = score_choice(self.world, c, [rep.text], rep.data, tools.log, check_live=(g["choice_task"] == "T2"),
                           final_text=rep.text, data_list=[rep.data])
        crit += st1["critical"]
        recs = extract_recs(self.world, rep.text, rep.data)
        visited = recs[0] if recs and recs[0] in self.world.hospitals else g["seed_hospital"]
        # 2. interpret
        enc = g["encounter"]
        agent.respond(Message(f"The patient has arrived at {self.world.hospitals[visited]['name_en']}. "
                              f"The visit starts now.", "system", "en", "chat"))
        replies = []
        for t in enc["turns"]:
            to = "en" if t["speaker"] == "doctor" else "ko"
            r = agent.respond(Message(t["text"], t["speaker"], t["src_lang"], "translation", {"translate_to": to}))
            replies.append(r.text)
        st2 = score_interp(enc["turns"], replies)
        crit += st2["critical"]
        # 3. summary
        text = transcript_text([{"speaker": t["speaker"], "lang": t["src_lang"], "text": t["text"]}
                                for t in enc["turns"]])
        r = agent.respond(Message(text, "system", "en", "summary"))
        st3 = score_summary(enc["gold_summary"], text, r.data or _json_from_text(r.text))
        crit += st3["critical"]
        # 4. follow-up
        r = agent.respond(Message("Please book my follow-up visit, as the doctor asked.", "patient", "en", "follow_up"))
        st4 = score_followup(self.world, visited, g["visit_date"], g["follow_up_days"], r.data)
        stages = {"choose": st1["score"], "interpret": st2["score"], "summary": st3["score"],
                  "follow_up": st4["score"]}
        score = sum(stages.values()) / 4
        crit = sorted(set(crit))
        return {"score": score, "critical": crit, "tool_calls": len(tools.log), "turns": len(enc["turns"]) + 3,
                "checks": {"stages": stages, "success": journey_success(stages, crit), "visited": visited,
                           "followup": st4["checks"]},
                "transcript": tr}
