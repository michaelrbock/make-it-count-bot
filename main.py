from google.appengine.api import urlfetch

import logging
import json
import os
import urllib
import webapp2


_GET_STARTED_PAYLOAD = 'GET_STARTED_PAYLOAD'
_PAGE_ACCESS_TOKEN = 'EAAZARvBDfATkBAB1pUyW3xlimC5ZCr7ZAK02l4jf5lVl8Fz5foXkefdfAOGb3y7wkusdxoZBgUJi6hHDE9jwanOTWZBgLfriS8fqWESodntxNbPnZARhDBEzInAusdR2zZAV2cHHk4mmUFNpEZB6uHgPSm7eigjq4Hg2XMUzcmik9QZDZD'
_VERIFICATION_TOKEN = 'make_it_count_verification_token_is_so_secret'


_BASE_URL = 'https://make-it-count.herokuapp.com/images/'
_WHITE_HOUSE_IMAGES = {
  'Much more Democratic': 'white-house-dark-blue.png',
  'Somewhat more Democratic': 'white-house-light-blue.png',
  'Like the country as a whole': 'white-house-neutral.png',
  'Somewhat more Republican': 'white-house-light-red.png',
  'Much more Republican': 'white-house-dark-red.png',
}
_SENATE_IMAGES = {
  'Likely Democratic': 'senate-dark-blue.png',
  'Competitive': 'senate-neutral.png',
  'Likely Republican': 'senate-dark-red.png'
}


class BaseHandler(webapp2.RequestHandler):
  def write(self, *a, **kw):
    self.response.out.write(*a, **kw)


class MainPage(BaseHandler):
  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'
    self.write('Hello')


def get_states():
  with open(os.path.join(os.path.split(__file__)[0], 'static/states.json')) as file:
    return json.load(file)


def create_senators_message(senator):
  fb_link = 'https://www.facebook.com/'
  for channel in senator['channels']:
    if channel['type'] == 'Facebook':
      fb_link += channel['id']
  message_data = {
    'title': senator['name'], 'subtitle':
    'Is your senator', 'image_url': senator['photoUrl'], 'item_url':
    senator['urls'][0], 'button_type': 'web_url', 'button_title': 'Follow '
    'on Facebook', 'button_url': fb_link
  }
  if senator['up_for_reelection']:
    message_data['subtitle'] += ' & is up for re-election'
  if senator['contested']:
    message_data['subtitle'] += " & it's going to be a close race!"
  return message_data


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

  def send_button_message(self, recipient_id, data):
    message_data = {
      'recipient': {
        'id': recipient_id
      },
      'message': {
        'attachment': {
          'type': 'template',
          'payload': {
            'template_type': 'button',
            'text': data.get('text', 'text'),
            'buttons': [{
              'type': data.get('button_type', 'postback'),
              'title': data.get('button_title', 'Next fact please!'),
            }]
          }
        }
      }
    }
    if 'payload' in data:
      message_data['message']['attachment']['payload']['buttons'][0]['payload'] = data.get('payload')
    if 'button_url' in data:
      message_data['message']['attachment']['payload']['buttons'][0]['url'] = data.get('button_url')
    self.call_send_api(message_data)

  def send_generic_message(self, recipient_id, data, extra_button=None):
    message_data = {
      'recipient': {
        'id': recipient_id
      },
      'message': {
        'attachment': {
          'type': 'template',
          'payload': {
            'template_type': 'generic',
            'elements': [{
              'title': data.get('title', 'title'),
              'subtitle': data.get('subtitle', 'subtitle'),
              'item_url': data.get('item_url', ''),
              'image_url': data.get('image_url', ''),
              'buttons': [{
                'type': data.get('button_type', 'postback'),
                'title': data.get('button_title', 'Click me!'),
              }]
            }]
          }
        }
      }
    }
    if 'payload' in data:
      message_data['message']['attachment']['payload']['elements'][0]['buttons'][0]['payload'] = data.get('payload')
    if 'button_url' in data:
      message_data['message']['attachment']['payload']['elements'][0]['buttons'][0]['url'] = data.get('button_url')
    if extra_button:
      message_data['message']['attachment']['payload']['elements'][0]['buttons'].append(extra_button)
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
    logging.info(address_text)
    uri += urllib.quote_plus(address_text)
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
        states = get_states()
        # 2
        self.send_text_message(sender_id,
          'You live in ' + states[state]['full_name'])
        # 3
        self.send_button_message(sender_id, {'text': 'Your vote is worth %s '
          'times as much as a typical vote in the U.S.' %
          states[state]['voter_power_index'], 'button_title' : 'Next fact '
          'please!', 'payload': '3_' + state})
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
    elif payload[0] == '3':
      state = payload.split('_')[1]
      states = get_states()
      # 4
      self.send_button_message(sender_id, {'text': 'Your state as a %s chance '
        'of tipping the election.' % states[state]['tipping_point_chance'],
        'button_title' : 'Interesting, go on...', 'payload': '4_' + state})
    elif payload[0] == '4':
      state = payload.split('_')[1]
      states = get_states()
      # 5
      self.send_generic_message(sender_id, {'title':
        states[state]['president_trends'] , 'subtitle': 'How Your State Tends '
        'to Vote For President', 'image_url': (_BASE_URL +
          _WHITE_HOUSE_IMAGES[states[state]['president_trends']]),
        'button_title': 'Cool', 'payload': '5_' + state})
    elif payload[0] == '5':
      state = payload.split('_')[1]
      states = get_states()
      # 6
      self.send_generic_message(sender_id, {'title':
        states[state]['senator_trends'], 'subtitle': 'Likely Senate Race '
        'Outcome', 'image_url': (_BASE_URL +
          _SENATE_IMAGES[states[state]['senator_trends']]), 'button_title':
        'Whoa!', 'payload': '6_' + state})
    elif payload[0] == '6':
      state = payload.split('_')[1]
      states = get_states()
      if states[state]['senators']:  # check against dc.
        # 7
        message_data = create_senators_message(states[state]['senators'][0])
        extra_button = {
          'type': 'postback',
          'title': 'Next senator!',
          'payload': '7_' + state
        }
        self.send_generic_message(sender_id, message_data, extra_button)
      else:
        self.send_button_message(sender_id, {'text': 'Now take this information'
          ' straight to the polls!', 'button_type': 'web_url', 'button_title':
          'Register to vote', 'button_url': 'https://vote.org'})
        self.send_text_message(sender_id, 'Type in another address to see more '
          'info :).')
    elif payload[0] == '7':
      state = payload.split('_')[1]
      states = get_states()
      # 8
      message_data = create_senators_message(states[state]['senators'][1])
      self.send_generic_message(sender_id, message_data)

      self.send_button_message(sender_id, {'text': 'Now take this information '
        'straight to the polls!', 'button_type': 'web_url', 'button_title':
        'Register to vote', 'button_url': 'https://vote.org'})
      self.send_text_message(sender_id, 'Type in another address to see more '
        'info :).')
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
