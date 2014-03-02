"""
For sending email to users, like telling them it's their turn to act in a game.
"""
import logging
from mailer import Mailer
from mailer import Message
from rvr.local_settings import SMTP_SERVER, SMTP_PORT, SMTP_PASSWORD, \
    SMTP_USERNAME, SMTP_FROM
from smtplib import SMTPException

def notify(recipient, unsubscribe):
    """
    Let recipient know it's their turn in a game
    """
    # TODO: use render_template
    # TODO: the unsubscribe link should use the identity as authentication
    message = Message(From=SMTP_FROM,
                      To=[recipient],
                      charset="utf-8")
    message.Subject = "It's your turn."
    message.Html = """It's your turn.
Click <a href="%s">here</a> to unsubscribe.
(You won't receive any move emails unless you log on again.)""" % (unsubscribe,)
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
    notify("rangevsrange@gmail.com", "http://unsubscribe.example.com/")
    print "That probably worked. Check your email."

if __name__ == '__main__':
    _main()