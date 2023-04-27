import re
import string
import urllib
from dateutil.parser import parse

API_BASE_URL = 'https://api.metadataapi.net'
API_SEARCH_URL = API_BASE_URL + '/scenes?parse=%s&hash=%s'
API_SCENE_URL = API_BASE_URL + '/scenes/%s'
API_SITE_URL = API_BASE_URL + '/sites/%s'

ID_REGEX = r'(:?.*https\:\/\/api\.metadataapi\.net\/scenes\/)?(?P<id>[0-9a-z]{8}\-[0-9a-z]{4}\-[0-9a-z]{4}\-[0-9a-z]{4}\-[0-9a-z]{12})'


def Start():
    HTTP.ClearCache()
    HTTP.CacheTime = CACHE_1MINUTE * 20
    HTTP.Headers['User-Agent'] = 'ThePornDBScenes.bundle'
    HTTP.Headers['Accept-Encoding'] = 'gzip'


def ValidatePrefs():
    Log.Debug('ValidatePrefs')


def GetJSON(url):
    headers = {
        'User-Agent': 'ThePornDBScenes.bundle',
    }

    if Prefs['personal_api_key']:
        headers['Authorization'] = 'Bearer %s' % Prefs['personal_api_key']

    return JSON.ObjectFromURL(url, headers=headers)


