# -*- coding: utf-8 -*-


import base64
from dateutil.parser import parse

from _utils import GetJSON, get_title_results, API_SCENE_URL, API_SITE_URL, API_ADD_TO_COLLECTION_QS_SUFFIX, make_request
from _logging import log

# plex debugging
try:
    import plexhints  # noqa: F401
except ImportError:
    pass
else:  # the code is running outside of Plex
    from plexhints.agent_kit import Agent, Media  # agent kit
    from plexhints.core_kit import Core  # core kit
    from plexhints.decorator_kit import handler, indirect, route  # decorator kit
    from plexhints.exception_kit import Ex  # exception kit
    from plexhints.locale_kit import Locale  # locale kit
    from plexhints.log_kit import Log  # log kit
    from plexhints.model_kit import Movie, VideoClip, VideoClipObject  # model kit
    from plexhints.network_kit import HTTP  # network kit
    from plexhints.object_kit import Callback, IndirectResponse, MediaObject, MessageContainer, MetadataItem, MetadataSearchResult, PartObject, SearchResult  # object kit
    from plexhints.parse_kit import HTML, JSON, Plist, RSS, XML, YAML  # parse kit
    from plexhints.prefs_kit import Prefs  # prefs kit
    from plexhints.proxy_kit import Proxy  # proxy kit
    from plexhints.resource_kit import Resource  # resource kit
    from plexhints.shortcut_kit import L, E, D, R, S  # shortcut kit
    from plexhints.util_kit import String, Util  # util kit

    from plexhints.constant_kit import CACHE_1MINUTE, CACHE_1HOUR, CACHE_1DAY, CACHE_1WEEK, CACHE_1MONTH  # constant kit
    from plexhints.constant_kit import ClientPlatforms, Protocols, OldProtocols, ServerPlatforms, ViewTypes, SummaryTextTypes, AudioCodecs, VideoCodecs, Containers, ContainerContents, StreamTypes  # constant kit, more commonly used in URL services

    # extra objects
    from plexhints.extras_kit import BehindTheScenesObject, ConcertVideoObject, DeletedSceneObject, FeaturetteObject, InterviewObject, LiveMusicVideoObject, LyricMusicVideoObject, MusicVideoObject, OtherObject, SceneOrSampleObject, ShortObject, TrailerObject


def Start():
    HTTP.ClearCache()
    HTTP.CacheTime = CACHE_1DAY
    HTTP.Headers['User-Agent'] = 'ThePornDBScenes.bundle'
    HTTP.Headers['Accept-Encoding'] = 'gzip'
    log.separator(msg='ThePornDB Scenes Agent started.', log_level='info')


def ValidatePrefs():
    log.debug('ValidatePrefs called.')


