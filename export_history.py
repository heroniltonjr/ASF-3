import json
import re
import os
from datetime import datetime

transcript_path = r"C:\Users\mcaln\.gemini\antigravity-ide\brain\054a52ab-dd14-4123-88e0-9c7b3ad8d594\.system_generated\logs\transcript_full.jsonl"
output_path = r"C:\ProjetosMLDB\AIOX_Pro_New\docs\historico_conversa_formulaos_asf3.md"

turns = []
current_turn = None

with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        obj = json.loads(line)
        stype = obj.get("type")
        source = obj.get("source")
        content = obj.get("content", "")
        timestamp = obj.get("timestamp")

        if stype == "USER_INPUT" and source == "USER_EXPLICIT":
            # Extrair somente o conteúdo da tag <USER_REQUEST> se existir
            m = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", content, re.DOTALL)
            clean_text = m.group(1).strip() if m else content.strip()

            # Evitar turnos vazios ou redundantes de retry 503
            if "Error: UNAVAILABLE" in clean_text and "<USER_REQUEST>" not in content:
                continue

            if current_turn:
                turns.append(current_turn)
            current_turn = {
                "user": clean_text,
                "timestamp": timestamp,
                "assistant_responses": []
            }
        elif stype == "PLANNER_RESPONSE" and source == "MODEL":
            tool_calls = obj.get("tool_calls", [])
            # Quando content não está vazio e não é apenas um call intermediário sem texto
            if content and content.strip() and not tool_calls and current_turn is not None:
                current_turn["assistant_responses"].append({
                    "text": content.strip(),
                    "timestamp": timestamp
                })

if current_turn:
    turns.append(current_turn)

print(f"Total de turnos encontrados: {len(turns)}")

# Gerar arquivo Markdown
md_lines = []
md_lines.append("# Histórico Completo de Conversa — Formula OS / ASF-3")
md_lines.append("")
md_lines.append(f"> **Data de Exportação:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
md_lines.append(f"> **Conversation ID:** `054a52ab-dd14-4123-88e0-9c7b3ad8d594`")
md_lines.append(f"> **Total de Interações:** {len(turns)} turnos")
md_lines.append("")
md_lines.append("---")
md_lines.append("")

for idx, turn in enumerate(turns, start=1):
    ts_str = f" ({turn['timestamp']})" if turn.get("timestamp") else ""
    md_lines.append(f"## 👤 Turno {idx} — Usuário{ts_str}")
    md_lines.append("")
    md_lines.append(turn["user"])
    md_lines.append("")
    
    md_lines.append(f"### 🤖 Resposta — Assistente")
    md_lines.append("")
    if turn["assistant_responses"]:
        # Se houver mais de uma resposta no turno, junta com separador
        combined_resp = "\n\n---\n\n".join(r["text"] for r in turn["assistant_responses"])
        md_lines.append(combined_resp)
    else:
        md_lines.append("*(Ações executadas em segundo plano/ferramentas)*")
    
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

print(f"Histórico exportado com sucesso para: {output_path}")
print(f"Tamanho do arquivo: {os.path.getsize(output_path)} bytes")
