'''
Read JSON file produced by tideschart scrapper and create the Google calendar
tide events.

The Google calendar interfacing code is modified version of example from
https://developers.google.com/calendar/quickstart/python and uses the
Google client library for Python. This is installed using pip::

    pip install -U plac google-api-python-client google-auth-httplib2 google-auth-oauthlib

On first execution of this module you will be prompted to grant access to only
calendars owned by you. The Google authentication *scope* used by the modules is::

    https://www.googleapis.com/auth/calendar.events.owned

The JSON file produced by the tideschart scrapper contains a list of dictionaries.

The dictionary in index ``[0]`` of the list contains meta data about the scrape.
This is used to create the tide calendar event *description* entry. E.g::

    [0]: {'meta_tide_url': 'http://tideschart.com/United-Kingdom/Scotland/
                                              Edinburgh/Dalgety-Bay-Beach',
          'meta_tide_location': 'Dalgety Bay Beach',
          'meta_scrape_time': '2021-06-10T21:36:02'}

In indices ``[1]`` to ``[7]`` are dictionaries containing the the scrapped data
of the tides for the next 7 days, i.e. index ``[1]`` will contain the tide
informaiton for the day the data was scraped, index ``[7]`` for the 7th day from
the day the data was scrapped. E.g.::

    [1]: {'date': '2021-06-10',
          'scrape_day': '<td class="day">10 Thu</td>',
          'scrape_tides': ['<td class="tide-u"> 3:32am<div><i>▲</i> 5.28 m</div></td>',
                           '<td class="tide-d"> 9:11am<div><i>▼</i> 1.22 m</div></td>',
                           '<td class="tide-u"> 3:47pm<div><i>▲</i> 5.2 m</div></td>',
                           '<td class="tide-d"> 9:21pm<div><i>▼</i> 1.28 m</div></td>']}

Index ``[8]`` contains a dictionary with the single key ``tide_list`` that is a
list of dictionaries, each containing a tide's details in correct format for a
tide calendar event. E.g.::

    [8]: {'tide_list': [{'date_time': '2021-06-10T03:32:00',
                         'number': '1st',
                         'is_high': True,
                         'height': '5.28m'},
                        {date_time': '2021-06-10T09:11:00',
                         'number': '2nd',
                         'is_high': False,
                         'height': '1.22m'},
                        {'date_time': '2021-06-10T15:47:00',
                         'number': '3rd',
                         'is_high': True,
                         'height': '5.2m'},
                        {'date_time': '2021-06-10T21:21:00',
                         'number': '4th',
                         'is_high': False,
                         'height': '1.28m'},
                        ...

Only data from list indices ``[0]`` and ``[8]`` are used to create the Google
calendar tide events.

All expample data shown above read from a tideschart scrapper JSON file and
output when this module is called with ``-l debug``.
'''

# Standard imports
import datetime
import json
import logging
import os
import traceback

# Third-parth imports
import plac
from googleapiclient.discovery import build, Resource
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Local imports
from logging_helper import setup_log

# Python logger identifier, following initial set_up, retrieve logger using:
#   log = logging.getLogger(MY_LOGGER)
MY_LOGGER = __name__

# If modifying the scopes, delete the file given in token_json option
SCOPES = ['https://www.googleapis.com/auth/calendar.events.owned']

def do_google_credentials(token_json: str) -> Resource:
    '''
    Do what is necessary to connect to user's Google calender and return
    resource service used to access the calendar.
    If ``token_json`` does not exist or does not contain valid credentials a
    new window is opened prompting you to authorize access to your data.

    :param token_json: Name of file used to store or read from (if previously \
        created) the user's access and refresh tokens.
    :type token_json: str

    :return: googleapiclient.discovery.Resource
    :rtype: Resource
    '''
    log = logging.getLogger(MY_LOGGER)
    creds = None
    # The file token_json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time
    if os.path.exists(token_json):
        log.info("Reading Google credentials from file '%s'", token_json)
        creds = Credentials.from_authorized_user_file(token_json, SCOPES)
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds_file = 'cal_creds.json'
            log.info("Reading app crendtials client secrets from file '%s'",
                     creds_file)
            try:
                flow = InstalledAppFlow.from_client_secrets_file(creds_file,
                                                                 SCOPES)
            except FileNotFoundError as exc:
                raise FileNotFoundError(f"File not found : '{creds_file}'. "
                                        "This error occurs when you have not "
                                        "authorized the desktop application "
                                        "credentials, see "
                                        "https://developers.google.com/calendar/api/quickstart/python#file_not_found_error_for_credentialsjson") \
                                        from exc

            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_json, 'w') as token:
            token.write(creds.to_json())
        log.info("Saving Google credentials to file '%s'", token_json)

    service = build('calendar', 'v3', credentials=creds)

    return service
# end do_google_credentials()

