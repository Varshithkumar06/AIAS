"""
AIAS Email Service
Sends OTP verification emails via Gmail SMTP over TLS.
Uses HTML templates for professional email appearance.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from config import Config


class EmailService:
    """Handles sending verification emails via Gmail SMTP."""

    @staticmethod
    def send_otp_email(recipient_email, otp_code, recipient_name=""):
        """
        Send a professional HTML verification email containing the OTP.

        Args:
            recipient_email: The email address to send to
            otp_code: The 6-digit OTP code (plaintext, for email body only)
            recipient_name: Optional display name for personalization

        Returns:
            dict with keys:
                - success (bool): Whether email was sent
                - error (str|None): Error message if failed
        """
        if not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
            return {
                "success": False,
                "error": "Email service not configured. Please set MAIL_USERNAME and MAIL_PASSWORD in .env",
            }

        # Build the HTML email
        html_body = EmailService._build_otp_email_html(recipient_email, otp_code, recipient_name)

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"AIAS Verification Code: {otp_code}"
        msg["From"] = f"{Config.MAIL_SENDER_NAME} <{Config.MAIL_USERNAME}>"
        msg["To"] = recipient_email

        # Plain text fallback
        plain_text = (
            f"Your AIAS verification code is: {otp_code}\n\n"
            f"This code expires in {Config.OTP_EXPIRY_MINUTES} minutes.\n"
            f"If you didn't request this code, please ignore this email.\n"
        )

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            # Connect via TLS
            context = ssl.create_default_context()
            with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                server.sendmail(Config.MAIL_USERNAME, recipient_email, msg.as_string())

            return {"success": True, "error": None}

        except smtplib.SMTPAuthenticationError:
            return {
                "success": False,
                "error": "Email authentication failed. Check your Gmail App Password in .env",
            }
        except smtplib.SMTPException as e:
            return {"success": False, "error": f"Failed to send email: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Email service error: {str(e)}"}

    @staticmethod
    def _build_otp_email_html(recipient_email, otp_code, recipient_name=""):
        """Build the professional HTML email template matching Google style."""
        greeting = f"Dear {recipient_name}," if recipient_name else "Dear AIAS User,"

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 20px; font-family: Arial, sans-serif; background-color: #f9f9f9;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); overflow: hidden;">

        <!-- Logo Header -->
        <div style="padding: 32px 32px 8px 32px;">
            <span style="font-size: 24px; font-family: Georgia, 'Times New Roman', serif; color: #222222;">AIAS</span>
            <span style="font-size: 24px; font-family: Georgia, 'Times New Roman', serif; color: #c4a137;">Platform</span>
        </div>

        <!-- Title Header (No Blue Box) -->
        <div style="padding: 16px 32px; border-bottom: 1px solid #f0f0f0;">
            <h1 style="color: #222222; margin: 0; font-size: 24px; font-weight: 400;">Verification Code</h1>
        </div>

        <!-- Body Content -->
        <div style="padding: 32px;">
            <p style="font-size: 16px; color: #3c4043; margin-top: 0;">{greeting}</p>

            <p style="font-size: 16px; color: #3c4043; line-height: 1.5;">
                We received a request to access your AIAS Account <a href="mailto:{recipient_email}" style="color: #1a73e8; text-decoration: none;">{recipient_email}</a> through your email address. Your AIAS verification code is:
            </p>

            <h2 style="font-size: 36px; font-weight: 700; color: #202124; text-align: center; margin: 40px 0;">
                {otp_code}
            </h2>

            <p style="font-size: 14px; color: #3c4043; line-height: 1.5;">
                If you did not request this code, it is possible that someone else is trying to access the AIAS Account <a href="mailto:{recipient_email}" style="color: #1a73e8; text-decoration: none;">{recipient_email}</a>. <strong>Do not forward or give this code to anyone.</strong>
            </p>

            <p style="font-size: 14px; color: #3c4043; line-height: 1.5;">
                You received this message because this email address is listed as the recovery email for the AIAS Account <a href="mailto:{recipient_email}" style="color: #1a73e8; text-decoration: none;">{recipient_email}</a>.
            </p>

            <p style="font-size: 14px; color: #3c4043; line-height: 1.5; margin-bottom: 0;">
                Sincerely yours,<br><br>
                The AIAS Accounts team
            </p>
        </div>
    </div>
</body>
</html>
"""

    @staticmethod
    def send_welcome_email(recipient_email, recipient_name=""):
        """
        Send a welcome email to newly registered users.

        Args:
            recipient_email: The email address to send to
            recipient_name: Optional display name for personalization

        Returns:
            dict with keys:
                - success (bool): Whether email was sent
                - error (str|None): Error message if failed
        """
        if not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
            return {
                "success": False,
                "error": "Email service not configured.",
            }

        html_body = EmailService._build_welcome_email_html(recipient_email, recipient_name)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Welcome to AIAS, {recipient_name or 'there'}!"
        msg["From"] = f"{Config.MAIL_SENDER_NAME} <{Config.MAIL_USERNAME}>"
        msg["To"] = recipient_email

        plain_text = (
            f"Welcome to AIAS, {recipient_name or 'there'}!\n\n"
            f"Thank you for creating an account with AIAS.\n"
            f"We're building the future of intelligent business automation — and you're part of it.\n\n"
            f"— The AIAS Team\n"
        )

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                server.sendmail(Config.MAIL_USERNAME, recipient_email, msg.as_string())

            return {"success": True, "error": None}

        except Exception as e:
            return {"success": False, "error": f"Welcome email error: {str(e)}"}

    @staticmethod
    def _build_welcome_email_html(recipient_email, recipient_name=""):
        """Build the welcome email HTML template matching the AIAS design."""
        greeting = f"Hi {recipient_name}," if recipient_name else "Hi there,"

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 20px; font-family: Arial, sans-serif; background-color: #f9f9f9;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); overflow: hidden;">

        <!-- Logo Header -->
        <div style="padding: 32px 32px 8px 32px;">
            <span style="font-size: 24px; font-family: Georgia, 'Times New Roman', serif; color: #222222;">AIAS</span>
            <span style="font-size: 24px; font-family: Georgia, 'Times New Roman', serif; color: #c4a137;">Platform</span>
        </div>

        <!-- Title -->
        <div style="padding: 16px 32px; border-bottom: 1px solid #f0f0f0;">
            <h1 style="color: #222222; margin: 0; font-size: 24px; font-weight: 400;">Welcome to AIAS</h1>
        </div>

        <!-- Body Content -->
        <div style="padding: 32px;">
            <p style="font-size: 16px; color: #3c4043; margin-top: 0;">{greeting}</p>

            <p style="font-size: 16px; color: #3c4043; line-height: 1.6;">
                Thank you for creating an account with AIAS. Your account is now active and ready to automate your workflows.
            </p>

            <!-- Highlight Box -->
            <div style="background-color: #fdf8ef; border-left: 4px solid #c4a137; padding: 20px 24px; margin: 28px 0; border-radius: 0 8px 8px 0;">
                <p style="font-size: 15px; color: #222222; margin: 0; font-weight: 600; line-height: 1.5;">
                    At AIAS, we're building the future of intelligent business automation.
                </p>
                <p style="font-size: 14px; color: #555555; margin: 10px 0 0 0; line-height: 1.5;">
                    From AI-powered workflows to real-time decision making — you now have access to enterprise-grade tools designed to help your business move faster and smarter.
                </p>
            </div>

            <p style="font-size: 15px; color: #3c4043; line-height: 1.6;">
                Here's what you can do today:
            </p>

            <!-- Feature List -->
            <table style="width: 100%; margin: 16px 0 28px 0; border-collapse: collapse;">
                <tr>
                    <td style="padding: 10px 12px 10px 0; vertical-align: top; width: 28px;">
                        <span style="color: #c4a137; font-size: 18px; font-weight: 700;">&#10003;</span>
                    </td>
                    <td style="padding: 10px 0; font-size: 14px; color: #3c4043; line-height: 1.5;">
                        <strong>Automate Workflows</strong> — Set up intelligent automation pipelines in minutes.
                    </td>
                </tr>
                <tr>
                    <td style="padding: 10px 12px 10px 0; vertical-align: top; width: 28px;">
                        <span style="color: #c4a137; font-size: 18px; font-weight: 700;">&#10003;</span>
                    </td>
                    <td style="padding: 10px 0; font-size: 14px; color: #3c4043; line-height: 1.5;">
                        <strong>AI-Powered Insights</strong> — Get real-time analytics and predictive intelligence.
                    </td>
                </tr>
                <tr>
                    <td style="padding: 10px 12px 10px 0; vertical-align: top; width: 28px;">
                        <span style="color: #c4a137; font-size: 18px; font-weight: 700;">&#10003;</span>
                    </td>
                    <td style="padding: 10px 0; font-size: 14px; color: #3c4043; line-height: 1.5;">
                        <strong>Scale with Confidence</strong> — Enterprise-grade security and infrastructure that grows with you.
                    </td>
                </tr>
            </table>

            <p style="font-size: 14px; color: #3c4043; line-height: 1.5;">
                You're now part of a growing community of businesses that are choosing intelligence over complexity. We're excited to have you on this journey.
            </p>

            <p style="font-size: 14px; color: #3c4043; line-height: 1.5; margin-bottom: 0;">
                Welcome aboard,<br><br>
                <strong>The AIAS Team</strong><br>
                <span style="font-size: 13px; color: #888888; font-style: italic;">Building the future of intelligent business.</span>
            </p>
        </div>

        <!-- Footer -->
        <div style="padding: 20px 32px; background-color: #fafafa; border-top: 1px solid #f0f0f0; text-align: center;">
            <p style="font-size: 12px; color: #999999; margin: 0; line-height: 1.5;">
                This email was sent to <a href="mailto:{recipient_email}" style="color: #c4a137; text-decoration: none;">{recipient_email}</a> because you created an AIAS account.
            </p>
        </div>
    </div>
