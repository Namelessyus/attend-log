"""Explicit local outbox or SMTP delivery; never log activation secrets."""
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from uuid import uuid4

from flask import current_app


def send_invitation(email: str, link: str) -> None:
    config = current_app.config
    message = EmailMessage()
    message["From"] = config["MAIL_FROM"]
    message["To"] = email
    message["Subject"] = "Your AttendLog teacher account"
    message.set_content(
        "Your administrator has invited you to AttendLog.\n\n"
        f"Set your password using this one-time link:\n{link}\n\n"
        "This link expires in 48 hours. If you did not expect it, contact your administrator."
    )
    if config["MAIL_BACKEND"] == "file":
        directory = Path(config["MAIL_OUTBOX"])
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        target = directory / f"{uuid4().hex}.eml"
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(message.as_bytes())
    elif config["MAIL_BACKEND"] == "smtp":
        with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"], timeout=10) as server:
            server.starttls(context=ssl.create_default_context())
            if config["SMTP_USER"]:
                server.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
            server.send_message(message)
    else:
        raise RuntimeError("Configure an invitation mail backend before creating teachers.")
