#!/usr/bin/python3

from slack import RTMClient, WebClient
import functools
import time
import urllib.request

from escpos.printer import Usb
from PIL import Image, ImageOps

# If an API call fails, sleep for this long
RATE_LIMIT_SLEEP = 5

# List of errors that we shouldn't retry API calls on (i.e. the error was expected)
KNOWN_ERRORS = ['method_not_supported_for_channel_type']

class ChannelWatcher(object):
    def __init__(self, rtm_client, web_client, line_printer):
        self._rtm_client = rtm_client
        self._web_client = web_client
        self._line_printer = line_printer
        self._watching_channels = set()
        self._max_image_width = 512 # guess. smaller than 640, larger than 277.
        rtm_client.on(event='message', callback=self._handle_event)
        #print("connecting:", self._rtm_client.rtm_connect()) #auto_reconnect=True

    def watch_channel(self, channel_name):
        self._watching_channels.add(channel_name)

    #def poll(self):
    #    events = self._rtm_client.rtm_read()
    #    for event in events:
    #        print('event', event)
    #        try:
    #            self._handle_event(event)
    #        except Exception as e:
    #            print('error handling event', e)

    def _handle_event(self, **event):
        print('event', event)
        event = event['data']
        channel = event.get('channel')
        print('channel', channel)
        if not isinstance(channel, str):
            return # Event isn't of interest

        if channel not in self._watching_channels:
            # Attempt to translate the channel
            channel = self._get_channel(channel)
            print('channel_details', channel)
            channel_name = channel['channel']['name']
            print('channel.name', channel_name)

            if channel_name not in self._watching_channels:
                return # event isn't of interest

        text = event.get('text')
        print('text', text)

        if text:
            self._write(text)

        for f in event.get('files', []):
            self._handle_file(f)

    def _handle_file(self, file_):
        '''
        Called with an object like {'url_private_download': 'https://files.slack.com/...', 'original_w': 290, ... }
        Decides whether the file is of interest and what to do with it if so.
        '''
        print('file', file_)
        url = file_.get('url_private')
        mimetype = file_.get('mimetype')
        if not url or not mimetype:
            return

        if mimetype.startswith('image/'):
            print('fetching image', url)
            file_handle = self._fetch_file(url)
            self._handle_image(file_handle)

    def _handle_image(self, im_handle):
        '''
        Print an image, taking any handle which PIL knows how to open.
        If the image is too large for the printer, it will be appropriately scaled.
        '''
        im = Image.open(im_handle)
        if im.width > self._max_image_width:
            # Scale down the image
            new_width = self._max_image_width
            scale = new_width / im.width
            new_height = int(round(im.height*scale))
            im = ImageOps.fit(im, (new_width, new_height)) # TODO: defaults to nearest-neighbor?

        self._line_printer.image(im)

    def _write(self, text):
        try:
            print('writing: {}'.format(text))
            if not text.endswith('\n'):
                text += '\n'
            self._line_printer.text(text)
        except OSError as e:
            print('error', e)

    def _api_call(self, endpoint, **kwargs):
        for i in range(2):
            results = self._web_client.api_call(endpoint, json=kwargs)
            is_ok = results.get('ok', True)
            if is_ok: break
            print('api returned error', results)
            if results.get('error') in KNOWN_ERRORS: break
            time.sleep(RATE_LIMIT_SLEEP)
        return results

    def _fetch_file(self, url):
        auth = 'Bearer {}'.format(self._web_client.token)
        req = urllib.request.Request(url, headers={'Authorization': auth})
        return urllib.request.urlopen(req)


    @functools.lru_cache(None)
    def _get_channel(self, channel):
        '''
        return information about a channel handle.
        see https://api.slack.com/methods/channels.info
        '''
        return self._api_call('channels.info', channel=channel)

def make_watcher():
    token = open('api.token', 'r').read().strip()
    rtm_client = RTMClient(token=token)
    web_client = WebClient(token=token)
    print(web_client.api_call('users.profile.get'))
    lp = Usb(0x04b8, 0x0202, 0) #, profile="TM-T88III"
    watcher = ChannelWatcher(rtm_client, web_client, lp)
    watcher.watch_channel('shitposting')
    watcher.watch_channel('slack_api_testing')
    watcher.watch_channel('slack_api_cwallace')
    watcher.watch_channel('GHUEMR31V') # slack_api_cwallace

    return watcher

def main():
    watcher = make_watcher()
    watcher._rtm_client.start()

    #while True:
    #    watcher.poll()
    #    time.sleep(2)
    #watcher._rtm_client.stop()

if __name__ == '__main__':
    main()
