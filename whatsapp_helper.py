"""
WhatsApp Notification Helper
Sends WhatsApp messages via various providers (Meta Cloud API, Twilio, Gupshup, etc.)

This module provides a unified interface for sending WhatsApp messages 
regardless of the underlying provider being used.
"""

import os
import logging
import requests
from typing import List, Tuple, Optional, Dict, Any
from threading import Thread
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add console handler if not present
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[WHATSAPP %(levelname)s] %(asctime)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


class WhatsAppSender:
    """Unified WhatsApp message sender supporting multiple providers"""
    
    def __init__(self, settings):
        """
        Initialize with WhatsAppSettings object from database
        
        Args:
            settings: WhatsAppSettings model instance
        """
        self.settings = settings
        self.provider = settings.provider.value if settings.provider else None
        self.api_key = settings.api_key
        self.api_secret = settings.api_secret
        self.access_token = settings.access_token
        self.phone_number_id = settings.phone_number_id
        self.business_account_id = settings.business_account_id
        self.sandbox_mode = settings.sandbox_mode
        self.default_template_name = settings.default_template_name
        self.default_template_language = settings.default_template_language or 'en'
    
    def send_message(self, to_phone: str, message: str, template_name: str = None, 
                     template_params: List[str] = None, media_urls: List[str] = None,
                     media_files: List[str] = None) -> Dict[str, Any]:
        """
        Send a WhatsApp message
        
        Args:
            to_phone: Recipient phone number (with country code, e.g., +91xxxxxxxxxx)
            message: Message text (for text messages)
            template_name: Optional template name (for template messages)
            template_params: Optional list of template parameters
            media_urls: Optional list of media URLs (for attachments)
            
        Returns:
            dict with 'success', 'message_id', 'error' keys
        """
        # Normalize phone number (remove spaces, dashes, etc.)
        to_phone = self._normalize_phone(to_phone)
        
        if not to_phone:
            return {'success': False, 'message_id': None, 'error': 'Invalid phone number'}
        
        if self.provider == 'Meta Cloud API':
            return self._send_via_meta(to_phone, message, template_name, template_params, media_files=media_files, media_urls=media_urls)
        elif self.provider == 'Twilio':
            return self._send_via_twilio(to_phone, message, media_urls)
        elif self.provider == 'Gupshup':
            return self._send_via_gupshup(to_phone, message)
        elif self.provider == 'WATI':
            return self._send_via_wati(to_phone, message, template_name, template_params)
        elif self.provider == 'Interakt':
            return self._send_via_interakt(to_phone, message, template_name, template_params)
        elif self.provider == 'AiSensy':
            return self._send_via_aisensy(to_phone, message, template_name, template_params)
        else:
            return {'success': False, 'message_id': None, 'error': f'Unsupported provider: {self.provider}'}
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to international format"""
        if not phone:
            return ''
        
        # Remove all non-digit characters except +
        phone = ''.join(c for c in phone if c.isdigit() or c == '+')
        
        # Ensure it starts with +
        if not phone.startswith('+'):
            # Assume Indian number if 10 digits
            if len(phone) == 10:
                phone = '+91' + phone
            elif not phone.startswith('91') and len(phone) == 12:
                phone = '+' + phone
            else:
                phone = '+' + phone
        
        return phone
    
    def _send_via_meta(self, to_phone: str, message: str, template_name: str = None,
                       template_params: List[str] = None, media_files: List[str] = None, media_urls: List[str] = None) -> Dict[str, Any]:
        """Send message via Meta Cloud API (Official WhatsApp Business API)"""
        try:
            url = f'https://graph.facebook.com/v18.0/{self.phone_number_id}/messages'
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Remove + from phone for Meta API
            to_phone_clean = to_phone.lstrip('+')
            
            if template_name:
                # Template message
                payload = {
                    'messaging_product': 'whatsapp',
                    'to': to_phone_clean,
                    'type': 'template',
                    'template': {
                        'name': template_name,
                        'language': {'code': self.default_template_language}
                    }
                }
                
                # Add template parameters if provided
                if template_params:
                    payload['template']['components'] = [{
                        'type': 'body',
                        'parameters': [{'type': 'text', 'text': p} for p in template_params]
                    }]
            else:
                # Text message (only works within 24-hour window)
                payload = {
                    'messaging_product': 'whatsapp',
                    'recipient_type': 'individual',
                    'to': to_phone_clean,
                    'type': 'text',
                    'text': {'body': message}
                }

            # If media_files are provided, upload them first and reference the
            # returned media IDs in the send request. Meta supports uploading
            # media to /{phone_number_id}/media (multipart/form-data), then
            # using the returned media id in the message body.
            if media_files:
                media_ids = []
                for path in media_files[:10]:
                    if not path or not os.path.exists(path):
                        logger.warning(f"[Meta API] Skipping non-existent media file: {path}")
                        continue
                    upload_url = f'https://graph.facebook.com/v18.0/{self.phone_number_id}/media'
                    files = {'file': open(path, 'rb')}
                    data = {'messaging_product': 'whatsapp'}
                    # Upload file
                    logger.info(f"[Meta API] Uploading media: {path}")
                    try:
                        r = requests.post(upload_url, headers={'Authorization': f'Bearer {self.access_token}'}, files=files, data=data, timeout=120)
                    finally:
                        try:
                            files['file'].close()
                        except Exception:
                            pass

                    if r is None or r.status_code not in [200, 201]:
                        logger.error(f"[Meta API] Media upload failed for {path}: {getattr(r, 'text', 'no response')}")
                        continue
                    mid = r.json().get('id')
                    if mid:
                        media_ids.append(mid)

                if media_ids:
                    # Send first media with body as document (or appropriate type)
                    first_mid = media_ids[0]
                    send_payload = {
                        'messaging_product': 'whatsapp',
                        'to': to_phone_clean,
                        'type': 'document',
                        'document': {'id': first_mid, 'filename': os.path.basename(media_files[0])}
                    }
                    logger.info(f"[Meta API] Sending document message to {to_phone}")
                    response = requests.post(url, headers=headers, json=send_payload, timeout=30)

                    if response.status_code in [200, 201]:
                        data = response.json()
                        message_id = data.get('messages', [{}])[0].get('id')
                        logger.info(f"[Meta API] Message sent successfully. ID: {message_id}")
                        # Send remaining media as separate messages
                        for extra_idx, mid in enumerate(media_ids[1:], start=1):
                            extra_payload = {
                                'messaging_product': 'whatsapp',
                                'to': to_phone_clean,
                                'type': 'document',
                                'document': {'id': mid, 'filename': os.path.basename(media_files[extra_idx])}
                            }
                            try:
                                er = requests.post(url, headers=headers, json=extra_payload, timeout=30)
                                if er is None or er.status_code not in [200, 201]:
                                    logger.error(f"[Meta API] Error sending extra media: {getattr(er, 'text', 'no response')}")
                                else:
                                    logger.info(f"[Meta API] Extra media sent: {media_files[extra_idx]}")
                            except Exception as e:
                                logger.error(f"[Meta API] Exception sending extra media: {e}")

                        return {'success': True, 'message_id': message_id, 'error': None}
                    else:
                        error = response.json().get('error', {}).get('message', response.text)
                        logger.error(f"[Meta API] Error: {error}")
                        return {'success': False, 'message_id': None, 'error': error}

            # If no media_files, but media_urls provided, attempt to send by url (not all flows support)
            if media_urls:
                # Meta does not accept external MediaUrl for document in the same way; prefer upload.
                # As a fallback, try to reference external link in the text body or skip.
                logger.info(f"[Meta API] Media URLs provided; prefer uploading files. URLs: {media_urls}")

            logger.info(f"[Meta API] Sending to {to_phone}")
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code in [200, 201]:
                data = response.json()
                message_id = data.get('messages', [{}])[0].get('id')
                logger.info(f"[Meta API] Message sent successfully. ID: {message_id}")
                return {'success': True, 'message_id': message_id, 'error': None}
            else:
                error = response.json().get('error', {}).get('message', response.text)
                logger.error(f"[Meta API] Error: {error}")
                return {'success': False, 'message_id': None, 'error': error}
                
        except Exception as e:
            logger.error(f"[Meta API] Exception: {e}")
            return {'success': False, 'message_id': None, 'error': str(e)}
    
    def _send_via_twilio(self, to_phone: str, message: str, media_urls: List[str] = None) -> Dict[str, Any]:
        """Send message via Twilio with optional media attachments"""
        try:
            # Twilio WhatsApp endpoint
            account_sid = self.api_key
            auth_token = self.api_secret
            
            # Ensure phone number has + prefix for Twilio
            from_phone = self.phone_number_id
            if not from_phone.startswith('+'):
                from_phone = '+' + from_phone
            
            from_number = f'whatsapp:{from_phone}'
            to_number = f'whatsapp:{to_phone}'
            
            url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'
            
            # Prepare payload. Use a list of tuples so we can repeat 'MediaUrl' keys
            # (requests accepts list-of-tuples for repeated form fields).
            data = [
                ('From', from_number),
                ('To', to_number),
                ('Body', message or '')
            ]

            valid_media = []
            if media_urls:
                # Twilio requires publicly accessible http(s) URLs. Validate simple cases.
                for u in media_urls[:10]:
                    if not u:
                        continue
                    if not (u.startswith('http://') or u.startswith('https://')):
                        logger.warning(f"[Twilio] Skipping non-http media URL: {u}")
                        continue
                    valid_media.append(u)

                # Show which media URLs will be sent so Twilio can download them
                if valid_media:
                    logger.info(f"[Twilio] Media URLs to send: {valid_media}")
                    # Also print to console for immediate visibility during runs
                    print(f"[TWILIO-MEDIA-URLS] {valid_media}", flush=True)
                else:
                    logger.info("[Twilio] No valid media URLs to send")

                for m in valid_media:
                    data.append(('MediaUrl', m))

                logger.info(f"[Twilio] Attaching {len(valid_media)} media file(s)")

            logger.info(f"[Twilio] Sending from {from_number} to {to_number}")
            logger.info(f"[Twilio] POST URL: {url}")
            print(f"[TWILIO-POST-URL] {url}", flush=True)
            logger.info(f"[Twilio] Account SID: {account_sid[:10]}...")
            response = requests.post(url, auth=(account_sid, auth_token), data=data, timeout=30)
            
            if response.status_code in [200, 201]:
                data = response.json()
                message_id = data.get('sid')
                logger.info(f"[Twilio] Message sent. SID: {message_id}")
                return {'success': True, 'message_id': message_id, 'error': None}
            else:
                error = response.json().get('message', response.text)
                logger.error(f"[Twilio] Error: {error}")
                logger.error(f"[Twilio] Response: {response.text}")
                return {'success': False, 'message_id': None, 'error': error}
                
        except Exception as e:
            logger.error(f"[Twilio] Exception: {e}")
            return {'success': False, 'message_id': None, 'error': str(e)}
    
    def _send_via_gupshup(self, to_phone: str, message: str) -> Dict[str, Any]:
        """Send message via Gupshup"""
        try:
            url = 'https://api.gupshup.io/sm/api/v1/msg'
            headers = {
                'apikey': self.api_key,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Remove + from phone
            to_phone_clean = to_phone.lstrip('+')
            
            payload = {
                'channel': 'whatsapp',
                'source': self.phone_number_id,
                'destination': to_phone_clean,
                'src.name': self.business_account_id or 'School',
                'message': message
            }
            
            logger.info(f"[Gupshup] Sending to {to_phone}")
            response = requests.post(url, headers=headers, data=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'submitted':
                    message_id = data.get('messageId')
                    logger.info(f"[Gupshup] Message submitted. ID: {message_id}")
                    return {'success': True, 'message_id': message_id, 'error': None}
                else:
                    error = data.get('message', 'Unknown error')
                    return {'success': False, 'message_id': None, 'error': error}
            else:
                return {'success': False, 'message_id': None, 'error': response.text}
                
        except Exception as e:
            logger.error(f"[Gupshup] Exception: {e}")
            return {'success': False, 'message_id': None, 'error': str(e)}
    
    def _send_via_wati(self, to_phone: str, message: str, template_name: str = None,
                       template_params: List[str] = None) -> Dict[str, Any]:
        """Send message via WATI"""
        try:
            # WATI uses template-based sending
            base_url = self.business_account_id or 'https://live-server-xxxxx.wati.io'
            
            # Remove + from phone
            to_phone_clean = to_phone.lstrip('+')
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            if template_name:
                url = f'{base_url}/api/v1/sendTemplateMessage'
                payload = {
                    'whatsappNumber': to_phone_clean,
                    'templateName': template_name,
                    'broadcast_name': 'notification',
                    'parameters': [{'name': f'param{i+1}', 'value': p} for i, p in enumerate(template_params or [])]
                }
            else:
                url = f'{base_url}/api/v1/sendSessionMessage/{to_phone_clean}'
                payload = {'messageText': message}
            
            logger.info(f"[WATI] Sending to {to_phone}")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('result'):
                    return {'success': True, 'message_id': data.get('id'), 'error': None}
                else:
                    return {'success': False, 'message_id': None, 'error': data.get('info', 'Unknown error')}
            else:
                return {'success': False, 'message_id': None, 'error': response.text}
                
        except Exception as e:
            logger.error(f"[WATI] Exception: {e}")
            return {'success': False, 'message_id': None, 'error': str(e)}
    
    def _send_via_interakt(self, to_phone: str, message: str, template_name: str = None,
                           template_params: List[str] = None) -> Dict[str, Any]:
        """Send message via Interakt"""
        try:
            url = 'https://api.interakt.ai/v1/public/message/'
            headers = {
                'Authorization': f'Basic {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            # Remove + from phone
            to_phone_clean = to_phone.lstrip('+')
            
            payload = {
                'countryCode': to_phone_clean[:2],
                'phoneNumber': to_phone_clean[2:],
                'type': 'Template',
                'template': {
                    'name': template_name or self.default_template_name,
                    'languageCode': self.default_template_language,
                    'bodyValues': template_params or [message]
                }
            }
            
            logger.info(f"[Interakt] Sending to {to_phone}")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {'success': True, 'message_id': data.get('id'), 'error': None}
            else:
                return {'success': False, 'message_id': None, 'error': response.text}
                
        except Exception as e:
            logger.error(f"[Interakt] Exception: {e}")
            return {'success': False, 'message_id': None, 'error': str(e)}
    
    def _send_via_aisensy(self, to_phone: str, message: str, template_name: str = None,
                          template_params: List[str] = None) -> Dict[str, Any]:
        """Send message via AiSensy"""
        try:
            url = 'https://backend.aisensy.com/campaign/t1/api/v2'
            headers = {
                'Content-Type': 'application/json'
            }
            
            # Remove + from phone
            to_phone_clean = to_phone.lstrip('+')
            
            payload = {
                'apiKey': self.api_key,
                'campaignName': 'notification',
                'destination': to_phone_clean,
                'userName': 'School',
                'templateParams': template_params or [message],
                'source': 'notification_system',
                'media': {},
                'buttons': [],
                'carouselCards': [],
                'location': {}
            }
            
            logger.info(f"[AiSensy] Sending to {to_phone}")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return {'success': True, 'message_id': data.get('data', {}).get('messageId'), 'error': None}
                else:
                    return {'success': False, 'message_id': None, 'error': data.get('message', 'Unknown error')}
            else:
                return {'success': False, 'message_id': None, 'error': response.text}
                
        except Exception as e:
            logger.error(f"[AiSensy] Exception: {e}")
            return {'success': False, 'message_id': None, 'error': str(e)}


def get_whatsapp_settings(tenant_id: int):
    """Get WhatsApp settings for a tenant"""
    from db_single import get_session
    from notification_models import WhatsAppSettings
    
    session = get_session()
    try:
        settings = session.query(WhatsAppSettings).filter_by(
            tenant_id=tenant_id,
            is_enabled=True
        ).first()
        return settings
    finally:
        session.close()


def is_whatsapp_configured(tenant_id: int) -> bool:
    """Check if WhatsApp is configured for a tenant"""
    settings = get_whatsapp_settings(tenant_id)
    if not settings:
        return False
    return settings.is_configured()


def send_whatsapp_message(tenant_id: int, to_phone: str, message: str, 
                          template_name: str = None, template_params: List[str] = None,
                          notification_id: int = None, recipient_name: str = None,
                          recipient_type: str = None, recipient_id: int = None,
                          media_urls: List[str] = None, media_files: List[str] = None) -> Dict[str, Any]:
    """
    Send a WhatsApp message and log it
    
    Args:
        tenant_id: School/tenant ID
        to_phone: Recipient phone number
        message: Message text
        template_name: Optional template name
        template_params: Optional template parameters
        notification_id: Optional notification ID for logging
        recipient_name: Optional recipient name for logging
        recipient_type: Optional recipient type ('student', 'teacher', 'parent')
        recipient_id: Optional recipient ID
        media_urls: Optional list of publicly accessible media URLs
        
    Returns:
        dict with 'success', 'message_id', 'error' keys
    """
    from db_single import get_session
    from notification_models import WhatsAppSettings, WhatsAppMessageLog
    
    session = get_session()
    try:
        # Get settings
        settings = session.query(WhatsAppSettings).filter_by(
            tenant_id=tenant_id,
            is_enabled=True
        ).first()
        
        if not settings:
            return {'success': False, 'message_id': None, 'error': 'WhatsApp not configured'}
        
        if not settings.is_configured():
            return {'success': False, 'message_id': None, 'error': 'WhatsApp not properly configured'}
        
        if not settings.can_send_message():
            return {'success': False, 'message_id': None, 'error': 'Daily message limit reached'}
        
        # Create log entry
        log_entry = WhatsAppMessageLog(
            tenant_id=tenant_id,
            notification_id=notification_id,
            recipient_phone=to_phone,
            recipient_name=recipient_name,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            message_content=message[:1000] if message else None,
            template_name=template_name,
            status='pending'
        )
        session.add(log_entry)
        session.flush()  # Get the ID
        
        # Send message
        sender = WhatsAppSender(settings)
        result = sender.send_message(to_phone, message, template_name, template_params, media_urls=media_urls, media_files=media_files)
        
        # Update log entry
        if result['success']:
            log_entry.status = 'sent'
            log_entry.provider_message_id = result.get('message_id')
            log_entry.sent_at = datetime.now()
            settings.increment_message_count()
        else:
            log_entry.status = 'failed'
            log_entry.error_message = result.get('error')
        
        session.commit()
        return result
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error sending WhatsApp message: {e}")
        return {'success': False, 'message_id': None, 'error': str(e)}
    finally:
        session.close()


def send_whatsapp_bulk(tenant_id: int, recipients: List[Tuple[str, str, str]], 
                       message: str, notification_id: int = None,
                       template_name: str = None, template_params: List[str] = None,
                       media_urls: List[str] = None, media_files: List[str] = None) -> Dict[str, Any]:
    """
    Send WhatsApp messages to multiple recipients
    
    Args:
        tenant_id: School/tenant ID
        recipients: List of tuples (phone, name, type) where type is 'student'/'teacher'/'parent'
        message: Message text
        notification_id: Optional notification ID
        template_name: Optional template name
        template_params: Optional template parameters
        media_urls: Optional list of publicly accessible media URLs
        
    Returns:
        dict with 'success_count', 'failed_count', 'errors' keys
    """
    success_count = 0
    failed_count = 0
    errors = []
    
    for phone, name, recipient_type in recipients:
        result = send_whatsapp_message(
            tenant_id=tenant_id,
            to_phone=phone,
            message=message,
            template_name=template_name,
            template_params=template_params,
            notification_id=notification_id,
            recipient_name=name,
            recipient_type=recipient_type,
            media_urls=media_urls,
            media_files=media_files
        )
        
        if result['success']:
            success_count += 1
        else:
            failed_count += 1
            errors.append(f"{name} ({phone}): {result['error']}")
    
    return {
        'success_count': success_count,
        'failed_count': failed_count,
        'errors': errors
    }


def send_whatsapp_async(tenant_id: int, recipients: List[Tuple[str, str, str]], 
                        message: str, notification_id: int = None,
                        template_name: str = None, template_params: List[str] = None,
                        media_urls: List[str] = None, media_files: List[str] = None):
    """
    Send WhatsApp messages asynchronously in a background thread
    
    Args:
        Same as send_whatsapp_bulk
    """
    def _send_in_thread():
        logger.info(f"[WhatsApp] Starting async send to {len(recipients)} recipients")
        result = send_whatsapp_bulk(
            tenant_id=tenant_id,
            recipients=recipients,
            message=message,
            notification_id=notification_id,
            template_name=template_name,
            template_params=template_params,
            media_urls=media_urls,
            media_files=media_files
        )
        logger.info(f"[WhatsApp] Async send complete: {result['success_count']} sent, {result['failed_count']} failed")
    
    thread = Thread(target=_send_in_thread, daemon=True)
    thread.start()
    logger.info(f"[WhatsApp] Started background thread for {len(recipients)} recipients")
