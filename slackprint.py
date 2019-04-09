#!/usr/bin/python3

from slackclient import SlackClient
import functools
import time

# If an API call fails, sleep for this long
RATE_LIMIT_SLEEP = 20

class LinePrinter(object):
    '''
    Wraps a line printer with stateful methods to control formatting, etc
    '''
    # Note: ESC/POS commands are data sent over the /dev/usb/lp0 interface which control behavior.
    # References:
    #   http://www.lprng.com/RESOURCES/PPD/epson.htm
    #   https://mike42.me/blog/what-is-escpos-and-how-do-i-use-it
    def __init__(self, device):
        self._device = device

    def write(self, data):
        with open(self._device, 'a') as dev:
            dev.write(text)

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
                print('error handling exception', e)

    def _handle_event(self, event):
        channel = event.get('channel')
        print('channel', channel)
        text = event.get('text')
        print('text', text)
        if isinstance(channel, str):
            channel = self._get_channel(channel)
            print('channel_details', channel)
            channel_name = channel['channel']['name']
            print('channel.name', channel_name)
            if channel_name in self._watching_channels and text:
                self._write(text)

    def _write(self, text):
        try:
            print('writing: {}'.format(text))
            if not text.endswith('\n'):
                text += '\n'
            self._line_printer.write(text)
        except OSError as e:
            print('error', e)

    def _api_call(self, endpoint, **kwargs):
        for i in range(100):
            results = self._client.api_call(endpoint, **kwargs)
            is_ok = results.get('ok', True)
            if is_ok: break
            print('api returned error', results)
            time.sleep(RATE_LIMIT_SLEEP)
        return results


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
    watcher = ChannelWatcher(client, LinePrinter('/dev/usb/lp0'))
    watcher.watch_channel('shitposting')
    watcher.watch_channel('slack_api_testing')

    while True:
        watcher.poll()
        time.sleep(2)

if __name__ == '__main__':
    main()
