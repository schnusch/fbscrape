# fbscrape

Scrape events from Facebook and convert them to iCalendar.

## -c/--cookies

Currently Facebook login is not implemented therefore you have to provide
session cookies.

The cookie file should look like this:

```json
[ {"name": "c_user", "value": "..."}
, {"name": "xs",     "value": "..."}
]
```

To obtain the cookie's values navigate to <https://mbasic.facebook.com/>, log in,
open Firefox's *Web Developer Tools* (by pressing `Ctrl+Shift+I`), go to
*Storage*, then *Cookies* and copy the value of these two cookies.
