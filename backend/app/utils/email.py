def send_welcome_email_placeholder(user_email: str, employee_name: str):
    # Production integrations can plug in SES, SendGrid, Postmark, or SMTP here.
    return {'queued': False, 'to': user_email, 'subject': f'Welcome {employee_name}'}
