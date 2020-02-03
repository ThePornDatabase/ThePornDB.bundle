import re
import random
import urllib2 as urllib
import urlparse
import json
from dateutil.parser import parse
import pprint

API_SEARCH_URL = 'http://master.metadataapi.net/api/scenes?parse=%s' 
API_SCENE_URL = 'http://master.metadataapi.net/api/scenes/%s'

def any(s):
    for v in s:
        if v:
            return True
    return False

def Start():
    HTTP.ClearCache()
    HTTP.CacheTime = CACHE_1MINUTE*20
    HTTP.Headers['User-agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36'
    HTTP.Headers['Accept-Encoding'] = 'gzip'

def capitalize(line):
    return ' '.join([s[0].upper() + s[1:] for s in line.split(' ')])

def GetJSON(url):

	http_headers = {
		'api-key': ''
	}

	if Prefs['personal_api_key'] and RE_KEY_CHECK.search(Prefs['personal_api_key']):
		http_headers['api-key'] = Prefs['personal_api_key']

	return JSON.ObjectFromURL(url, headers=http_headers, sleep=1.0)

class ThePornDBAgent(Agent.Movies):
    name = 'ThePornDB'
    languages = [Locale.Language.English]
    accepts_from = ['com.plexapp.agents.localmedia']
    primary_provider = True

    def search(self, results, media, lang):
        title = media.name
        if media.primary_metadata is not None:
            title = media.primary_metadata.studio + " " + media.primary_metadata.title

        title = title.replace('"','').replace(":","").replace("!","").replace("[","").replace("]","").replace("(","").replace(")","").replace("&","").replace('RARBG.COM','').replace('RARBG','').replace('180x180','').replace('Hevc','').replace('Avc','').replace('5k','').replace(' 4k','').replace('.4k','').replace('2300p60','').replace('2160p60','').replace('1920p60','').replace('1600p60','').replace('2160p','').replace('1080p','').replace('720p','').replace('480p','').replace('540p','').replace(' XXX',' ').replace('MP4-KTR','').replace('Sexors','').replace('3dh','').replace('Oculus','').replace('Lr','').replace('-180_','').replace('TOWN.AG_','').strip()

        Log('*******MEDIA TITLE****** ' + str(title))

        # Search for year
        year = media.year
        if media.primary_metadata is not None:
            year = media.primary_metadata.year

        uri = (API_SEARCH_URL % (media.filename.replace(' ', '.'))) 
        if media.openSubtitlesHash:
            uri += '&hash=' + media.openSubtitlesHash

        Log(uri)
        try:
		    json_obj = GetJSON(uri)
        except:
		    json_obj = None

        if json_obj:
            for release in json_obj['data']:
                name = release['site']['name'] + ': ' + release['title']
                results.Append(MetadataSearchResult(id=release['id'], name=name, year=release['date'], lang='en', score=100))

    def update(self, metadata, media, lang):
        uri = (API_SCENE_URL % metadata.id) 
        Log(uri)
        
        try:
		    json_obj = GetJSON(uri)
        except:
		    json_obj = None

        if json_obj:
            Log(json.dumps(json_obj))
            metadata.title = json_obj['data']['site']['name'] + ': ' + json_obj['data']['title']
            metadata.studio = json_obj['data']['site']['name']
            metadata.summary = json_obj['data']['description']
            #metadata.tagline = json_obj['data']['site']['name']
           
            metadata.collections.clear()
            metadata.collections.add( json_obj['data']['site']['name'] )

            # Genres
            metadata.genres.clear()
            for tag in json_obj['data']['tags']:
                metadata.genres.add(tag['tag'])

            # Actors
            metadata.roles.clear()
            for performer in json_obj['data']['performers']:
                role = metadata.roles.new()
                role.role = performer['name']
                role.name = performer['name']
                role.photo = performer['image']
                Log.Debug("[TPDB Agent] Adding actor : %s (%s)" %(role.role, role.name))

            metadata.posters[json_obj['data']['poster']] = Proxy.Media(HTTP.Request(json_obj['data']['poster']).content)
            metadata.art[json_obj['data']['background']['large']] = Proxy.Media(HTTP.Request(json_obj['data']['background']['large']).content)
            metadata.content_rating = 'XXX'

            date_object = parse(json_obj['data']['date'])
            metadata.originally_available_at = date_object
            metadata.year = metadata.originally_available_at.year
