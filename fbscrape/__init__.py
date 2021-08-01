"""
fbscrape
Copyright (C) 2021  schnusch

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import datetime
import json  # type: ignore
import locale
import logging
import os.path
import re
import shutil
import sys
from typing import cast, Any, BinaryIO, Iterator, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from selenium.common.exceptions import NoSuchElementException  # type: ignore
from selenium.webdriver import Firefox  # type: ignore
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile  # type: ignore
from selenium.webdriver.firefox.options import Options as FirefoxOptions  # type: ignore
from selenium.webdriver.remote.webdriver import WebDriver  # type: ignore
from selenium.webdriver.support.ui import WebDriverWait  # type: ignore

from .date import parse_date
from .writers import IcsDirectory, IcsWriter, JsonWriter


clubs = {
    'aqua':                '/AquaDD/events/',
    'bärenzwinger':        '/clubbaerenzwinger/events/',
    'borsi':               '/Borsi34/events/',
    'club11':              '/clubelf.de/events/',
    'count down':          '/countdowndd/events/',
    'heinrich-cotta-club': '/HeinrichCottaClub/events/',
    'gag18':               '/KellerklubGAG18eV/events/',
    'gutzkowclub':         '/Gutzkow/events/',
    'hängemathe':          '/clubhaengemathe/events/',
    'novitatis':           '/novitatis/events/',
    'traumtänzer':         '/club.traumtaenzer/events/',
    'wu5':                 '/clubwu5/events/',
}

logger = logging.getLogger(__name__)


@contextmanager
def open_output(path:      Optional[str] = None,
                overwrite: bool          = False) -> Iterator[BinaryIO]:
    if path is None:
        out = cast(Any, sys.stdout).detach()
        sys.stdout = sys.stderr
        yield out
    else:
        with open(path, 'wb' if overwrite else 'xb') as fp:
            yield cast(BinaryIO, fp)


@contextmanager
def firefox_profile(path: Optional[str] = None) -> Iterator[FirefoxProfile]:
    profile = FirefoxProfile(path)
    try:
        yield profile
    finally:
        shutil.rmtree(profile.path, ignore_errors=True)


@contextmanager
def firefox_driver(profile:       str,
                   headless:      bool          = True,
                   minimize:      bool          = False,
                   timeout:       Optional[int] = None,
                   implicit_wait: Optional[int] = None,
                   log_path:      Optional[str] = None) -> Iterator[Firefox]:
    options = FirefoxOptions()
    if profile is not None:
        options.profile = profile
    if headless:
        options.add_argument('--headless')
    kwargs = {}
    if log_path is not None:
        kwargs['service_log_path'] = log_path
    driver = Firefox(options=options, **kwargs)
    try:
        if minimize and not headless:
            driver.minimize_window()
        if timeout is not None:
            driver.set_page_load_timeout(timeout)
        if implicit_wait is not None:
            driver.implicitly_wait(implicit_wait)
        yield driver
    finally:
        driver.close()


def load_cookies(driver: WebDriver, cookies: str):
    with open(cookies, 'r', encoding='utf-8') as fp:
        for cookie in json.load(fp):
            driver.add_cookie(cookie)


def normalize_event_url(url: str) -> str:
    parsed_url = urlparse(url)
    m = re.match(r'^/events/[^/]*', parsed_url.path)
    if m is None:
        raise ValueError
    return f'https://mbasic.facebook.com{m[0]}'


def find_upcoming_event_urls(driver: WebDriver):
    events = []
    for elem in driver.find_elements_by_css_selector('table a[href][aria-label]'):
        href = elem.get_attribute('href')
        if href is None:
            continue
        try:
            url = normalize_event_url(href)
        except ValueError:
            continue
        events.append(url)
    if events:
        logger.info('%d event%s found on %s',
                    len(events),
                    '' if len(events) == 1 else 's',
                    driver.current_url)
    else:
        # try to find the no-events-notification, if it is found there are no
        # upcoming events, if not a NoSuchElementException is raised for us
        driver.find_element_by_css_selector('#pages_msite_body_contents table div')
        logger.warning('no events found on %s', driver.current_url)
    return (True, events)


def bypass_cookie_consent(driver: WebDriver):
    try:
        cookie_consent = driver.find_element_by_name('accept_consent')
    except NoSuchElementException:
        return
    accept_button = cookie_consent.find_element_by_xpath('ancestor::form//button')
    accept_button.click()


def get_event_urls(driver:  WebDriver,
                   page:    str,
                   timeout: int       = 10) -> List[str]:
    driver.get(urljoin('https://mbasic.facebook.com/', page))
    bypass_cookie_consent(driver)
    _, upcoming_events = WebDriverWait(driver, timeout).until(find_upcoming_event_urls)
    return upcoming_events


def collect_events(driver: WebDriver,
                   pages:  List[str]) -> Tuple[bool, List[str]]:
    error = False
    if not pages:
        pages = list(clubs.values())
    else:
        pages = [clubs.get(page, page) for page in pages]
    event_urls = []
    for page in pages:
        try:
            event_urls.extend(get_event_urls(driver, page))
        except Exception:
            logger.exception('cannot find upcoming events on %s', page)
            error = True
    return (error, event_urls)


@dataclass
class FBEvent:
    url:      str
    title:    str
    start:    datetime.datetime
    end:      datetime.datetime
    location: str
    details:  Optional[str] = None
    image:    Optional[str] = None


def get_event(driver: WebDriver,
              url:    str) -> FBEvent:
    url = normalize_event_url(url)
    driver.get(url)
    bypass_cookie_consent(driver)

    title         = driver.find_element_by_tag_name('h1')
    event_summary = driver.find_element_by_id('event_summary')

    infos = event_summary.find_elements_by_css_selector('dt div')
    start, end = parse_date(infos[0].text)
    location = infos[1].text if len(infos) > 1 else None

    ev = FBEvent(
        url      = url,
        title    = title.text,
        start    = start,
        end      = end,
        location = location,
    )

    try:
        details = event_summary.find_element_by_xpath('following::section')
        ev.details = details.text
    except NoSuchElementException:
        pass

    try:
        image = driver.find_element_by_css_selector('#event_header img')
        ev.image = image.get_property('src')
    except NoSuchElementException:
        pass

    return ev


def main(argv: Optional[List[str]] = None):
    locale.setlocale(locale.LC_ALL, '')

    p = argparse.ArgumentParser(
        description="Scrape Facebook events",
        epilog="""
            The cookie file is expected to contain a JSON-encoded list. Each
            element in the list is an object where the property `name` is the
            cookie's name and the property `value` is the cookie's value.
        """)
    p.add_argument('-e', '--events',
                   action='store_true',
                   help="treat <page> as event URL not as a Facebook page")
    p.add_argument('--headless',
                   action='store_true',
                   help="start browser in headless mode")
    p.add_argument('-c', '--cookies',
                   metavar='<cookie file>',
                   required=True,
                   help="see format of the cookie file below")
    p.add_argument('-d', '--directory',
                   action='store_true',
                   help="write events to separare iCalendar files in a directory")
    p.add_argument('-j', '--json',
                   dest='writer_class',
                   action='store_const',
                   default=IcsWriter,
                   const=JsonWriter,
                   help="write events as a JSON array instead of iCalendar")
    p.add_argument('-o', '--out',
                   metavar='<out>',
                   help="write to <out> instead of stdout")
    p.add_argument('-v', '--verbose',
                   action='store_const',
                   default=logging.INFO,
                   const=logging.DEBUG,
                   help="enable debug logging")
    p.add_argument('--geckodriver-log',
                   metavar='<path>',
                   default=os.path.devnull,
                   help="path to geckodriver's log file")
    p.add_argument('pages',
                   metavar='<page>',
                   nargs='*',
                   help="Facebook page or event URL")
    args = p.parse_args(argv)

    logging.basicConfig(format='[%(asctime)s] %(levelname)-8s %(name)-29s %(message)s',
                        level=args.verbose, stream=sys.stderr)

    if args.events and not args.pages:
        print(f'{sys.argv[0]}: no events given', file=sys.stderr)
        sys.exit(1)

    if args.directory and args.out is None:
        print(f'{sys.argv[0]}: -d/--directory requires -o/--out', file=sys.stderr)
        sys.exit(1)

    if args.directory:
        # save us from refactoring
        @contextmanager
        def open_output(path, overwrite):
            yield path
        args.writer_class = IcsDirectory

    with open_output(args.out, overwrite=True) as out:
        with firefox_profile() as profile:
            profile.set_preference('javascript.enabled', False)
            profile.set_preference('network.cookie.cookieBehavior', 1)

            with firefox_driver(profile, headless=args.headless,
                                log_path=args.geckodriver_log) as driver:
                driver.get('https://mbasic.facebook.com/')
                load_cookies(driver, args.cookies)

                if args.events:
                    error  = False
                    event_urls = args.pages
                else:
                    error, event_urls = collect_events(driver, args.pages)

                failed_events = 0
                with args.writer_class(out) as w:
                    for url in event_urls:
                        try:
                            event = get_event(driver, url)
                        except Exception:
                            logger.exception('cannot extract event info on %s', url)
                            error = True
                            failed_events += 1
                        else:
                            logger.info('extracted %s at %s, %s',
                                        event.title,
                                        event.location,
                                        event.start.strftime('%F %T%z'))
                            w.write_event(event)

    if failed_events > 0:
        logger.error('failed to scrape %d of %d events', failed_events,
                     len(event_urls))
    if error:
        sys.exit(1)