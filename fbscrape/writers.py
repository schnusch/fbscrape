import datetime
import icalendar  # type: ignore
import io
import json
import pytz
from typing import BinaryIO


class Writer:
    def __init__(self, fp: BinaryIO):
        self._fp = fp

    def __enter__(self):
        return self

    def write_event(self, event):
        raise NotImplementedError


class IcsWriter(Writer):
    def __enter__(self):
        self._cal = icalendar.Calendar()
        self._cal.add('version', '2.0')
        self._cal.add('prodid',  '-//fbscrape')
        self._cal.add('method',  'PUBLISH')
        return super().__enter__()

    def write_event(self, event):
        vevent = icalendar.Event()
        vevent.add('uid',      event.url)
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
