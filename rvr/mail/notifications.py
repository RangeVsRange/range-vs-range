"""
For sending email to users, like telling them it's their turn to act in a game.
"""
import logging
from mailer import Mailer
from mailer import Message
from rvr.local_settings import SMTP_SERVER, SMTP_PORT, SMTP_PASSWORD, \
    SMTP_USERNAME, SMTP_FROM
from smtplib import SMTPException

def notify(recipient):
    """
    Let recipient know it's their turn in a game
    """
    message = Message(From=SMTP_FROM,
                      To=[recipient],
                      charset="utf-8")
    message.Subject = "It's your turn."
    message.Body = "It's your turn."
    sender = Mailer(host=SMTP_SERVER, port=SMTP_PORT, use_tls=True)
    sender.login(SMTP_USERNAME, SMTP_PASSWORD)
    try:
        sender.send(message)
    except SMTPException as err:
        logging.warning("notification failed. address: '%s'. error: %r",
                        recipient, err)

def _main():
    """
    Send a test email
    """
    notify("rangevsrange@gmail.com")

if __name__ == '__main__':
    _main()