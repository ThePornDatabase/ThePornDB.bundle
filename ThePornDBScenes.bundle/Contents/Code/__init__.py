import re
import urllib
from dateutil.parser import parse

API_BASE_URL = 'https://api.metadataapi.net'
API_SEARCH_URL = API_BASE_URL + '/scenes?q=%s&hash=%s'
API_SCENE_URL = API_BASE_URL + '/scenes/%s'
API_SITE_URL = API_BASE_URL + '/sites/%s'
INITIAL_SCORE = 100


def Start():
    HTTP.ClearCache()
    HTTP.CacheTime = CACHE_1MINUTE * 20
    HTTP.Headers['User-Agent'] = 'ThePornDB.bundle'
    HTTP.Headers['Accept-Encoding'] = 'gzip'


def ValidatePrefs():
    Log.Debug('ValidatePrefs')


def GetJSON(url):
    headers = {
        'User-Agent': 'ThePornDB.bundle',
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

    def search(self, results, media, lang):
        open_hash = ''
        if media.items[0].parts[0].openSubtitleHash and Prefs['oshash_matching_enable']:
            open_hash = media.items[0].parts[0].openSubtitleHash
        
        title = media.name
        filename = re.search('.*[\\\/](.*)', media.items[0].parts[0].file).group(1)
        filename = re.search('(.*)\.\w{3,4}', filename).group(1)
        if filename and Prefs['match_by_filepath_enable']:
            title = urllib.unquote(filename)
            if Prefs['filepath_cleanup_enable'] and Prefs['filepath_cleanup']:
                regexes = Prefs['filepath_cleanup'].split(",")
                Log('[TPDB Agent] Regexes Passed: `%s`' % Prefs['filepath_cleanup'])
                Log('[TPDB Agent] Title before Regex: `%s`' % title)
                for regex in regexes:
                    try:
                        regexcompile = re.compile(regex, re.IGNORECASE)
                        if re.search(regexcompile, title):
                            Log('[TPDB Agent] Stripping Regex from Title: `%s`' % regex)
                            title = regexcompile.sub("", title).strip()
                    except re.error:
                        Log('[TPDB Agent] Invalid Regex supplied: `%s`' % regex)
                Log('[TPDB Agent] Title after Regex: `%s`' % title)                
                
        if Prefs['rewrite_season_episode']:
            if re.search(' ([sS]\d+[eE]\d+) ', title) or re.search(' ([sS]\d+[eE]\d+) ?', title):
                titlesearch = re.search('(.* [sS]\d+)([eE]\d+ ?.*)', title)
                title = titlesearch.group(1) + ":" + titlesearch.group(2)

        search_results = []
        if title:
            Log('[TPDB Agent] Searching: `%s`' % title)
            uri = API_SEARCH_URL % (urllib.quote(title), open_hash)
            try:
                json_obj = GetJSON(uri)
            except:
                json_obj = None

            if json_obj:
                search_results = json_obj['data']

        if search_results:
            for idx, search_result in enumerate(search_results):
                scene_id = search_result['id']
                name = search_result['title']
                if 'site' in search_result and search_result['site']:
                    name = '%s: %s' % (search_result['site']['name'], search_result['title'])
                date = parse(search_result['date'])
                year = date.year if date else None
                score = INITIAL_SCORE - Util.LevenshteinDistance(title.lower(), name.lower())

                results.Append(MetadataSearchResult(id=scene_id, name=name, year=year, lang='en', score=score))
            results.Sort('score', descending=True)

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
                collections.append(scene_data['site']['name'])

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
                        collections.append(site_data['name'])

            for collection in collections:
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
                # role.role = performer['name']
                role.name = performer['name']
                role.photo = performer['image']
                Log.Debug('[TPDB Agent] Adding actor: %s' % role.name)

            metadata.posters[scene_data['posters']['large']] = Proxy.Media(HTTP.Request(scene_data['posters']['large']).content)
            metadata.art[scene_data['background']['large']] = Proxy.Media(HTTP.Request(scene_data['background']['large']).content)

            if Prefs['custom_title_enable']:
                data = {
                    'title': metadata.title,
                    'actors': ', '.join([actor.name.encode('ascii', 'ignore') for actor in metadata.roles]),
                    'studio': metadata.studio,
                    'series': ', '.join(set([collection.encode('ascii', 'ignore') for collection in metadata.collections if collection not in metadata.studio])),
                }

                metadata.title = Prefs['custom_title'].format(**data)

        return metadata
