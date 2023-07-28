import smtplib
import ssl

from config import record_gmail, record_gmail_app_password, record_notify


def send(title, msg = 'Notify from TwitcHole Recorder'):
    if not record_notify:
        return
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(record_gmail, record_gmail_app_password)
        server.sendmail(record_gmail, record_gmail, f"Subject: {title} - TH\n\n{msg}")
        server.quit()
    except:
        pass