def rm_old_tides(tide_data: list) -> list:
    '''
    From tide_data remove all tides that are in the past in respect to time
    now.

    :param tide_data: List containing all tide data.
    :type tide_data: list

    :return: List of tide data containing only tides in the future.
    :rtype: list
    '''
    log = logging.getLogger(MY_LOGGER)

    future_tides = []

    now_datetime = datetime.datetime.now()
    for tide in tide_data:
        tide_datetime = datetime.datetime.fromisoformat(tide['date_time'])
        if tide_datetime > now_datetime:
            future_tides.append(tide)
            continue
        log.debug("Removing tide in past: %s", str(tide))

    return future_tides
# end rm_old_tides())

def get_cal_tide_times(service: Resource, calendar_id: str, num_days: int=10) -> list:
    '''
    From user's Google calendar read all tide events occurring in the next
    num_days from today and return list containing their start time, i.e.
    the 'tide time' of the event.

    :param service: The googleapiclient.discovery.Resource providing access to \
        user's calendar.
    :type service: Resource
    :param calendar_id: Google calendar id of calendar to retrieve tide time \
        events from.
    :type calendar_id: str
    :param num_days: The number of days to read searching for all tide events.
    :type num_days: int

    :return: List of current tide event start times as strings in Google event \
        data time format.
    :rtype: list
    '''
    log = logging.getLogger(MY_LOGGER)

    now_datetime = datetime.datetime.utcnow()
    until_datetime = now_datetime + datetime.timedelta(days=num_days)
    now = now_datetime.isoformat() + 'Z' # 'Z' indicates UTC time
    until = until_datetime.isoformat() + 'Z'
    log.info("Getting '%s' calendar events from %s until %s", calendar_id, now, until)
    events_result = service.events().list(calendarId=calendar_id, timeMin=now,
                                          timeMax=until, singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])

    # Following debug logging a bit of overkill during normal operation
    # considering info debug immediately after
    #if log.getEffectiveLevel() <= logging.DEBUG:
    #    if not events:
    #        log.debug("No calendar events found in the next %d days", num_days)
    #    else:
    #        log.debug("In the next %d days %d calendar events found:", num_days,
    #                  len(events))
    #        for event in events:
    #            start = event['start'].get('dateTime', event['start'].get('date'))
    #            print("\t" + start, event['summary'])


    tide_events = [e for e in events if 'tide' in e['summary'].lower()]
    if log.getEffectiveLevel() <= logging.INFO:
        if not tide_events:
            log.info("No *tide* calendar events found in the next %d days", num_days)
        else:
            log.info("In the next %d days %d *tide* calendar events found:", num_days,
                     len(tide_events))
            for event in tide_events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                print("\t" + start, event['summary'])

    tide_event_times = []
    for event in tide_events:
        # We're not interested in timezone as scraped tide times do not include
        # timezone so only use string before '+'
        # e.g.    2021-06-05T02:30:00+01:00
        # becomes 2021-06-05T02:30:00
        tide_time = event['start'].get('dateTime').split('+', 1)[0]
        tide_event_times.append(tide_time)

    log.debug("Calendar tide event times: %s", str(tide_event_times))

    return tide_event_times
# end get_cal_tide_times()

def get_new_tide_data(tide_times_in_cal: list, tide_data: list) -> list:
    '''
    Return list of tide data dictionaries containing tides not already in the
    calendar.

    :param tide_times_in_cal: List of tide times already in caledar, list \
        contains only the start time of the calendar event.
    :type tide_times_in_cal: list
    :param tide_data: List of dictionaries containing latest tide data.
    :type tide_data: list

    :return: List of dictionaries containing data of new tides.
    :rtype: list
    '''
    log = logging.getLogger(MY_LOGGER)

    new_tide_data = [td for td in tide_data
                        if td['date_time'] not in tide_times_in_cal]

    log.info("Number of new tides already in calendar = %d",
             (len(tide_data) - len(new_tide_data)))

    if log.getEffectiveLevel() <= logging.DEBUG:
        log.debug("New tide data to be added to calendar:")
        for index, data in enumerate(new_tide_data):
            print(f"[{index}]: {data}")

    return new_tide_data
# end get_new_tide_data()

