#!/usr/bin/python3

from slackclient import SlackClient
import functools
import time
import urllib.request

from escpos.printer import Usb

# If an API call fails, sleep for this long
RATE_LIMIT_SLEEP = 5

# List of errors that we shouldn't retry API calls on (i.e. the error was expected)
KNOWN_ERRORS = ['method_not_supported_for_channel_type']

class ChannelWatcher(object):
    def __init__(self, client, line_printer):
        self._client = client
        self._line_printer = line_printer
        self._watching_channels = set()
        print("connecting:", self._client.rtm_connect(auto_reconnect=True))

    def watch_channel(self, channel_name):
        self._watching_channels.add(channel_name)

    def poll(self):
        events = self._client.rtm_read()
        for event in events:
            print('event', event)
            try:
                self._handle_event(event)
            except Exception as e:
                print('error handling event', e)

    def _handle_event(self, event):
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
            self._line_printer.image(file_handle)

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
            results = self._client.api_call(endpoint, **kwargs)
            is_ok = results.get('ok', True)
            if is_ok: break
            print('api returned error', results)
            if results.get('error') in KNOWN_ERRORS: break
            time.sleep(RATE_LIMIT_SLEEP)
        return results

    def _fetch_file(self, url):
        auth = 'Bearer {}'.format(self._client.token)
        req = urllib.request.Request(url, headers={'Authorization': auth})
        return urllib.request.urlopen(req)


    @functools.lru_cache(None)
    def _get_channel(self, channel):
        '''
        return information about a channel handle.
        see https://api.slack.com/methods/channels.info
        '''
        return self._api_call('channels.info', channel=channel)

def main():
    token = open('api.token', 'r').read().strip()
    client = SlackClient(token)
    print(client.api_call('users.profile.get'))
    lp = Usb(0x04b8, 0x0202, 0, profile="TM-T88III")
    #lp.image('doge.jpg')
    watcher = ChannelWatcher(client, lp)
    watcher.watch_channel('shitposting')
    watcher.watch_channel('slack_api_testing')
    watcher.watch_channel('slack_api_cwallace')
    watcher.watch_channel('GHUEMR31V') # slack_api_cwallace

    while True:
        watcher.poll()
        time.sleep(2)

if __name__ == '__main__':
    main()
