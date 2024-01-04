# -*- coding: utf-8 -*-

import os
import re
import time
import json
import traceback
import urllib
from dateutil.parser import parse

import requests

from _logging import log

# plex debugging
try:
    import plexhints  # noqa: F401
except ImportError:
    pass
else:  # the code is running outside of Plex
    from plexhints.core_kit import Core  # core kit
    from plexhints.log_kit import Log  # log kit
    from plexhints.network_kit import HTTP  # network kit
    from plexhints.object_kit import MetadataSearchResult
    from plexhints.prefs_kit import Prefs  # prefs kit
    from plexhints.parse_kit import JSON, XML  # parse kit
    from plexhints.util_kit import Util  # util kit


API_BASE_URL = 'https://api.metadataapi.net'
API_SEARCH_URL = API_BASE_URL + '/movies?parse=%s&hash=%s'
API_SCENE_URL = API_BASE_URL + '/movies/%s'
API_SITE_URL = API_BASE_URL + '/sites/%s'
API_ADD_TO_COLLECTION_QS_SUFFIX = '?add_to_collection=true'

ID_REGEXES = [
    r'\[theporndbid=(?P<id>.*)\]',
    r'^https://(?:api\.)?metadataapi\.net/movies/(?P<id>.*)$',
]


def json_decode(output):
    """
        Decodes JSON output.
    """
    try:
        return json.loads(output, encoding='UTF-8')
    except AttributeError:
        return None


def make_request(url, headers={}):
    """
        Makes and returns an HTTP request.
        Retries 4 times, increasing  time between each retry.
    """

    # Initialize variables
    response = None
    str_error = None

    sleep_time = 1
    num_retries = 4
    for x in range(0, num_retries):
        log.debug('[TPDB Agent] Requesting GET "%s"' % url)
        try:
            response = requests.get(url, headers=headers, timeout=90, verify=False)
        except Exception as str_error:
            log.error('[TPDB Agent] Failed HTTP Request Attempt #%d: %s' % (x, url))
            log.error('[TPDB Agent] %s' % str_error)

        if str_error:
            time.sleep(sleep_time)
            sleep_time = sleep_time * x
        else:
            break

    return response.content if response else response


def GetJSON(url):
    headers = {
        'User-Agent': 'ThePornDBMovies.bundle',
    }

    if Prefs['personal_api_key']:
        headers['Authorization'] = 'Bearer %s' % Prefs['personal_api_key']

    return json_decode(make_request(url, headers))


def cleanup(text):
    text = urllib.unquote(text)
    log.debug('[TPDB Agent] Cleanup text: "%s"' % text)

    if Prefs['filepath_cleanup_enable'] and Prefs['filepath_cleanup']:
        replace_text = Prefs['filepath_replace']
        if not replace_text:
            replace_text = ''
        substrings = Prefs['filepath_cleanup'].split(',')

        log.debug('[TPDB Agent] Substitute String: "%s"' % Prefs['filepath_cleanup'])
        log.debug('[TPDB Agent] Substitute Title Text: "%s"' % text)

        for substring in substrings:
            log.debug('[TPDB Agent] Substitution Instance: "%s"' % substring)
            text = re.sub(substring, replace_text, text, re.IGNORECASE)

        text = ' '.join(text.split())

    log.debug('[TPDB Agent] Cleaned Title: "%s"' % text)

    return text


def process_search_result(title, search_result, is_id_match):
    scene_id = search_result['id']

    name = search_result['title']
    if 'site' in search_result and search_result['site']:
        name = '%s %s' % (search_result['site']['name'], search_result['title'])

    date = parse(search_result['date'])
    year = date.year if date else None

    if not is_id_match:
        # If the date is in the search string, remove it
        title = title.lower()
        if re.search(r'(\d{4}-\d{2}-\d{2})', title):
            title = re.sub(r'\d{4}-\d{2}-\d{2}', '', title)

        title = ' '.join(title.split())

        score = 100 - Util.LevenshteinDistance(title, name.lower())
    else:
        score = 100

    log.info('[TPDB Agent] Found Result: "%s" Site: "%s" (%i)' % (search_result['title'], search_result['site']['name'], score))

    return MetadataSearchResult(id=scene_id, name=name, year=year, lang='en', score=score)


def get_title_results(media, results, manual):
    open_hash = ''

    if media.items[0].parts[0].openSubtitleHash and Prefs['oshash_matching_enable']:
        open_hash = media.items[0].parts[0].openSubtitleHash

    title = media.name if media.name else media.title
    search_year = str(media.year) if media.year else ''

    log.debug('[TPDB Agent] Plex Title (Not Filename): "%s"' % title)

    if (not manual or not title) and media.filename and Prefs['match_by_filepath_enable']:
        if Prefs['filepath_strip_path_enable']:
            log.debug('[TPDB Agent] Using Filename to Search')

            title = urllib.unquote(media.filename)
            log.debug('[TPDB Agent] Stripping Path & Ext From: "%s"' % title)

            title = os.path.basename(title)
            title = title.rsplit('.', 1)[0]
            log.debug('[TPDB Agent] Ending Search Title: "%s"' % title)

        title = cleanup(title)

    if not title:
        return results

    if search_year:
        search_query = title + ' ' + search_year
        log.info('[TPDB Agent] Searching with Year: "%s"' % search_query)
    else:
        search_query = title
        log.info('[TPDB Agent] Searching: "%s"' % search_query)

    title_is_id = None
    for regex in ID_REGEXES:
        title_is_id = re.search(regex, title)
        if title_is_id:
            break

    if title_is_id:
        uri = API_SCENE_URL % (urllib.quote(title_is_id.group('id')))
    else:
        uri = API_SEARCH_URL % (urllib.quote(search_query), open_hash)

    try:
        json_obj = GetJSON(uri)
    except Exception as e:
        json_obj = None
        log.error('[TPDB Agent] Failed to fetch search results: "%s"' % uri)
        log.error('[TPDB Agent] %s: %s' % (e, traceback.format_exc()))

    if not json_obj:
        return results

    if 'error' in json_obj and json_obj['error']:
        log.error('[TPDB Agent] Server error: %s' % json_obj['error'])
        return results

    search_results = [json_obj['data']] if title_is_id else json_obj['data']
    if not search_results:
        return results

    log.debug('[TPDB Agent] Search Results: "%s"' % search_results)

    for search_result in search_results:
        results.Append(process_search_result(title, search_result, title_is_id))

    return results