def get_new_tide_events(scrape_meta: dict, tide_data: list) -> list:
    '''
    Return list of Google calendar events detailing new tide events to be added
    to the calender.

    :param scrape_meta: Meta data about the scrape added to event descriptions.
    :type scrape_meta: dict
    :param tide_data: List of dictionaries containing tide data for which Google \
        calendar events are to be created.
    :type tide_data: list

    :return: List of Google calendar events containing tides to be added to the \
        calendar.
    :rtype: list
    '''
    log = logging.getLogger(MY_LOGGER)

    # The description text of each tide event is the same
    now_datetime = datetime.datetime.now()
    desc_time_str = f"{now_datetime.strftime('%a %d %b %Y')} at " + \
                    f"{now_datetime.strftime('%H:%M')}"
    tide_location = scrape_meta['meta_tide_location']
    tide_url = scrape_meta['meta_tide_url']
    scrape_datetime = datetime.datetime.fromisoformat(scrape_meta['meta_scrape_time'])
    scrape_time_str = f"{scrape_datetime.strftime('%a %d %b %Y')} at " + \
                      f"{scrape_datetime.strftime('%H:%M')}"
    desc_text = f"<b>{tide_location}</b> tide event added by Tides2Cal on {desc_time_str}.<br>" +\
                f"Tide data scrapped on {scrape_time_str} from {tide_url}"

    new_tide_events = []
    for tide in tide_data:
        if tide['is_high']:
            state = 'HIGH'
            color_id = 9 # blue
        else:
            state = 'low'
            color_id = 11 # red
        tide_datetime = datetime.datetime.fromisoformat(tide['date_time'])
        event_end_datetime = tide_datetime + datetime.timedelta(minutes=20)
        event = {
            'summary': f"{tide['number']} tide {state} {tide['height']}",
            'description': desc_text,
            'colorId': color_id,
            'start': {
                'dateTime': f"{tide['date_time']}",
                'timeZone': 'Europe/London',
            },
            'end': {
                'dateTime': f"{event_end_datetime.strftime('%Y-%m-%dT%H:%M:%S')}",
                'timeZone': 'Europe/London',
            }
        }
        new_tide_events.append(event)

    if log.getEffectiveLevel() <= logging.DEBUG:
        log.debug("New tide events to be added to calendar:")
        for index, event in enumerate(new_tide_events):
            print(f"[{index}]: {event}")

    return new_tide_events
# end get_new_tide_events()

def add_cal_tide_events(service: Resource, calendar_id: str, new_tide_events: list) -> None:
    '''
    Add tide event to Google calendar if not already present in calendar.

    :param service: The googleapiclient.discovery.Resource providing access to \
        user's calendar.
    :type service: Resource
    :param calendar_id: Google calendar id of calendar to retrieve tide time \
        events from.
    :type calendar_id: str
    :param new_tide_events: List of new tide calendar events to be added to \
        the calendar.
    :type new_tide_events: list

    :return: None
    '''
    for event in new_tide_events:
        service.events().insert(calendarId=calendar_id, body=event).execute()

# end add_cal_tide_events()

@plac.opt('cal_name', "User's Google calendar name tide events are to be " + \
          "added to.", type=str)
@plac.opt('token_json', "User's Google calendar access and refresh tokens - is " + \
          "created automatically when the authorization flow completes for the " + \
          "first time.", type=str)
@plac.opt('json_in', "Input JSON file containing tide data to be used to " + \
          "create Google calendar events.", type=str)
@plac.opt('read_only', "When False do NOT create new calendar tide events, " + \
          'only read tide and display on screen.', type=bool)
@plac.opt('log', "Set logging level.", type=str,
          choices=['off', 'info', 'debug'])
def main(cal_name: str='primary', token_json: str='cal_token.json',
         json_in: str='tides.json', read_only: bool=False, log: str='off'):
    '''
    Read JSON file produced by scrapper containing tide data and create
    Google calendar tide events.
    '''
    log = setup_log(MY_LOGGER, log)

    log.info("Reading tide data from '%s'", json_in)

    json_data = None
    with open(json_in, 'r') as input_data:
        json_data = json.load(input_data)

    if json_data is None or len(json_data) == 0:
        log.warning("Tide JSON file '%s' is empty - NO tide data %s '%s'", json_in,
                    "events added to calendar", cal_name)
        return

    if log.getEffectiveLevel() <= logging.DEBUG:
        log.debug("Data read from calendar JSON file:")
        for index, data in enumerate(json_data):
            print(f"[{index}]: {data}")

    # Index 8 of the list in the tides JSON data contains the list of tide data
    # dictionaries
    tide_data = json_data[8]['tide_list']

    cal_tide_data = rm_old_tides(tide_data)

    if len(cal_tide_data) == 0:
        log.warning("Tide data file '%s' does not contain any tides %s %s '%s'", json_in,
                    "that are not in the past - NO tide data events added ",
                    "to calendar", cal_name)
        return
    log.info("Tides in past removed from tide data = %d",
             (len(tide_data) - len(cal_tide_data)))

    cal_service = do_google_credentials(token_json)

    cal_tide_times_at_start = get_cal_tide_times(cal_service, cal_name)

    new_tide_data = get_new_tide_data(cal_tide_times_at_start, cal_tide_data)

    new_tide_events = get_new_tide_events(json_data[0], new_tide_data)

    if len(new_tide_events) > 0:
        if not read_only:
            add_cal_tide_events(cal_service, cal_name, new_tide_events)
            print(f"Tides events added to calendar '{cal_name}' = {len(new_tide_events)}")
        else:
            print(f"{__name__} called with --read-only=True - tide events NOT added " +
                  "to calendar.")
            print(f"Without use of --read-only {len(new_tide_events)} new events " +
                  "would be added to calendar, details:")
            for event in new_tide_events:
                print(event)
    else:
        print(f"No new tide events found in '{json_in}' to be added to " +
              f"calendar '{cal_name}'")

# end main()

if __name__ == '__main__':
    try:
        plac.call(main)
    except Exception as exc:
        print("Exception executing " + os.path.basename(__file__) +
              f" main() Exception: {exc}")
        print(traceback.format_exc())

# end-of-file
