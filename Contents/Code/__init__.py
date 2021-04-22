import re
import urllib
from dateutil.parser import parse

API_SEARCH_URL = 'https://api.metadataapi.net/scenes?parse=%s&hash=%s'
API_SCENE_URL = 'https://api.metadataapi.net/scenes/%s'


def Start():
    HTTP.ClearCache()
    HTTP.CacheTime = CACHE_1MINUTE * 20
    HTTP.Headers['User-agent'] = 'ThePornDB.bundle'
    HTTP.Headers['Accept-Encoding'] = 'gzip'


def ValidatePrefs():
    Log('ValidatePrefs function call')


def GetJSON(url):
    http_headers = {
        'Authorization': '',
        'User-agent': 'ThePornDB.bundle'
    }

    if Prefs['personal_api_key']:
        http_headers['Authorization'] = 'Bearer ' + Prefs['personal_api_key']

    return JSON.ObjectFromURL(url, headers=http_headers, sleep=1.0)


class ThePornDBAgent(Agent.Movies):
    name = 'ThePornDB'
    languages = [Locale.Language.English]
    accepts_from = ['com.plexapp.agents.localmedia']
    primary_provider = True

    def search(self, results, media, lang):
        title = getSearchTitle(media.name)

        Log('*******MEDIA TITLE****** ' + str(title))

        # Search for year
        year = media.year
        if media.primary_metadata is not None:
            year = media.primary_metadata.year

        openHash = None
        if media.openSubtitlesHash:
            openHash = media.openSubtitlesHash

        if media.filename:
            uri = API_SEARCH_URL % (media.filename, openHash)

            try:
                json_obj = GetJSON(uri)
            except:
                json_obj = None

            if json_obj:
                for release in json_obj['data']:
                    name = release['site']['name'] + ': ' + release['title']
                    results.Append(MetadataSearchResult(id=release['id'], name=name, year=release['date'], lang='en', score=100))

        uri = API_SEARCH_URL % (urllib.quote(title), openHash)

        try:
            json_obj = GetJSON(uri)
        except:
            json_obj = None

        if json_obj:
            for release in json_obj['data']:
                name = release['site']['name'] + ': ' + release['title']
                results.Append(MetadataSearchResult(id=release['id'], name=name, year=release['date'], lang='en', score=50))

        return results

    def update(self, metadata, media, lang):
        uri = API_SCENE_URL % metadata.id

        try:
            json_obj = GetJSON(uri)
        except:
            json_obj = None

        if json_obj:
            metadata.title = json_obj['data']['title']
            metadata.studio = json_obj['data']['site']['name']
            metadata.summary = json_obj['data']['description']
            # metadata.tagline = json_obj['data']['site']['name']

            metadata.collections.clear()
            metadata.collections.add(json_obj['data']['site']['name'])

            # Genres
            metadata.genres.clear()
            if 'tags' in json_obj['data']:
                for tag in json_obj['data']['tags']:
                    metadata.genres.add(tag['tag'])

            # Actors
            metadata.roles.clear()
            for performer in json_obj['data']['performers']:
                role = metadata.roles.new()
                # role.role = performer['name']
                role.name = performer['name']
                role.photo = performer['image']
                Log.Debug('[TPDB Agent] Adding actor: %s' % role.name)

            metadata.posters[json_obj['data']['posters']['large']] = Proxy.Media(HTTP.Request(json_obj['data']['posters']['large']).content)
            metadata.art[json_obj['data']['background']['large']] = Proxy.Media(HTTP.Request(json_obj['data']['background']['large']).content)
            metadata.content_rating = 'XXX'

            date_object = parse(json_obj['data']['date'])
            metadata.originally_available_at = date_object
            metadata.year = metadata.originally_available_at.year

            if Prefs['custom_title_enable']:
                data = {
                    'title': metadata.title,
                    'actors': ', '.join([actor.name.encode('ascii', 'ignore') for actor in metadata.roles]),
                    'studio': metadata.studio,
                    'series': ', '.join(set([collection.encode('ascii', 'ignore') for collection in metadata.collections if collection not in metadata.studio])),
                }

                metadata.title = Prefs['custom_title'].format(**data)

        return metadata


def getSearchTitle(title):
    trashTitle = (
        'RARBG', 'COM', r'\d{3,4}x\d{3,4}', 'HEVC', r'H\d{3}', 'AVC', r'\dK',
        r'\d{3,4}p', 'TOWN.AG_', 'XXX', 'MP4', 'KLEENEX', 'SD', 'HD',
        'KTR', 'IEVA', 'WRB', 'NBQ', 'ForeverAloneDude', r'X\d{3}', 'SoSuMi',
    )

    title = re.sub(r'[^a-zA-Z0-9#&, ]', ' ', title)
    for trash in trashTitle:
        title = re.sub(r'\b%s\b' % trash, '', title, flags=re.IGNORECASE)

    title = ' '.join(title.split())

    return title
