import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import ssl

def send_html_email_smtp(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    sender_email: str,
    recipient_emails: list,
    subject: str,
    html_content: str,
    use_tls: bool = True,
    use_ssl: bool = False
):
    """
    Send an HTML email via SMTP.

    Args:
        smtp_host (str): SMTP server hostname.
        smtp_port (int): SMTP port number.
        smtp_user (str): SMTP username for login.
        smtp_password (str): SMTP password for login.
        sender_email (str): Email address of the sender.
        recipient_emails (list): List of recipient email addresses.
        subject (str): Subject line of the email.
        html_content (str): HTML content of the email body.
        use_tls (bool): Whether to use TLS via starttls() (default True).
        use_ssl (bool): Whether to use implicit SSL connection (default False).
    """
    msg = MIMEMultipart('alternative')
    msg['From'] = sender_email
    msg['To'] = ", ".join(recipient_emails)
    msg['Subject'] = subject

    # Attach the HTML content
    msg.attach(MIMEText(html_content, 'html'))

    try:
        if use_ssl:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            if use_tls:
                server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(sender_email, recipient_emails, msg.as_string())
        server.quit()
        print_success("Notification email sent successfully.")
    except Exception as e:
        print_error(f"Failed to send email: {e}")

# Console colors for logs
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKORANGE = '\033[38;5;214m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

#####
def print_info(msg):
    print(f"{bcolors.OKBLUE}[INFO]{bcolors.ENDC} {msg}")

def print_build(msg):
    print(f"{bcolors.OKORANGE}[BUILD]{bcolors.ENDC} {msg}")

def print_success(msg):
    print(f"{bcolors.OKGREEN}[SUCCESS]{bcolors.ENDC} {msg}")

def print_warn(msg):
    print(f"{bcolors.WARNING}[WARNING]{bcolors.ENDC} {msg}")

def print_error(msg):
    print(f"{bcolors.FAIL}[ERROR]{bcolors.ENDC} {msg}")
