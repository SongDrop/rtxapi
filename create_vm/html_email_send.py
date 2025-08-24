import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import asyncio

async def send_html_email_smtp(smtp_host: str, smtp_port: int, smtp_user: str, smtp_password: str,
                              sender_email: str, recipient_emails: list, subject: str, 
                              html_content: str, use_tls: bool = True):
    """
    Send HTML email using SMTP (async version)
    """
    try:
        # Run the synchronous SMTP code in a thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, 
            lambda: _send_email_sync(
                smtp_host, smtp_port, smtp_user, smtp_password,
                sender_email, recipient_emails, subject, html_content, use_tls
            )
        )
        return True
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        raise e

def _send_email_sync(smtp_host: str, smtp_port: int, smtp_user: str, smtp_password: str,
                    sender_email: str, recipient_emails: list, subject: str, 
                    html_content: str, use_tls: bool = True):
    """
    Synchronous implementation of email sending
    """
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = ', '.join(recipient_emails)
    
    # Attach HTML content
    html_part = MIMEText(html_content, 'html')
    msg.attach(html_part)
    
    # Send email
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        if use_tls:
            server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(sender_email, recipient_emails, msg.as_string())