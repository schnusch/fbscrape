import datetime
import icalendar  # type: ignore
import json
import re
import subprocess
from typing import Any, List, BinaryIO, Union


class PandocBlock(dict):
    def __init__(self, t: str, c: Any = None):
        self['t'] = t
        if c is not None:
            self['c'] = c


def pandoc_to_markdown(blocks: List[PandocBlock], out: BinaryIO):
    document = {
        'pandoc-api-version': [1, 22],
        'meta': {},
        'blocks': blocks,
    }
    p = subprocess.run(['pandoc', '-t', 'markdown', '-f', 'json'],
                       input=json.dumps(document, separators=(',', ':')).encode('utf-8'),
                       stdout=out)
    if p.returncode != 0:
        raise ValueError('pandoc error')


def pandoc_space() -> PandocBlock:
    return PandocBlock('Space')


def pandoc_linebreak() -> PandocBlock:
    return PandocBlock('LineBreak')


def pandoc_horizontalrule() -> PandocBlock:
    return PandocBlock('HorizontalRule')


def pandoc_str(text: Union[str, bytes]) -> PandocBlock:
    if isinstance(text, bytes):
        text = text.decode('utf-8')
    return PandocBlock('Str', text)


def pandoc_strong(blocks: List[PandocBlock]) -> PandocBlock:
    return PandocBlock('Strong', blocks)


def pandoc_link(text: Union[str, bytes], url: Union[str, bytes]) -> PandocBlock:
    if isinstance(url, bytes):
        url = url.decode('utf-8')
    return PandocBlock('Link', (['', [], []],
                                [pandoc_str(text)],
                                [url, '']))


def pandoc_url(url: Union[str, bytes]) -> PandocBlock:
    if isinstance(url, bytes):
        url = url.decode('utf-8')
    return PandocBlock('Link', (['', ['uri'], []],
                                [pandoc_str(url)],
                                [url, '']))


def pandoc_header(level: int, text: str) -> PandocBlock:
    return PandocBlock('Header', (3,
                                  ['', [], []],
                                  [
                                      pandoc_str(text),
                                  ]))


def pandoc_para(blocks: List[PandocBlock]) -> PandocBlock:
    return PandocBlock('Para', blocks)


def pandoc_blockquote(blocks: List[PandocBlock]) -> PandocBlock:
    return PandocBlock('BlockQuote', blocks)


def format_time(t: datetime.datetime) -> str:
    return t.astimezone().strftime('%a %d.%m.%Y, %H:%M%z')


def pandoc_blocks_from_event(event: icalendar.Event) -> List[PandocBlock]:
    screenshot  = event.decoded('uid').decode('ascii') + '.png'
    description = event.decoded('description').decode('utf-8')
    paragraphs  = []  # type: List[PandocBlock]
    for paragraph in re.split(r'\n{2,}', description):
        blocks = []  # type: List[PandocBlock]
        for line in paragraph.splitlines():
            blocks.append(pandoc_str(line))
            blocks.append(pandoc_linebreak())
        paragraphs.append(pandoc_para(blocks[:-1]))
    return [
        pandoc_header(3, event.decoded('summary')),
        pandoc_para([
            pandoc_strong([pandoc_str('Beginn:')]),
            pandoc_space(),
            pandoc_str(format_time(event.decoded('dtstart'))),
            pandoc_linebreak(),

            pandoc_strong([pandoc_str('Ende:')]),
            pandoc_space(),
            pandoc_str(format_time(event.decoded('dtend'))),
            pandoc_linebreak(),

            pandoc_strong([pandoc_str('Ort:')]),
            pandoc_space(),
            pandoc_str(event.decoded('location')),
            pandoc_linebreak(),

            pandoc_strong([pandoc_str('Link:')]),
            pandoc_space(),
            pandoc_url(event.decoded('url')),
            pandoc_linebreak(),

            pandoc_strong([pandoc_str('Screenshot:')]),
            pandoc_space(),
            pandoc_link(screenshot, screenshot),
        ]),
        pandoc_blockquote(paragraphs),
    ]


def write_readme(fp: BinaryIO, events: List[icalendar.Event]):
    now = datetime.datetime.now(datetime.timezone.utc)
    key = lambda ev: ev.decoded('dtstart')
    events = sorted(filter(lambda ev: key(ev) >= now, events), key=key)

    blocks: List[PandocBlock] = []
    for event in events:
        if blocks:
            blocks.append(pandoc_horizontalrule())
        blocks.extend(pandoc_blocks_from_event(event))

    pandoc_to_markdown(blocks, fp)