</body>
</html>
"""

    @staticmethod
    def send_booking_notification(name="N/A", email="N/A", whatsapp="", service_needed="N/A",
                                  budget_range="N/A", timeline="N/A", problem_statement="",
                                  call_type="Voice Call", zoom_meeting_link="", timestamp="",
                                  scheduled_at=None):
        """
        Sends a single professional booking email to both the team and the client.
        """
        if not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
            return {"success": False, "error": "Email service not configured."}

        TEAM_EMAIL = "aiasprivateltd@gmail.com"

        # Build recipients list
        recipients = [TEAM_EMAIL]
        if email and email != "N/A" and "@" in email:
            recipients.append(email.strip())

        # Format scheduled time nicely
        formatted_time = ""
        if scheduled_at:
            if isinstance(scheduled_at, datetime):
                formatted_time = scheduled_at.strftime('%A, %B %d, %Y at %I:%M %p (IST)')
            else:
                formatted_time = str(scheduled_at)

        # Construct details table rows
        rows_client = [
            ("Name", name, True),
            ("Email", email, False),
            ("WhatsApp", whatsapp or "Not provided", True),
            ("Service Needed", service_needed, False),
            ("Budget Range", budget_range, True),
            ("Timeline", timeline, False),
            ("Call Type", call_type, True),
        ]
        if formatted_time:
            rows_client.append(("Scheduled Time", formatted_time, False))

        if call_type == "Video Conference":
            rows_client.append((
                "Zoom Join Link",
                f'<a href="{zoom_meeting_link}" style="color:#1a73e8;text-decoration:none;word-break:break-all;">{zoom_meeting_link}</a>' if zoom_meeting_link else "Will be sent via email shortly",
                len(rows_client) % 2 == 1
            ))

        table_rows_client = ""
        for label, value, shaded in rows_client:
            bg = ' style="background:#fdf8ef;"' if shaded else ""
            table_rows_client += f"""
        <tr{bg}>
          <td class="label-cell" style="padding:12px 16px;font-size:13px;color:#888;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;width:180px;border-bottom:1px solid #f0f0f0;">{label}</td>
          <td class="value-cell" style="padding:12px 16px;font-size:15px;color:#1a1a1a;border-bottom:1px solid #f0f0f0;">{value}</td>
        </tr>"""

        # Zoom meeting alert box
        zoom_instructions = ""
        if call_type == "Video Conference":
            if zoom_meeting_link:
                time_str = f" scheduled for <strong>{formatted_time}</strong>" if formatted_time else " scheduled in 72 hours"
                zoom_instructions = f"""
          <div class="alert-box" style="background-color: #fdf8ef; border-left: 4px solid #c4a137; padding: 20px 24px; margin: 28px 0; border-radius: 0 8px 8px 0;">
            <p style="font-size: 15px; color: #222222; margin: 0; font-weight: 600; line-height: 1.5;">
              🎥 Your Zoom Link is Ready
            </p>
            <p style="font-size: 14px; color: #555555; margin: 10px 0 0 0; line-height: 1.5;">
              Click the link below to join the video conference{time_str}:<br>
              <a href="{zoom_meeting_link}" style="display:inline-block; margin-top:10px; background:#c4a137; color:#fff; text-decoration:none; padding:10px 18px; border-radius:4px; font-weight:bold; font-size:13px;">Join Zoom Meeting</a>
            </p>
          </div>
                """
            else:
                time_str = f" scheduled for <strong>{formatted_time}</strong>" if formatted_time else ""
                zoom_instructions = f"""
          <div class="alert-box" style="background-color: #fdf8ef; border-left: 4px solid #c4a137; padding: 20px 24px; margin: 28px 0; border-radius: 0 8px 8px 0;">
            <p style="font-size: 15px; color: #222222; margin: 0; font-weight: 600; line-height: 1.5;">
              🎥 Video Meeting Link Pending
            </p>
            <p style="font-size: 14px; color: #555555; margin: 10px 0 0 0; line-height: 1.5;">
              Our team is scheduling your discovery video call{time_str}. We will send you the calendar invite with your unique Zoom meeting link via email shortly.
            </p>
          </div>
                """
        else:
            time_str = f" at <strong>{formatted_time}</strong>" if formatted_time else ""
            zoom_instructions = f"""
          <div class="alert-box" style="background-color: #fdf8ef; border-left: 4px solid #c4a137; padding: 20px 24px; margin: 28px 0; border-radius: 0 8px 8px 0;">
            <p style="font-size: 15px; color: #222222; margin: 0; font-weight: 600; line-height: 1.5;">
              📞 Voice Discovery Call
            </p>
            <p style="font-size: 14px; color: #555555; margin: 10px 0 0 0; line-height: 1.5;">
              Our tech leads will call you{time_str} at your provided contact details (WhatsApp: {whatsapp or 'N/A'}, Email: {email}).
            </p>
          </div>
            """

        # Admin instruction banner (at bottom)
        admin_banner = f"""
    <!-- Admin Team Notice -->
    <div class="admin-notice" style="padding: 20px 32px; background-color: #fafafa; border-top: 1px solid #f0f0f0;">
      <p style="font-size: 12px; color: #888888; margin: 0; line-height: 1.5;">
        <strong>Notice for AIAS Team:</strong> A new lead has booked a call. Please contact this lead (Reply-to: {email} / WhatsApp: {whatsapp or 'N/A'}).
        {f'Scheduled time: {formatted_time}. ' if formatted_time else ''}
        {'' if call_type != 'Video Conference' else ('Zoom Link: ' + zoom_meeting_link if zoom_meeting_link else '⚠️ Zoom link pending setup. Please schedule the meeting via Admin Panel to create the Zoom link.')}
      </p>
    </div>
        """

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    @media only screen and (max-width: 480px) {{
      body {{
        padding: 10px !important;
      }}
      .email-card {{
        border-radius: 6px !important;
      }}
      .email-header {{
        padding: 24px 20px 8px 20px !important;
      }}
      .email-title {{
        padding: 12px 20px !important;
      }}
      .email-title h1 {{
        font-size: 20px !important;
      }}
      .email-body {{
        padding: 20px !important;
      }}
      /* Stack table cells on mobile */
      .info-table tr {{
        display: block !important;
        width: 100% !important;
        border-bottom: 1px solid #f0f0f0 !important;
        padding: 10px 0 !important;
        background: none !important;
      }}
      .info-table td {{
        display: block !important;
        width: 100% !important;
        box-sizing: border-box !important;
        padding: 4px 0 !important;
        border: none !important;
      }}
      .info-table td.label-cell {{
        width: 100% !important;
        font-size: 11px !important;
        color: #888888 !important;
        padding-bottom: 2px !important;
      }}
      .info-table td.value-cell {{
        width: 100% !important;
        font-size: 14px !important;
        color: #111111 !important;
      }}
      /* Make alert boxes responsive */
      .alert-box {{
        padding: 16px 16px !important;
        margin: 20px 0 !important;
        border-radius: 6px !important;
      }}
      /* Admin notice */
      .admin-notice {{
        padding: 16px 20px !important;
      }}
    }}
  </style>
</head>
<body style="margin:0;padding:20px;font-family:Arial,sans-serif;background-color:#f9f9f9;">
  <div class="email-card" style="max-width:600px;margin:0 auto;background-color:#ffffff;border:1px solid #e0e0e0;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.05);overflow:hidden;">
    <div class="email-header" style="padding:32px 32px 8px 32px;">
      <span style="font-size:24px;font-family:Georgia,serif;color:#222;">AIAS</span>
      <span style="font-size:24px;font-family:Georgia,serif;color:#c4a137;">Platform</span>
    </div>
    <div class="email-title" style="padding:16px 32px;border-bottom:1px solid #f0f0f0;">
      <h1 style="color:#222;margin:0;font-size:24px;font-weight:400;">Booking Confirmed</h1>
    </div>
    <div class="email-body" style="padding:32px;">
      <p style="font-size:16px;color:#3c4043;margin-top:0;">Hi {name.split(' ')[0]},</p>
      <p style="font-size:16px;color:#3c4043;line-height:1.6;">
        Thank you for booking a session with us! We have received your project details and are preparing the right solution for you. Here is a summary of what you shared:
      </p>
      <table class="info-table" style="width:100%;border-collapse:collapse;margin:24px 0;">
        {table_rows_client}
      </table>
      {zoom_instructions}
      <p style="font-size:15px;color:#3c4043;line-height:1.6;font-weight:600;">Here is what happens next:</p>
      <table style="width:100%;margin:16px 0;border-collapse:collapse;">
        <tr>
          <td style="padding:8px 12px 8px 0;vertical-align:top;width:24px;color:#c4a137;font-size:16px;font-weight:bold;">1.</td>
          <td style="padding:8px 0;font-size:14px;color:#3c4043;line-height:1.5;">
            <strong>Check Your Calendar</strong> — You will receive an invitation to block the slot.
          </td>
        </tr>
        <tr>
          <td style="padding:8px 12px 8px 0;vertical-align:top;width:24px;color:#c4a137;font-size:16px;font-weight:bold;">2.</td>
          <td style="padding:8px 0;font-size:14px;color:#3c4043;line-height:1.5;">
            <strong>Reviewing Requirements</strong> — Our engineering team will study your scope so we can provide instant value.
          </td>
        </tr>
        <tr>
          <td style="padding:8px 12px 8px 0;vertical-align:top;width:24px;color:#c4a137;font-size:16px;font-weight:bold;">3.</td>
          <td style="padding:8px 0;font-size:14px;color:#3c4043;line-height:1.5;">
            <strong>Discovery Session</strong> — We will discuss solutions and map out the tech architecture. No hard sales pitch, promise!
          </td>
        </tr>
      </table>
      <p style="font-size:14px;color:#3c4043;line-height:1.5;margin-top:28px;">
        Sincerely,<br><br>
        <strong>The AIAS Team</strong><br>
        <span style="font-size:13px;color:#888888;font-style:italic;">Building the future of intelligent business.</span>
      </p>
    </div>
    {admin_banner}
  </div>
</body>
</html>
"""

        plain = (
            f"Booking Confirmed — AIAS Platform\n\n"
            f"Hi {name},\n\n"
            f"We've received your request! Here is a recap:\n"
            f"Service Needed : {service_needed}\n"
            f"Budget Range   : {budget_range}\n"
            f"Timeline       : {timeline}\n"
            f"Call Type      : {call_type}\n"
            f"{f'Scheduled Time : {formatted_time}' if formatted_time else ''}\n"
            f"{f'Zoom Meeting   : {zoom_meeting_link}' if zoom_meeting_link else ('Zoom Meeting   : Will be sent via email shortly' if call_type == 'Video Conference' else '')}\n\n"
            f"We look forward to speaking with you.\n\n"
            f"— The AIAS Team\n\n"
            f"Notice for AIAS Team: Contact lead."
        )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📅 Booking Confirmed: {name} — {service_needed}"
        msg["From"] = f"{Config.MAIL_SENDER_NAME} <{Config.MAIL_USERNAME}>"
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Deliver
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                server.sendmail(Config.MAIL_USERNAME, recipients, msg.as_string())
            return {"success": True, "error": None}
        except Exception as e:
            return {"success": False, "error": str(e)}
