import json
import re
import os
from datetime import datetime

transcript_path = r"C:\Users\mcaln\.gemini\antigravity-ide\brain\05b3ae97-f2b1-4621-b584-3d768656876a\.system_generated\logs\transcript_full.jsonl"
output_path = r"C:\ProjetosMLDB\ASF-3\docs\historico_conversa_completo.md"

turns = []
current_turn = None

with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            obj = json.loads(line)
        except Exception:
            continue

        stype = obj.get("type")
        source = obj.get("source")
        content = obj.get("content", "") or ""
        timestamp = obj.get("timestamp")

        if stype == "USER_INPUT" and source == "USER_EXPLICIT":
            # Extrair somente o conteúdo da tag <USER_REQUEST> se existir
            m = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", content, re.DOTALL)
            clean_text = m.group(1).strip() if m else content.strip()

            # Se houver metadata extra anexada antes de <USER_REQUEST>
            if "<USER_REQUEST>" in content:
                # Opcionalmente podemos pegar se o usuário fez uma ação antes
                action_match = re.search(r"The USER performed the following action:\s*(.*?)(?=<USER_REQUEST>|$)", content, re.DOTALL)
                action_info = action_match.group(1).strip() if action_match else None
            else:
                action_info = None

            if current_turn:
                turns.append(current_turn)

            current_turn = {
                "user": clean_text,
                "action": action_info,
                "timestamp": timestamp,
                "assistant_responses": []
            }

        elif stype == "PLANNER_RESPONSE" and source == "MODEL":
            tool_calls = obj.get("tool_calls", [])
            # Quando content não está vazio e não é apenas um call intermediário sem texto
            if content and content.strip() and not tool_calls and current_turn is not None:
                # Evitar mensagens de sistema duplicadas
                resp_text = content.strip()
                # Não repetir a exata mesma resposta
                if not current_turn["assistant_responses"] or current_turn["assistant_responses"][-1]["text"] != resp_text:
                    current_turn["assistant_responses"].append({
                        "text": resp_text,
                        "timestamp": timestamp
                    })

if current_turn:
    turns.append(current_turn)

print(f"Total de turnos processados: {len(turns)}")

md_lines = []
md_lines.append("# 📜 Histórico Completo de Conversa — Formula OS / ASF-3")
md_lines.append("")
md_lines.append(f"> **Data de Exportação:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
md_lines.append(f"> **Conversation ID:** `05b3ae97-f2b1-4621-b584-3d768656876a`")
md_lines.append(f"> **Total de Interações:** {len(turns)} turnos")
md_lines.append("")
md_lines.append("## 📑 Sumário de Tópicos")
md_lines.append("")

for idx, turn in enumerate(turns, start=1):
    first_line = turn["user"].split("\n")[0].strip()
    if len(first_line) > 90:
        first_line = first_line[:87] + "..."
    # Escape markdown chars for summary
    summary_title = first_line.replace("[", "").replace("]", "").replace("*", "")
    md_lines.append(f"- [Turno {idx}: {summary_title}](#turno-{idx})")

md_lines.append("")
md_lines.append("---")
md_lines.append("")

for idx, turn in enumerate(turns, start=1):
    ts_str = f" — *{turn['timestamp']}*" if turn.get("timestamp") else ""
    md_lines.append(f"<a id='turno-{idx}'></a>")
    md_lines.append(f"## 👤 Turno {idx}{ts_str}")
    md_lines.append("")

    if turn.get("action"):
        md_lines.append(f"> ℹ️ **Ação do Usuário no Editor:** {turn['action']}")
        md_lines.append("")

    md_lines.append(turn["user"])
    md_lines.append("")

    md_lines.append("### 🤖 Resposta — Antigravity / AIOX Master")
    md_lines.append("")

    if turn["assistant_responses"]:
        combined_resp = "\n\n---\n\n".join(r["text"] for r in turn["assistant_responses"])
        md_lines.append(combined_resp)
    else:
        md_lines.append("*(Operações técnicas automatizadas / chamadas de ferramentas executadas)*")

    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

print(f"Sucesso! Arquivo gerado em: {output_path}")
print(f"Tamanho total: {os.path.getsize(output_path)} bytes")
