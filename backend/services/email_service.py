"""Serviço de envio de e-mails do Formula OS.

Suporta envio real via SMTP com STARTTLS ou SSL,
com fallback transparente de logging em arquivo caso o servidor de e-mail não esteja configurado.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from ..settings import settings

logger = logging.getLogger(__name__)

# Diretório para gravação de logs de e-mails enviados
LOGS_DIR = Path(__file__).resolve().parent.parent / "data"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
EMAILS_LOG_FILE = LOGS_DIR / "emails_sent.log"


def is_smtp_configured() -> bool:
    """Verifica se os parâmetros mínimos de SMTP foram fornecidos no ambiente."""
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    return bool(host and user)


def send_email(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
) -> bool:
    """Dispara um e-mail para o destinatário especificado.
    
    Caso o SMTP não esteja configurado, grava o conteúdo no arquivo de log `backend/data/emails_sent.log`
    e retorna True para não interromper os fluxos do sistema.
    """
    to_email = (to_email or "").strip()
    if not to_email:
        raise ValueError("Destinatário de e-mail não informado")

    from_email = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "nao-responda@autoshoppingformula.com.br")).strip()
    from_name = os.getenv("SMTP_FROM_NAME", "Formula OS").strip()

    if not is_smtp_configured():
        # Fallback local / dev: grava no arquivo de auditoria
        log_entry = (
            f"================================================================================\n"
            f"DATA/HORA: {os.getenv('TZ', 'UTC')} | DESTINATÁRIO: {to_email}\n"
            f"DE: {from_name} <{from_email}>\n"
            f"ASSUNTO: {subject}\n"
            f"-------------------------------- TEXTO -----------------------------------------\n"
            f"{body_text}\n"
            f"================================================================================\n\n"
        )
        try:
            with open(EMAILS_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as file_err:
            logger.warning("Falha ao gravar emails_sent.log: %s", file_err)
        
        logger.info("[EMAIL SERVICE SIMULATED] Para: %s | Assunto: %s", to_email, subject)
        return True

    # Envio real via SMTP
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    use_ssl = os.getenv("SMTP_SSL", "false").lower() in ("true", "1", "yes")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email

    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        if use_ssl or port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()

        if user and password:
            server.login(user, password)

        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        logger.info("[EMAIL SERVICE ENVIADO] Para: %s | Assunto: %s", to_email, subject)
        return True
    except Exception as exc:
        logger.exception("Falha ao enviar e-mail via SMTP para %s: %s", to_email, exc)
        raise RuntimeError(f"Erro no envio de e-mail: {exc}") from exc