class ThePornDBScenesAgent(Agent.Movies):
    name = 'ThePornDB Scenes'
    languages = [Locale.Language.English]
    accepts_from = ['com.plexapp.agents.localmedia', 'com.plexapp.agents.lambda', 'com.plexapp.agents.xbmcnfo']
    contributes_to = ['com.plexapp.agents.none']
    primary_provider = True
    global debug
    debug = Prefs['debug_logging']

    def search(self, results, media, lang):
        open_hash = ''
        if media.items[0].parts[0].openSubtitleHash and Prefs['oshash_matching_enable']:
            open_hash = media.items[0].parts[0].openSubtitleHash

        title = media.name
        if debug: Log.Debug('[TPDB Agent] Plex Title (Not Filename): %s' % title)

        if media.filename and Prefs['match_by_filepath_enable']:
            if Prefs['filepath_strip_path_enable']:
                if debug: Log.Debug('[TPDB Agent] Using Filename to Search')
                title = urllib.unquote(media.filename)
                if debug: Log.Debug('[TPDB Agent] Stripping Path & Ext From: %s' % title)
                title = re.sub('.*[\\\/]', '', title)
                title = re.sub('\.\w{3,4}$', '', title)
                if debug: Log.Debug('[TPDB Agent] Ending Search Title: %s' % title)
            title = cleanup(title)

        title_is_id = re.match(ID_REGEX, title)

        search_results = []
        if title:
            Log('[TPDB Agent] Searching: `%s`' % title)
            if title_is_id:
                uri = API_SCENE_URL % (urllib.quote(title_is_id.group("id")))
            else:
                uri = API_SEARCH_URL % (urllib.quote(title), open_hash)

            try:
                json_obj = GetJSON(uri)
            except:
                json_obj = None

            if json_obj:
                search_results = [json_obj['data']] if title_is_id else json_obj['data']

        if search_results:
            if debug: Log.Debug('[TPDB Agent] Search Results: %s' % search_results)
            for idx, search_result in enumerate(search_results):
                scene_id = search_result['id']

                name = search_result['title']
                if 'site' in search_result and search_result['site']:
                    name = '%s %s' % (search_result['site']['name'], search_result['title'])

                date = parse(search_result['date'])
                year = date.year if date else None

                # If the date is in the search string, remove it
                title = title.lower()
                if re.search('(\d{4}-\d{2}-\d{2})', title):
                    title = re.sub('\d{4}-\d{2}-\d{2}', '', title)
                title = title.replace("  ", " ").strip()

                score = 100 - Util.LevenshteinDistance(title, name.lower())
                title = string.capwords(title)
                if debug: Log('[TPDB Agent] Found Result: `%s` Site: `%s` (%i)' % (search_result['title'], search_result['site']['name'], score))
                results.Append(MetadataSearchResult(id=scene_id, name=name, year=year, lang='en', score=score))

            results.Sort('score', descending=True)
        else:
            Log.Debug('[TPDB Agent] No results found for: %s' % title)

        return results

    def update(self, metadata, media, lang):
        uri = API_SCENE_URL % metadata.id

        try:
            json_obj = GetJSON(uri)
        except:
            json_obj = None

        if json_obj:
            scene_data = json_obj['data']
            metadata.content_rating = 'XXX'

            metadata.title = scene_data['title']
            if 'site' in scene_data and scene_data['site']:
                metadata.studio = scene_data['site']['name']
            metadata.summary = scene_data['description']
            # metadata.tagline = scene_data['site']['name']

            date_object = parse(scene_data['date'])
            if date_object:
                metadata.originally_available_at = date_object
                metadata.year = metadata.originally_available_at.year

            # Collections
            metadata.collections.clear()
            collections = []

            if 'site' in scene_data and scene_data['site']:
                if Prefs['collections_from_site']:
                    if Prefs['collection_site_prefix']:
                        site_collection = Prefs['collection_site_prefix'] + scene_data['site']['name']
                    else:
                        site_collection = scene_data['site']['name']
                    if debug: Log.Debug('[TPDB Agent] Writing Site Collection: %s' % site_collection)
                    collections.append(site_collection)

                site_id = scene_data['site']['id']
                network_id = scene_data['site']['network_id']
                if network_id and site_id != network_id and Prefs['collections_from_networks']:
                    uri = API_SITE_URL % network_id

                    try:
                        site_data = GetJSON(uri)
                    except:
                        site_data = None

                    if site_data:
                        site_data = site_data['data']
                        if Prefs['collection_network_prefix']:
                            net_collection = Prefs['collection_network_prefix'] + site_data['name']
                        else:
                            net_collection = site_data['name']
                        if debug: Log.Debug('[TPDB Agent] Writing Network Collection: %s' % net_collection)
                        collections.append(net_collection)

            for collection in collections:
                if debug: Log.Debug('[TPDB Agent] Adding Collection: %s' % collection)
                metadata.collections.add(collection)

            # Genres
            metadata.genres.clear()
            if 'tags' in scene_data:
                for tag in scene_data['tags']:
                    metadata.genres.add(tag['name'])

            # Actors
            metadata.roles.clear()
            for performer in scene_data['performers']:
                role = metadata.roles.new()

                if 'parent' in performer and performer['parent']:
                    role.name = performer['parent']['name']
                else:
                    role.name = performer['name']

                role.role = performer['name']
                role.photo = performer['face']
                if debug: Log.Debug('[TPDB Agent] Adding actor: %s' % role.name)

            if Prefs['custom_title_enable']:
                if debug: Log.Debug('[TPDB Agent] Using custom naming format: %s' % Prefs['custom_title'])

                data = {
                    'title': metadata.title,
                    'actors': ', '.join([actor.name.encode('ascii', 'ignore') for actor in metadata.roles]),
                    'studio': metadata.studio,
                    'series': ', '.join(set([collection.encode('ascii', 'ignore') for collection in metadata.collections if collection not in metadata.studio])),
                }
                metadata.title = Prefs['custom_title'].format(**data)
                if debug: Log.Debug('[TPDB Agent] Resulting Title: %s' % metadata.title)

            try:
                metadata.posters[scene_data['posters']['large']] = Proxy.Media(HTTP.Request(scene_data['posters']['large']).content)
            except:
                Log.Debug('[TPDB Agent] Unable to retrieve poster image from TPDB: %s' % scene_data['posters']['large'])

            try:
                metadata.art[scene_data['background']['large']] = Proxy.Media(HTTP.Request(scene_data['background']['large']).content)
            except:
                Log.Debug('[TPDB Agent] Unable to retrieve background image from TPDB: %s' % scene_data['background']['large'])

        return metadata


def cleanup(text):
    text = urllib.unquote(text)
    if debug: Log.Debug('[TPDB Agent] Cleanup text: %s' % text)
    if Prefs['filepath_cleanup_enable'] and Prefs['filepath_cleanup']:
        replacetext = Prefs['filepath_replace']
        if not replacetext:
            replacetext = ""
        substrings = Prefs['filepath_cleanup'].split(",")
        if debug: Log.Debug('[TPDB Agent] Substitute string: %s' % Prefs['filepath_cleanup'])
        if debug: Log.Debug('[TPDB Agent] Substitute Title Text: %s' % text)
        for substring in substrings:
            Log.Debug('[TPDB Agent] Subsitution Instance: %s' % substring)
            text = re.sub(substring, replacetext, text, re.IGNORECASE)
        text = text.replace("  ", " ").strip()
    if debug: Log.Debug('[TPDB Agent] Cleaned Title: %s' % text)

    return text