class ThePornDBScenesAgent(Agent.Movies):
    name = 'ThePornDB Scenes'
    languages = [Locale.Language.English]
    accepts_from = ['com.plexapp.agents.localmedia', 'com.plexapp.agents.lambda', 'com.plexapp.agents.xbmcnfo']
    contributes_to = ['com.plexapp.agents.none']
    primary_provider = True

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def search(self, results, media, lang, manual=False):
        log.separator(msg='Search Parameters', log_level='debug')
        log.debug('[TPDB Agent] Media Title: "%s"' % media.title)
        log.debug('[TPDB Agent] Media Name: "%s"' % media.name)
        log.debug('[TPDB Agent] Media Year: "%s"' % media.year)
        log.debug('[TPDB Agent] File: "%s"' % media.items[0].parts[0].file)
        log.debug('[TPDB Agent] Filename: "%s"' % media.filename)
        log.debug('[TPDB Agent] Language: "%s"' % lang)
        log.debug('[TPDB Agent] Manual Search: "%s"' % manual)
        log.separator(msg='', log_level='debug')

        if not manual:
            results = get_title_results(media, results, manual)
        else:
            log.debug('[TPDB Agent] Adding title search results because this is a manual search')
            results = get_title_results(media, results, manual)

        results.Sort('score', descending=True)

        return results

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def update(self, metadata, media, lang, force=False):
        uri = API_SCENE_URL % metadata.id

        if Prefs['save_to_collection']:
            uri = uri + API_ADD_TO_COLLECTION_QS_SUFFIX

        try:
            json_obj = GetJSON(uri)
        except:
            json_obj = None

        if not json_obj:
            return metadata

        metadata.content_rating = 'XXX'

        scene_data = json_obj['data']

        metadata.title = scene_data['title']

        if 'duration' in scene_data and scene_data['duration'] and int(scene_data['duration']) > 0:
            metadata.duration = int(scene_data['duration']) * 1000

        if 'site' in scene_data and scene_data['site']:
            metadata.studio = scene_data['site']['name']

        metadata.summary = scene_data['description']

        date_object = parse(scene_data['date'])
        if date_object:
            metadata.originally_available_at = date_object
            metadata.year = metadata.originally_available_at.year

        collections = []
        if 'site' in scene_data and scene_data['site']:
            site_name = scene_data['site']['name']

            # Site Collection
            if site_name and Prefs['collections_from_site']:
                site_collection = ''

                if Prefs['collection_site_prefix']:
                    site_collection = Prefs['collection_site_prefix']

                site_collection += site_name

                log.debug('[TPDB Agent] Queueing Site Collection: "%s"' % site_collection)
                collections.append(site_collection)

            # Network Collection
            site_id = scene_data['site']['id']
            network_id = scene_data['site']['network_id']
            if network_id and site_id != network_id and Prefs['collections_from_networks']:
                network_name = ''

                if 'network' in scene_data['site'] and scene_data['site']['network']:
                    network_name = scene_data['site']['network']['name']
                else:
                    uri = API_SITE_URL % network_id

                    try:
                        site_data = GetJSON(uri)
                    except:
                        site_data = None

                    if site_data:
                        network_name = site_data['data']['name']

                if network_name and network_name != site_name:
                    net_collection = ''

                    if Prefs['collection_network_prefix']:
                        net_collection = Prefs['collection_network_prefix']

                    net_collection += network_name

                    log.debug('[TPDB Agent] Queueing Network Collection: "%s"' % net_collection)
                    collections.append(net_collection)

        # Genres
        genres = []
        if 'tags' in scene_data:
            for tag in scene_data['tags']:
                genres.append(tag['name'])

        metadata.genres.clear()
        for genre in genres:
            log.debug('[TPDB Agent] Adding Genre: "%s"' % genre)
            metadata.genres.add(genre)

        if Prefs['create_all_tag_collection_tags']:
            for genre in genres:
                log.debug('[TPDB Agent] Queueing Tag Collection: "%s"' % genre)
                collections.append(genre)

        # Collections
        metadata.collections.clear()
        for collection in collections:
            log.debug('[TPDB Agent] Adding Collection: "%s"' % collection)
            metadata.collections.add(collection)

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

            log.debug('[TPDB Agent] Adding Actor: "%s": "%s"' % (role.name, role.photo))

        if Prefs['custom_title_enable']:
            log.debug('[TPDB Agent] Using custom naming format: "%s"' % Prefs['custom_title'])

            data = {
                'title': metadata.title,
                'actors': ', '.join([actor.name.encode('ascii', 'ignore') for actor in metadata.roles]),
                'studio': metadata.studio,
                'series': ', '.join(set([collection.encode('ascii', 'ignore') for collection in metadata.collections if collection not in metadata.studio])),
            }
            metadata.title = Prefs['custom_title'].format(**data)

            log.debug('[TPDB Agent] Resulting Title: "%s"' % metadata.title)

        poster = scene_data['posters']['large']
        if poster:
            try:
                metadata.posters[poster] = Proxy.Media(make_request(poster))
            except:
                log.error('[TPDB Agent] Failed to retrieve poster image: "%s"' % poster)

        background = scene_data['background']['full']
        if background:
            try:
                metadata.art[background] = Proxy.Media(make_request(background))
            except:
                log.error('[TPDB Agent] Failed to retrieve background image: "%s"' % background)

        if 'trailer' in scene_data and scene_data['trailer']:
            if Prefs['import_trailer']:
                trailer_url = 'tpdb://trailer/' + base64.urlsafe_b64encode(scene_data['trailer'])
                trailer = TrailerObject(url=trailer_url, title='Trailer', thumb=background)
                log.debug('[TPDB Agent] Adding Trailer: %s' % scene_data['trailer'])

                metadata.extras.add(trailer)
            else:
                log.debug('[TPDB Agent] Trailer available, but not imported due to user preferences')

        return metadata
