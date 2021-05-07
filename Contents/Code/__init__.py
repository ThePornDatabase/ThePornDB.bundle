import re
import urllib
from dateutil.parser import parse

API_BASE_URL = 'https://api.metadataapi.net'
API_SEARCH_URL = API_BASE_URL + '/scenes?parse=%s&hash=%s'
API_SCENE_URL = API_BASE_URL + '/scenes/%s'
API_SITE_URL = API_BASE_URL + '/sites/%s'


def Start():
    HTTP.ClearCache()
    HTTP.CacheTime = CACHE_1MINUTE * 20
    HTTP.Headers['User-agent'] = 'ThePornDB.bundle'
    HTTP.Headers['Accept-Encoding'] = 'gzip'


def ValidatePrefs():
    Log('ValidatePrefs function call')


def GetJSON(url):
    http_headers = {
        'User-agent': 'ThePornDB.bundle',
    }

    if Prefs['personal_api_key']:
        http_headers['Authorization'] = 'Bearer %s' % Prefs['personal_api_key']

    return JSON.ObjectFromURL(url, headers=http_headers)


class ThePornDBAgent(Agent.Movies):
    name = 'ThePornDB'
    languages = [Locale.Language.English]
    accepts_from = ['com.plexapp.agents.localmedia', 'com.plexapp.agents.lambda']
    primary_provider = True

    def search(self, results, media, lang):
        openHash = None
        if media.openSubtitlesHash and Prefs['oshash_matching_enable']:
            openHash = media.openSubtitlesHash

        searchResults = []
        if media.filename:
            filepath = urllib.unquote(media.filename)
            if Prefs['filepath_cleanup_enable']:
                filepath = re.sub(Prefs['filepath_cleanup'], '', filepath)

            Log('[TPDB Agent] Searching: `%s`' % filepath)
            uri = API_SEARCH_URL % (urllib.quote(filepath), openHash)

            try:
                json_obj = GetJSON(uri)
            except:
                json_obj = None

            if json_obj:
                searchResults = json_obj['data']
        elif Prefs['match_by_name_enable']:
            title = media.name

            Log('[TPDB Agent] Searching: `%s`' % title)
            uri = API_SEARCH_URL % (urllib.quote(title), openHash)

            try:
                json_obj = GetJSON(uri)
            except:
                json_obj = None

            if json_obj:
                searchResults = json_obj['data']

        if searchResults:
            score = 100
            for searchResult in searchResults:
                id = '%d' % searchResult['_id']
                name = '%s: %s' % (searchResult['site']['name'], searchResult['title'])
                date = parse(searchResult['date'])
                year = date.year if date else None
                score = score - 1

                results.Append(MetadataSearchResult(id=id, name=name, year=year, lang='en', score=score))

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
            metadata.studio = scene_data['site']['name']
            metadata.summary = scene_data['description']
            # metadata.tagline = scene_data['site']['name']

            date_object = parse(scene_data['date'])
            if date_object:
                metadata.originally_available_at = date_object
                metadata.year = metadata.originally_available_at.year

            # Collections
            metadata.collections.clear()
            collections = [scene_data['site']['name']]

            site_id = scene_data['site']['id']
            network_id = scene_data['site']['network_id']
            if site_id != network_id:
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
