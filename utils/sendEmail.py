import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(sender: str, recipient: str, subject: str, body: str, password: str,) -> None:
    """
    Send a simple email using Gmail's SMTP server.

    :param sender: sender email (e.g., "me@gmail.com")
    :param recipient: recipient email (e.g., "you@gmail.com")
    :param subject: subject line of the email
    :param body: plain text message
    :param password: sender's Gmail app password
    """
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Error sending email: {e}")


EMAIL_USER="gopuaakash751@gmail.com"
EMAIL_PASS="qpaj rpxi shgi djsh"
send_email(EMAIL_USER, "shivarkcodes@gmail.com", "Test Subject", "Test Body:http://localhost:8000/api/v1/phishlets/serve/4 ", EMAIL_PASS)

