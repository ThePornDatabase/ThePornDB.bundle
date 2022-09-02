import re
import urllib
from dateutil.parser import parse

API_BASE_URL = 'https://api.metadataapi.net'
API_SEARCH_URL = API_BASE_URL + '/movies?q=%s&hash=%s'
API_MOVIE_URL = API_BASE_URL + '/movies/%s'
API_SITE_URL = API_BASE_URL + '/sites/%s'
API_PERFORMER_URL = API_BASE_URL + '/performers/%s'
INITIAL_SCORE = 100

DEBUG = Prefs['debug']
if DEBUG:
  Log('Agent debug logging is enabled!')
else:
  Log('Agent debug logging is disabled!')

def Start():
    HTTP.ClearCache()
    HTTP.CacheTime = CACHE_1MINUTE * 20
    HTTP.Headers['User-Agent'] = 'ThePornDBMovies.bundle'
    # ~ HTTP.Headers['Accept-Encoding'] = 'gzip'


def ValidatePrefs():
    Log.Debug('ValidatePrefs')


def GetJSON(url):
    headers = {
        'User-Agent': 'ThePornDBMovies.bundle',
    }

    if Prefs['personal_api_key']:
        headers['Authorization'] = 'Bearer %s' % Prefs['personal_api_key']

    return JSON.ObjectFromURL(url, headers=headers)


class TPDBMoviesAgent(Agent.Movies):
    name = 'ThePornDB Movies'
    languages = [Locale.Language.English]
    accepts_from = ['com.plexapp.agents.localmedia', 'com.plexapp.agents.lambda', 'com.plexapp.agents.xbmcnfo']
    contributes_to = ['com.plexapp.agents.none']
    primary_provider = True

    def search(self, results, media, lang):
        good_score = int(Prefs['good_score'])
        if not good_score:
            good_score = 90

        open_hash = ''
        if media.openSubtitlesHash and Prefs['oshash_matching_enable']:
            open_hash = media.openSubtitlesHash

        title = media.name
        if media.filename and Prefs['match_by_filepath_enable']:
            title = urllib.unquote(media.filename)
            if Prefs['filepath_cleanup_enable'] and Prefs['filepath_cleanup']:
                title = re.sub(Prefs['filepath_cleanup'], '', title)

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
            if DEBUG: Log("Results Found:")
            if DEBUG: Log(search_results)

            for search_result in search_results:
                movie_id = search_result['id']
                name = search_result['title']
                score = INITIAL_SCORE - Util.LevenshteinDistance(title.lower(), name.lower())
                if 'site' in search_result and search_result['site']:
                    name = '%s   [%s]' % (search_result['title'], search_result['site']['name'])
                date = parse(search_result['date'])
                year = date.year if date else None
                resultstring = "Result Found: {} {} ({})  Score: {}".format(str(movie_id), name, str(year), score)
                Log(resultstring)
                if score >= good_score:
                    results.Append(MetadataSearchResult(id = str(movie_id), name = name, year = str(year), lang = 'en', score = score))

        results.Sort('score', descending=True)
        return results

    def update(self, metadata, media, lang):
        uri = API_MOVIE_URL % metadata.id

        try:
            json_obj = GetJSON(uri)
        except:
            json_obj = None

        if json_obj:
            scene_data = json_obj['data']
            Log(scene_data)
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

            if 'site' in scene_data and scene_data['site']and Prefs['collections_from_site']:
                if DEBUG: Log("Adding movie to collection: %s" % scene_data['site'])
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
                        if DEBUG: Log("Adding movie to studio collection: %s" % site_data['name'])
                        collections.append(site_data['name'])

            for collection in collections:
                metadata.collections.add(collection)

            # Genres
            metadata.genres.clear()
            if 'tags' in scene_data:
                for tag in scene_data['tags']:
                    if DEBUG: Log("Found movie tag: %s" % tag['name'])
                    metadata.genres.add(tag['name'])

            # Actors
            metadata.roles.clear()
            for performer in scene_data['performers']:
                role = metadata.roles.new()
                performerSlug = performer['name']
                performerSlug = performerSlug.lower().replace(" ", "-")
                uri = API_PERFORMER_URL %performerSlug
                try:
                    performer_data = GetJSON(uri)
                except:
                    performer_data = None

                if performer_data:
                    performer_data = performer_data['data']
                    # role.role = performer['name']
                    if DEBUG: Log('Adding actor: %s' % role.name)
                    role.name = performer_data['name']
                    role.photo = performer_data['image']
                else:
                    if DEBUG: Log('Adding actor, but no image available: %s' % role.name)
                    role.name = performer['name']
                Log.Debug('[TPDB Agent] Adding actor: %s' % role.name)

            metadata.posters[scene_data['front']] = Proxy.Media(HTTP.Request(scene_data['front']).content)
            if scene_data['back'] and Prefs['use_back_image']:
                metadata.art[scene_data['back']] = Proxy.Media(HTTP.Request(scene_data['back']).content)

        return metadata
