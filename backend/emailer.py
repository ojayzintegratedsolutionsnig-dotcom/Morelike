import os
import resend

RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'noreply@contact.morelikecreator.com')

_configured = False


def _ensure_configured():
    global _configured
    if not _configured and RESEND_API_KEY:
        resend.api_key = RESEND_API_KEY
        _configured = True


def send_token_email(to_email, token):
    if not RESEND_API_KEY:
        print(f"[EMAIL SKIP] No RESEND_API_KEY set. Token for {to_email}: {token}")
        return

    _ensure_configured()
    resend.Emails.send({
        "from": f"Morelike <{FROM_EMAIL}>",
        "to": [to_email],
        "subject": "Your Morelike Access Token",
        "html": f"""
            <h2>Welcome to Morelike!</h2>
            <p>Your access token is:</p>
            <h1 style="font-family:monospace;background:#f5f5f5;padding:16px;border-radius:8px;">
                {token}
            </h1>
            <p><strong>Credits remaining:</strong> 1</p>
            <p>Go to <a href="https://morelikecreator.com/portal">the portal</a> and enter this token to start.</p>
            <p>Keep this email safe — if you lose your token, you can reclaim it with this email address.</p>
            <hr/>
            <p style="color:#888;">Morelike — Reverse-engineer viral content strategies</p>
        """
    })


def send_reply_email(to_email, reply_text):
    if not RESEND_API_KEY:
        print(f"[EMAIL SKIP] Reply to {to_email}: {reply_text}")
        return

    _ensure_configured()
    resend.Emails.send({
        "from": f"Morelike <{FROM_EMAIL}>",
        "to": [to_email],
        "subject": "Reply from Morelike — your feedback",
        "html": f"""
            <h2>Response to your feedback</h2>
            <p>Thanks for sharing your experience with Morelike. Here's our reply:</p>
            <blockquote style="background:#f5f5f5;padding:16px;border-left:4px solid #7c3aed;border-radius:4px;">
                {reply_text}
            </blockquote>
            <p>— The Morelike Team</p>
        """
    })
