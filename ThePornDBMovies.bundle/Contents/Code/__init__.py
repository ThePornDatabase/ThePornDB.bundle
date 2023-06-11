import re
import string
import urllib
from dateutil.parser import parse

API_BASE_URL = 'https://api.metadataapi.net'
API_SEARCH_URL = API_BASE_URL + '/movies?parse=%s&hash=%s'
API_MOVIE_URL = API_BASE_URL + '/movies/%s'
API_SITE_URL = API_BASE_URL + '/sites/%s'

ID_REGEX = r'(:?.*https\:\/\/api\.metadataapi\.net\/movies\/)?(?P<id>[0-9a-z]{8}\-[0-9a-z]{4}\-[0-9a-z]{4}\-[0-9a-z]{4}\-[0-9a-z]{12})'


def Start():
    HTTP.ClearCache()
    HTTP.CacheTime = CACHE_1MINUTE * 20
    HTTP.Headers['User-Agent'] = 'ThePornDBMovies.bundle'
    HTTP.Headers['Accept-Encoding'] = 'gzip'


def ValidatePrefs():
    Log.Debug('ValidatePrefs')


def GetJSON(url):
    headers = {
        'User-Agent': 'ThePornDBMovies.bundle',
    }

    if Prefs['personal_api_key']:
        headers['Authorization'] = 'Bearer %s' % Prefs['personal_api_key']

    return JSON.ObjectFromURL(url, headers=headers)


class ThePornDBMoviesAgent(Agent.Movies):
    name = 'ThePornDB Movies'
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
        if media.year:
            search_year = str(media.year)
        else:
            search_year = ''
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
            if search_year:
                title = title + " " + search_year
                Log('[TPDB Agent] Searching with Year: `%s`' % title)
            else:
                Log('[TPDB Agent] Searching: `%s`' % title)
            if title_is_id:
                uri = API_MOVIE_URL % (urllib.quote(title_is_id.group("id")))
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
                movie_id = search_result['id']

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

                score = 100 - Util.LevenshteinDistance(title, search_result['title'].lower())
                if debug:
                    Log.Debug('[TPDB Agent] Lev Distance: (Search) "%s" to (Found) "%s" is %i' % (title, search_result['title'].lower(), score))
                title = string.capwords(title)
                if debug: Log.Debug('[TPDB Agent] Found Result: `%s` Studio: `%s` (%i)' % (search_result['title'], search_result['site']['name'], score))
                results.Append(MetadataSearchResult(id=movie_id, name=name, year=year, lang='en', score=score))

            results.Sort('score', descending=True)
        else:
            Log.Debug('[TPDB Agent] No results found for: %s' % title)

        return results

    def update(self, metadata, media, lang):
        uri = API_MOVIE_URL % metadata.id

        try:
            json_obj = GetJSON(uri)
        except:
            json_obj = None

        if json_obj:
            movie_data = json_obj['data']
            metadata.content_rating = 'XXX'

            metadata.title = movie_data['title']
            if 'site' in movie_data and movie_data['site']:
                metadata.studio = movie_data['site']['name']
            metadata.summary = movie_data['description']
            metadata.tagline = movie_data['site']['name']

            date_object = parse(movie_data['date'])
            if date_object:
                metadata.originally_available_at = date_object
                metadata.year = metadata.originally_available_at.year

            # Collections
            metadata.collections.clear()
            collections = []

            if 'site' in movie_data and movie_data['site']:
                if Prefs['collections_from_site']:
                    if Prefs['collection_site_prefix']:
                        site_collection = Prefs['collection_site_prefix'] + movie_data['site']['name']
                    else:
                        site_collection = movie_data['site']['name']
                    if debug: Log.Debug('[TPDB Agent] Writing Studio Collection: %s' % site_collection)
                    collections.append(site_collection)

                site_id = movie_data['site']['id']

            for collection in collections:
                if debug: Log.Debug('[TPDB Agent] Adding Collection: %s' % collection)
                metadata.collections.add(collection)

            # Genres
            metadata.genres.clear()
            if 'tags' in movie_data:
                for tag in movie_data['tags']:
                    metadata.genres.add(tag['name'])
                    if Prefs["CreateAllTagCollectionTags"]:
                        if debug:
                            Log.Debug("Adding Tag Collection: " + tag["name"])
                        metadata.collections.add(tag["name"])

            # Actors
            metadata.roles.clear()
            for performer in movie_data['performers']:
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
                metadata.posters[movie_data['posters']['large']] = Proxy.Media(HTTP.Request(movie_data['posters']['large']).content)
            except:
                Log.Debug('[TPDB Agent] Unable to retrieve poster image from TPDB: %s' % movie_data['posters']['large'])

            try:
                metadata.art[movie_data['background']['large']] = Proxy.Media(HTTP.Request(movie_data['background']['large']).content)
            except:
                Log.Debug('[TPDB Agent] Unable to retrieve background image from TPDB: %s' % movie_data['background']['large'])

        return metadata


def cleanup(text):
    text = urllib.unquote(text)
    if debug: Log.Debug('[TPDB Agent] Cleanup text: %s' % text)
    if Prefs['filepath_cleanup_enable'] and Prefs['filepath_cleanup']:
        replacetext = Prefs['filepath_replace']
        if not replacetext:
            replacetext = ""
        substrings = Prefs['filepath_cleanup'].split("|")
        if debug: Log.Debug('[TPDB Agent] Substitute string: %s' % Prefs['filepath_cleanup'])
        if debug: Log.Debug('[TPDB Agent] Substitute Title Text: %s' % text)
        for substring in substrings:
            Log.Debug('[TPDB Agent] Substitution Instance: %s' % substring)
            text = re.sub(substring, replacetext, text, re.IGNORECASE)
        text = text.replace("  ", " ").strip()
    if debug: Log.Debug('[TPDB Agent] Cleaned Title: %s' % text)

    return text
