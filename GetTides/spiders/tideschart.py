#!/usr/bin/env python
"""
A spider to scrape tide times from http://tideschart.com/.
"""

# Standard modules
import datetime
import os
import re
from enum import Enum
from typing import Tuple

# Third-party modules
import scrapy

TIDESCHART_WEB_SITE = 'http://tideschart.com/'
DALGETY_BAY_URL = 'United-Kingdom/Scotland/Edinburgh/Dalgety-Bay-Beach'

# Regex to parse tide state, tide time and height from:
# <td class="tide-d"> 3:11pm<div><i>▼</i> 1.54 m</div></td>
# (also, a valid tide height may have no decimal place, e.g. '5 m')
# E.g.:
#   match.group(1) will contain 'tide-d'
#   match.group(2) will contain '3:11pm'
#   match.group(3) will contain '1.54 m'
re_get_info_from_tide = re.compile('<td class="(tide-[du])">' + \
                                   '[ ]*([0-9]+:[0-9]+[apm]+)' + \
                                   '<div><i>[▼▲]</i>[ ]*([0-9]+[.0-9]* m)</div></td>')


class OrdinalNum(Enum):
    '''
    Enumeration to provide easy access to ordinal numbers to identify a tide's
    order within a day's tides.
    '''
    FIRST = "1st"
    SECOND = "2nd"
    THIRD = "3rd"
    FOURTH = "4th"

    def __str__(self):
        return str(self.value)

    def next(self):
        '''
        Return the enumeration representing the next ordinal number.
        '''
        cls = self.__class__
        members = list(cls)
        index = members.index(self) + 1
        if index >= len(members):
            index = 0
        return members[index]
# end class OrdinalNum


