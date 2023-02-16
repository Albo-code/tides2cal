.. tides2cal documentation master file, created by
   sphinx-quickstart on Sat Jun 18 20:33:40 2022.

tides2cal documentation
=======================

Python module using web spider to scrape tidal data and add *high* and *low*
tide events to a Google calendar.

Web scraper uses the `Scrapy`_ web scraping framework to get tidal data from
`www.tideschart.com`_. Scraped data is saved to a `.json` file and used to
create Google calendar events for each *high* and *low* tide over the next
7 days (number of days of tidal data avaiable on `www.tideschart.com`_).

.. _scrapy: https://scrapy.org/
.. _www.tideschart.com: https://www.tideschart.com/

Python virtual environment creation
===================================
To create a Python virtual environment containing packages required to run
the Python scraper and build this documentation::

   python3 -m venv tides2cal_venv
   source tides2cal_venv/bin/activate
   pip install -U pip
   pip install -U pylint -U Scrapy -U sphinx -U sphinx_rtd_theme

To add packages necessary to run the Python code to add Google calendar events
install the following::

   pip install -U plac -U google-api-python-client -U google-auth-oauthlib

Scrape tidal data
=================
In active Python virtual environment::

   scrapy crawl tideschart -O data/tides_$(date -d "today" +"%Y-%m-%dT%H%M").json \
   -a save_page=True

Above stores scraped data in .json file and also saves the `www.tideschart.com`_
web page the data was obtained from as the ``-a save_page=True`` option was
specified.

Add tide events to Google calendar
===================================
In active Python virtual environment::

   python AddEvents/add_cal_events.py -t <path_to_auth_token>.json \
   -j data/tides_<timestamp>.json

Modify above to:

 * ``-t`` option: supply path to file containing user's Google calendar access
   refresh tokens (file created automatically when the authorization flow
   and completes for the first time).
 * ``-j`` option: provide name of file created by call to ``scrapy crawl tideschart``,
   see above.

For further information use the ``-h, --help`` option.

.. toctree::
   :maxdepth: 2
   :caption: API:

   tideschart.rst
   add_cal_events.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
