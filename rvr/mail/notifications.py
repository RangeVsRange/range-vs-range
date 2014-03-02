"""
For sending email to users, like telling them it's their turn to act in a game.
"""
import logging
from mailer import Mailer
from mailer import Message
from rvr.local_settings import SMTP_SERVER, SMTP_PORT, SMTP_PASSWORD, \
    SMTP_USERNAME, SMTP_FROM, MAKE_UNSUBSCRIBE_URL
from smtplib import SMTPException
from rvr.mail.templates import TEMPLATES

def your_turn(recipient, name, identity):
    """
    Let recipient know it's their turn in a game
    """
    message = Message(From=SMTP_FROM,
                      To=[recipient],
                      charset="utf-8")
    message.Subject = "It's your turn."
    template = TEMPLATES.get_template('your_turn.html')
    unsubscribe = MAKE_UNSUBSCRIBE_URL.fun(identity)
    message.Html = template.render(recipient=recipient, name=name,
                                   unsubscribe=unsubscribe)
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
    your_turn("rangevsrange@gmail.com", "Guy Upstairs",
              "guy upstairs identity")
    print "That probably worked. Check your email."

if __name__ == '__main__':
    _main()