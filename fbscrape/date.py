import datetime
import logging
import re
import time
from typing import Tuple


date_regex = re.compile(r'^(?P<dayofweek>.*?)(?:, (?P<date>.*))?'
                        r'(?P<time>(?:(?: von (?P<von>.*))(?: bis (?P<bis>.*)))|(?: um (?P<um>.*)))$')
utc_regex = re.compile(r'UTC[+-]\d+')
logger = logging.getLogger(__name__)


def match_date(t: str) -> re.Match:
    m = date_regex.match(t)
    if m is None:
        raise ValueError('unexpected date %r' % t)
    return m


def pad_utc_offset(m: re.Match) -> str:
    return m[0].ljust(8, '0')


def fix_utc_offset(t: str) -> str:
    return utc_regex.sub(pad_utc_offset, t)


def parse_date_part(m: re.Match) -> datetime.date:
    dayofweek = m['dayofweek']
    if dayofweek == 'Heute':
        off = 0
    elif dayofweek == 'Morgen':
        off = 1
    elif not m['date']:
        today = datetime.date.today().weekday()
        then  = datetime.datetime.strptime(dayofweek, '%A').weekday()
        off   = then - today
        while off <= 0:
            off += 7
    else:
        # parse absolute date
        if m['date'] is None:
            raise ValueError('cannot find date substring')
        return datetime.datetime.strptime(m['date'], '%d. %B %Y').date()

    # add offset for relative dates
    return datetime.date.today() + datetime.timedelta(days=off)


def parse_time_part(t: str) -> datetime.time:
    time_tuple = time.strptime(fix_utc_offset(t), '%H:%M UTC%z')
    tz = datetime.timezone(datetime.timedelta(seconds=time_tuple.tm_gmtoff))
    return datetime.time(*time_tuple[3:6], tzinfo=tz)


def parse_date(t: str) -> Tuple[datetime.datetime, datetime.datetime]:
    logger.debug('parsing date %r...', t)

    try:
        m = match_date(t)
        date = parse_date_part(m)

        start_time = parse_time_part(m['von'] or m['um'])
        start = datetime.datetime.combine(date, start_time)
        if m['bis']:
            end_time = parse_time_part(m['bis'])
            end = datetime.datetime.combine(date, end_time)
        else:
            end = start.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    except ValueError:
        logger.exception('cannot parse date %r', t)
        raise

    while end <= start:
        end += datetime.timedelta(days=1)

    return (start, end)
