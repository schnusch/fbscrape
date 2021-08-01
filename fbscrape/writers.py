import datetime
from getpass import getuser
import icalendar  # type: ignore
import io
import json
import logging
import os
import pathlib
import pytz
from socket import gethostname
import subprocess
import sys
import tempfile
from typing import BinaryIO, Optional, Union


class Writer:
    def __init__(self, fp: BinaryIO):
        self._fp = fp

    def __enter__(self):
        return self

    def write_event(self, event):
        raise NotImplementedError


def compare_vevents(event1: icalendar.Event, event2: icalendar.Event) -> bool:
    for k in (event1.keys() | event2.keys()):
        if k.lower() == 'dtstamp':
            pass
        elif k in event1 and k in event2:
            if event1.decoded(k) != event2.decoded(k):
                return False
        else:
            return False
    return True


def generate_uid(url: str) -> str:
    assert url.startswith('https://mbasic.')
    return url[15:].replace('/', '-')


class IcsDirectory:
    logger = logging.getLogger(__name__ + '.IcsDirectory')

    def __init__(self, directory: str):
        self.directory = pathlib.Path(directory)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        git = ['git',
               '-c', 'user.name=fbscrape',
               '-c', 'user.email=' + getuser() + '@' + gethostname()]
        kwargs = dict(cwd   =self.directory,
                      stdin =subprocess.DEVNULL,
                      stdout=sys.stderr)
        p = subprocess.run(git + ['add', '-A'], **kwargs)
        if p.returncode == 0:
            subprocess.run(git + ['commit', '-m', 'update events'], **kwargs)

    def _get_path(self, event: Union[str, icalendar.Event]) -> pathlib.Path:
        uid = event if isinstance(event, str) else event.decoded('uid').decode('ascii')
        return self.directory / (uid + '.ics')

    def _fix_dtstamp(self, event: icalendar.Event):
        try:
            old_event = self.read_event(event.decoded('uid').decode('ascii'))
        except (FileNotFoundError, ValueError):
            self.logger.info('new event %r',
                             event.decoded('uid').decode('ascii'))
            return
        if compare_vevents(event, old_event):
            # the event content did not change so do we so not change DTSTAMP
            # so the file contents stay the same
            event['dtstamp'] = old_event['dtstamp']
            self.logger.info('event %r did not change, using old DTSSTAMP',
                             event.decoded('uid').decode('ascii'))

    def write_event(self, event):
        vevent = IcsWriter.create_vevent(event)
        path = self._get_path(vevent)
        self._fix_dtstamp(vevent)
        with tempfile.NamedTemporaryFile(dir=self.directory) as tmp:
            cal = icalendar.Calendar()
            cal.add('version', '2.0')
            cal.add('prodid',  '-//fbscrape')
            cal.add_component(vevent)
            tmp.write(cal.to_ical())
            tmp.flush()
            os.rename(tmp.name, path)
            tmp._closer.delete = False
            self.logger.info('wrote event %r',
                             vevent.decoded('uid').decode('ascii'))

    def read_event(self, uid: str) -> icalendar.Event:
        with open(self._get_path(uid), 'rb') as fp:
            data = fp.read()
        cal = icalendar.Event.from_ical(data)
        return cal.subcomponents[0]


class IcsWriter(Writer):
    def __enter__(self):
        self._cal = icalendar.Calendar()
        self._cal.add('version', '2.0')
        self._cal.add('prodid',  '-//fbscrape')
        self._cal.add('method',  'PUBLISH')
        return super().__enter__()

    @staticmethod
    def create_vevent(event) -> icalendar.Event:
        vevent = icalendar.Event()
        vevent.add('uid',      generate_uid(event.url))
        vevent.add('url',      event.url)
        vevent.add('dtstamp',  datetime.datetime.now(datetime.timezone.utc))
        # For some reason when using datetime.timezone.utc icalendar adds the
        # attribute TZID (which is not allowed for timestamps in UTC).
        # By using pytz.utc this is avoided.
        # For some reason it's not a problem in the above line.
        vevent.add('dtstart',  event.start.astimezone(pytz.utc))
        vevent.add('dtend',    event.end.astimezone(pytz.utc))
        vevent.add('summary',  event.title)
        vevent.add('location', event.location)
        if event.details:
            vevent.add('description', event.details)
        return vevent

    def write_event(self, event):
        vevent = self.create_vevent(event)
        self._cal.add_component(vevent)

    def __exit__(self, type, value, traceback):
        self._fp.write(self._cal.to_ical())


class JsonWriter(Writer):
    def __enter__(self):
        self._events = []
        return super().__enter__()

    def write_event(self, event):
        event_dict = {
            'url':      event.url,
            'title':    event.title,
            'image':    event.image,
            'start':    int(event.start.timestamp()),
            'end':      int(event.end.timestamp()),
            'location': event.location,
        }
        if event.details:
            event_dict['details'] = event.details
        self._events.append(event_dict)

    def __exit__(self, type, value, traceback):
        out = io.TextIOWrapper(self._fp, encoding='utf-8', newline='\n')
        json.dump(self._events, out, indent='\t', separators=(',', ': '))
        out.write('\n')