class TideschartSpider(scrapy.Spider):
    """
    Scrapy Spider class implementing the tides chart spider.
    """
    name = 'tideschart'
    allowed_domains = ['tideschart.com']

    # Once using Python 3.8 the pylint warning keyword-arg-before-vararg generted
    # by __init__ can be fixed using the positional-only argument marker '/'
    # and the pylint disable removed
    # (see https://docs.python.org/3/glossary.html#term-parameter)
    # pylint: disable=keyword-arg-before-vararg
    def __init__(self,
                 save_page: str = 'False',
                 tide_url: str = DALGETY_BAY_URL,
                 *args, **kwargs):
        # To stop pylint super-with-arguments refactoring message
        #   super(TideschartSpider, self).__init__(*args, **kwargs)
        # changed to following
        super().__init__(*args, **kwargs)

        # Convert save_page arg from str to bool
        self.save_page = save_page.lower() == 'true'
        self.tide_url = TIDESCHART_WEB_SITE + tide_url

    def start_requests(self):
        yield scrapy.Request(self.tide_url, self.parse)

    def parse(self, response: scrapy.http.TextResponse, **kwargs):
        '''
        Override :meth:`scrapy.Spider.parse` accepting the scraped webpage
        in response object (see
        https://docs.scrapy.org/en/latest/topics/request-response.html#response-subclasses)
        '''
        scrape_time = datetime.datetime.now()
        self._save_webpage(scrape_time, response)

        # Provide meta data about scrape - will be 1st entry in produced output
        yield {
            'meta_tide_url': self.tide_url,
            'meta_tide_location': self.tide_url.rsplit('/', 1)[1].replace('-', ' '),
            'meta_scrape_time': scrape_time.strftime("%Y-%m-%dT%H:%M:%S")
        }

        # tide_list is used to store a consequtive list of the scraped tides
        tide_list = []

        # Tides webpage contains tides for 7 days (day 1 is today)
        for day_id in range(1, 8):
            date_str, day_data = TideschartSpider._get_day_data(scrape_time, day_id, response)

            # Get all tides for today - 2 = 1st tide, 3 = 2nd tide, 4 = 3rd tide, ...
            scrape_tide_data = []
            # To add to calendar event the number of the tide in the day keep
            # a running total
            tide_num_in_day = OrdinalNum.FIRST
            for tide_seq in range(2, 6):
                # A tide can be either low (tide-d) or high (tide-u) - we don't
                # know which before we look so we look for both
                for tide_state in ['tide-d', 'tide-u']:
                    this_tide = response.xpath(
                        f'//tr[(((count(preceding-sibling::*) + 1) = {day_id}) and parent::*)]' \
                        '//*[contains(concat( " ", @class, " " ), ' \
                            f'concat( " ", "{tide_state}", " " )) ' \
                            'and (((count(preceding-sibling::*) + 1) = ' \
                            f'{tide_seq}) and parent::*)]').get()
                    if this_tide is None:
                        continue
                    scrape_tide_data.append(this_tide)
                    tide_time, tide_is_high, tide_height = \
                        TideschartSpider._extract_tide_info(this_tide)
                    tide_list.append({
                        'date_time': date_str + "T" + tide_time,
                        'number': str(tide_num_in_day),
                        'is_high': tide_is_high,
                        'height': tide_height
                    })

                # Progress to next tide in the day
                tide_num_in_day = tide_num_in_day.next()

            # Add add all data for this day to scraped data
            yield {
                'date': date_str,
                'scrape_day': day_data,
                'scrape_tides': scrape_tide_data
            }

        yield{
            'tide_list': tide_list
        }
    # end parse()

    def _save_webpage(self, scrape_time: datetime.datetime, response) -> None:
        '''
        If user has requested the scraped webpage to be saved to local file
        write body of response to file in `data` directory if this is present,
        otherwise in current directory. File name is created from name of tide
        location and time page was scraped.

        :param scrape_time: used to create filename
        :type scrape_time: str
        :param response: as passed as arg to `:meth:parse`
        '''
        if self.save_page:
            # Create filename from part of URL containing name of tide location
            filename = self.tide_url.rsplit('/', 1)[-1] + '_' + \
                scrape_time.strftime("%Y-%m-%dT%H:%M:%S") + '.html'
            if os.path.isdir('data'):
                filename = 'data/' + filename
            with open(filename, 'wb') as web_page:
                web_page.write(response.body)
            self.log(f'Webpage saved to file {filename}')
    # end _save_webpage()

    @staticmethod
    def _get_day_data(scrape_time: datetime.datetime,
                      day_id: int, response) -> Tuple[str, str]:
        '''
        From the scraped webpage calculate the date information of the
        requested day.

        :param scrape_time: used to calculate the date relating to `day_id`
        :type scrape_time: str
        :param day_id: used to calculate the date of tides by _adding_ to `scrape_time`
        :type day_id: int

        :return: Tuple containing 2 items:
                    1. Date of tide in YYYY-MM-DD format
                    2. Tides _day_ data as scraped, e.g.:
                        "<td class=\"day\">29 Sat</td>"
        :rtype: (str, str)
        '''
        # Calculate date of tides
        date = scrape_time + datetime.timedelta(days=day_id-1)
        date_str = date.strftime("%Y-%m-%d")

        day_data = response.xpath(
            f'//tr[(((count(preceding-sibling::*) + 1) = {day_id}) and parent::*)]' \
            '//*[contains(concat( " ", @class, " " ), concat( " ", "day", " " )) ]').get()

        return date_str, day_data
    # end _get_day_data()

    @staticmethod
    def _extract_tide_info(tide_data: str) -> Tuple[str, bool, str]:
        '''
        From tide table `tide` entry parse tide time, tide state and tide height.
        A tide table `tide` entry (low tide) has format::

            <td class="tide-d"> 3:11pm<div><i>▼</i> 1.54 m</div></td>

        Returns:
            str: tide time.
            bool: `True` if tide is a **high** tide, otherwise `False`
            str: tide height in metres
        '''
        tide_info_p = re_get_info_from_tide.match(tide_data)
        try:
            assert tide_info_p is not None
        except AssertionError as exc:
            exc_msg = f"Cannot parse tide information from '{tide_data}'"
            raise RuntimeError(exc_msg) from exc
        try:
            state = tide_info_p.group(1)
            time_raw = tide_info_p.group(2)
            height_raw = tide_info_p.group(3)
        except AttributeError as exc:
            exc_msg = f"Cannot parse tide information from '{tide_data}'"
            raise RuntimeError(exc_msg) from exc

       # Is the tide state high or low?
        if state == 'tide-u':
            is_high = True
        elif state == 'tide-d':
            is_high = False
        else:
            exc_msg = f"Cannot determine tide state from '{state}' parsed from: " + \
                      f"'{tide_data}'. Expected either 'tide-u' or 'tide-d'"
            raise RuntimeError(exc_msg)

        # Translate tide time from am/pm to 24hr clock
        time_12h = datetime.datetime.strptime(time_raw, "%I:%M%p")
        time = time_12h.strftime("%H:%M:%S")

        # Remove space between tide height digits and units,
        # e.g. "5.2 8m" becomes "5.28m"
        height = height_raw.replace(' ', '')

        return (time, is_high, height)
    # end extract_tide_info()

# end class TideschartSpider
