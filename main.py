from google.appengine.api import urlfetch

import logging
import json
import urllib
import webapp2


_GET_STARTED_PAYLOAD = 'GET_STARTED_PAYLOAD'
_PAGE_ACCESS_TOKEN = 'EAAZARvBDfATkBAB1pUyW3xlimC5ZCr7ZAK02l4jf5lVl8Fz5foXkefdfAOGb3y7wkusdxoZBgUJi6hHDE9jwanOTWZBgLfriS8fqWESodntxNbPnZARhDBEzInAusdR2zZAV2cHHk4mmUFNpEZB6uHgPSm7eigjq4Hg2XMUzcmik9QZDZD'
_VERIFICATION_TOKEN = 'make_it_count_verification_token_is_so_secret'


class BaseHandler(webapp2.RequestHandler):
  def write(self, *a, **kw):
    self.response.out.write(*a, **kw)


class MainPage(webapp2.RequestHandler):
  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.write('Hello, World!')


class WebhookHandler(BaseHandler):
  def get(self):
    if (self.request.get('hub.mode') == 'subscribe' and
        self.request.get('hub.verify_token') == _VERIFICATION_TOKEN):
      self.write(self.request.get('hub.challenge'))

  def received_authentication(self, event):
    pass

  def call_send_api(self, message_data):
    uri = ('https://graph.facebook.com/v2.6/me/messages?access_token=' +
      _PAGE_ACCESS_TOKEN)
    payload = json.dumps(message_data)
    result = urlfetch.fetch(uri, method='POST', payload=payload,
      headers={'Content-Type': 'application/json'})
    if result.status_code == 200:
      content = json.loads(result.content)
      logging.info(
        'Successfully sent generic message with id %s to recipient %s' %
        (content['recipient_id'], content['message_id']))
    else:
      logging.error('Unable to send message.')
      logging.error(result.status_code)
      logging.error(result.content)

  def send_generic_message(self, recipient_id):
    message_data = {
      'recipient': {
        'id': recipient_id
      },
      'message': {
        'attachment': {
          'type': 'template',
          'payload': {
            'template_type': "generic",
            'elements': [{
              'title': title,
              'subtitle': 'subtitle',
              'item_url': 'https://google.com',
              'image_url': 'http://messengerdemo.parseapp.com/img/rift.png',
              'buttons': [{
                'type': 'web_url',
                'url': 'https://facebook.com',
                'title': 'Open Web URL'
              }, {
                'type': 'postback',
                'title': 'Call Postback',
                'payload': 'Payload for the first bubble, second button'
              }]
            }]
          }
        }
      }
    }
    self.call_send_api(message_data)

  def send_text_message(self, recipient_id, text):
    message_data = {
      'recipient': {
        'id': recipient_id
      },
      'message': {
        'text': text
      }
    }
    self.call_send_api(message_data)

  def handle_address(self, address_text):
    uri = 'https://maps.googleapis.com/maps/api/geocode/json?address='
    uri += urllib.urlencode(address_text)
    result = urlfetch.fetch(uri)
    if result.status_code == 200:
      content = json.loads(result.content)
      for component in content['results'][0]['address_components']:
        if 'administrative_area_level_1' in component['types']:
          logging.info('Found state: ' + component['short_name'].lower())
          return component['short_name'].lower()
    else:
      logging.error('Unable to send message.')
      logging.error(result.status_code)
      logging.error(result.content)

  def received_message(self, event):
    sender_id = event['sender']['id']
    recipient_id = event['recipient']['id']
    time_of_message = event['timestamp']
    message = event['message']

    logging.info('Received message for user %s and page %s at %d with message:'
      % (sender_id, recipient_id, time_of_message))
    logging.info(str(message))

    if 'text' in message:
      if message['text'] == 'image':
        send_image_message(sender_id)
      elif message['text'] == 'button':
        send_button_message(sender_id)
      elif message['text'] == 'generic':
        self.send_generic_message(sender_id)
      elif message['text'] == 'receipt':
        send_receipt_message(sender_id)
      else:
        state = self.handle_address(message['text'])
        self.send_text_message(sender_id, state)
    elif 'attachments' in message:
      self.send_text_message(sender_id, 'Message with attachment received')

  def received_delivery_confirmation(self, event):
    pass

  def received_postback(self, event):
    sender_id = event['sender']['id']
    recipient_id = event['recipient']['id']
    time_of_postback = event['timestamp']

    payload = event['postback']['payload']

    logging.info('Received postback for user %s and page %s with payload (%s)'
      ' at %d' % (sender_id, recipient_id, payload, time_of_postback))

    if payload == _GET_STARTED_PAYLOAD:
      # 1
      self.send_text_message(sender_id, 'The 2016 Election is one of the '
        'most important of all time. Type in your address to find out how '
        'much your vote will count in this historic election.')
    else:
      self.send_text_message(sender_id, 'Postback called')

  def post(self):
    request_obj = json.loads(self.request.body)
    logging.info(str(request_obj))
    if request_obj['object'] == 'page':
      for page_entry in request_obj['entry']:
        time = page_entry['time']

        for messaging_event in page_entry['messaging']:
          if 'optin' in messaging_event:
            self.received_authentication(messaging_event)
          elif 'message' in messaging_event:
            self.received_message(messaging_event)
          elif 'delivery' in messaging_event:
            self.received_delivery_confirmation(messaging_event)
          elif 'postback' in messaging_event:
            self.received_postback(messaging_event)
          else:
            logging.error('Webhook received unknown messaging_event: '
              + str(messaging_event))


app = webapp2.WSGIApplication([
  ('/', MainPage),
  ('/webhook', WebhookHandler)
], debug=True)
