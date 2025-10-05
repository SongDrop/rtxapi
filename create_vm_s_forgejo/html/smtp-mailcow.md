Allowing Forgejo to send eMails via Mailcow
Since this is not the default setting in Forgejo, I would like to write down how I setup Forgejo to send eMails via Mailcow. This concept should probably also be true for any eMail server that uses STARTTLS (or, mostly equivalent, if you want to connect to port 587).

I have got a Configuration file at /etc/forgejo/app.ini, this might be somewhere else for you. In there, I have got the [mailer] section, which is the important one. For me, it looks like that:

[mailer]
ENABLED = true
FROM = Forgejo <noreply@tech-tales.blog>
PROTOCOL = smtp+starttls
SMTP_ADDR = mailer.tech-tales.blog
SMTP_PORT = 587
USER = noreply@tech-tales.blog
PASSWD = redacted

So the thing I did not expect here is the protocol to be smtp+starttls, I first assumed that this should just be smtp (which would be true on port 25) or smtps (which is used on port 465).

In the admin console of Forgejo in Configuration - Summary, you can send a test eMail to an eMail address of your choice.
