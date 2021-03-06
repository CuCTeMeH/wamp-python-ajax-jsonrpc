from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner, ApplicationSessionFactory
from autobahn.wamp.types import RegisterOptions
from twisted.internet.defer import inlineCallbacks, returnValue
from authenticator import PandaXAuthenticator
from http.cookies import SimpleCookie
import requests
import simplejson
import urllib
import redis
import treq


class PandaX(ApplicationSession):
    def __init__(self, config=None):
        """
        Constructor used to instantiate class variables.

        :param config:
        """
        ApplicationSession.__init__(self, config)
        self.cookies = {}
        self.encryptedCookies = {}
        self.oauthCookie = {}
        self.topics = {}
        self.topic_ids = {}
        self.user_sessions = {}
        self.logged_users = {}
        self.topics_to_users = {}
        self.users_to_topics = {}
        self.topics_to_user = {}
        self.user_to_topics = {}

    def onConnect(self):
        """
        Event on connect that will pass the realm configuration.

        :return:
        """
        self.join(self.config.realm)

    @inlineCallbacks
    def onJoin(self, details):
        """
        Event on server join that will hook all the needed events.

        :param details:
        :return:
        """
        yield self.subscribe(self.on_session_join, u'wamp.session.on_join')
        yield self.subscribe(self.on_leave, u'wamp.session.on_leave')
        yield self.subscribe(self.on_subscribe, u'wamp.subscription.on_subscribe')
        yield self.subscribe(self.on_unsubscribe, u'wamp.subscription.on_unsubscribe')
        yield self.subscribe(self.on_subscribe_create, u'wamp.subscription.on_create')
        yield self.register(self.jsonrpc, u"jsonrpc.", options=RegisterOptions(match=u"prefix", details_arg="details"))
        yield self.register(self.system_private, u"system.private.", options=RegisterOptions(match=u"prefix", details_arg="details"))

    def on_leave(self, session):
        """
        Event on leave that will remove user sessions and users to topics session.

        :param session:
        :return:
        """
        user_sessions = self.user_sessions
        for user_id, sessions in user_sessions.items():
            for session_id, s_id in sessions.copy().items():
                if session_id == session:
                    sessions.pop(session_id)
                    self.del_topics_to_users(user_id)
                    self.remove_logged_user(session_id)

        self.user_sessions = user_sessions
        self.update_user_sessions_redis()
        self.update_users_to_topics_redis()

    def remove_logged_user(self, session):
        logged_users = self.logged_users
        for sessions, user_id in logged_users.items():
            for session_id, s_id in user_id.copy().items():
                if session_id == session:
                    sessions.pop(session_id)

        self.logged_users = logged_users

    def update_user_sessions_redis(self):
        """
        Helper method used to store user session connections in REDIS.

        :return:
        """
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        r.set('socket_user_sessions', simplejson.dumps(self.user_sessions))

        for user_id, user_socket_id in self.user_sessions.items():
            r.set('socket_user_sessions:' + str(user_id), simplejson.dumps(user_socket_id))

    def update_users_to_topics_redis(self):
        """
        Helper method used to store the topics to users dict in REDIS

        :return:
        """
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        r.set('socket_topics_to_users', self.topics_to_users)

        if self.topics_to_users is not None:
            for t, u in self.topics_to_users.items():
                r.set('socket_topic_to_users:' + str(t), simplejson.dumps(u))
        if self.users_to_topics is not None:
            for u, t in self.users_to_topics.items():
                r.set('socket_user_to_topics:' + str(u), simplejson.dumps(t))

    def add_topics_to_users(self, topic, user):
        """
        Helper method to add topics to users dict.

        :param topic:
        :param user:
        :return:
        """
        topics_to_users = self.topics_to_users
        users_to_topics = self.users_to_topics
        user = str(user)

        if topics_to_users.get(topic, None) is None:
            topics_to_users[topic] = {}

        if users_to_topics.get(user, None) is None:
            users_to_topics[user] = {}

        topics_to_users[topic][user] = user
        users_to_topics[user][topic] = topic

        self.topics_to_users = topics_to_users
        self.users_to_topics = users_to_topics

        self.update_users_to_topics_redis()

    def delete_keys_from_dict(self, dict_del, lst_keys):
        """
        Gracefully delete keys from nested dictionary

        :param dict_del:
        :param lst_keys:
        :return:
        """
        for k in lst_keys:
            try:
                del dict_del[k]
            except KeyError:
                pass
        for v in dict_del.values():
            if isinstance(v, dict):
                self.delete_keys_from_dict(v, lst_keys)

        return dict_del

    def del_topics_to_users(self, user, topic=None):
        """
        Helper method to delete the users from a topic.

        :param user:
        :param topic:
        :return:
        """
        topics_to_users = self.topics_to_users
        users_to_topics = self.users_to_topics

        if topic is not None:
            topics_to_users = topics_to_users.get(topic, {}).pop(user, None)
            users_to_topics = users_to_topics.get(user, {}).pop(topic, None)
        else:
            topics_to_users = self.delete_keys_from_dict(topics_to_users, [str(user)])

            for u, tt in users_to_topics.copy().items():
                if u == str(user):
                    for tk, tv in tt.copy().items():
                        tt.pop(tv, None)

        self.topics_to_users = topics_to_users
        self.users_to_topics = users_to_topics

        self.update_users_to_topics_redis()

    def on_subscribe_create(self, session, subscription_details):
        """
        Event on channel/topic creation. We add the topic to the dict for passing it to PHP backend.

        :param session:
        :param subscription_details:
        :return:
        """
        topic = subscription_details['uri']
        topic_id = subscription_details['id']
        self.topics[topic_id] = topic
        self.topic_ids[topic] = topic_id

    def on_unsubscribe(self, session, subscription):
        """
        Event on unsubscribe that will remove the user session from the topic session.

        :param session:
        :param subscription:
        :return:
        """
        topic = self.topics[subscription]
        users = self.user_sessions

        for user_id, user_socket_id in users.items():
            for sock_ids in user_socket_id:
                if session == sock_ids:
                    self.del_topics_to_users(user_id, topic)

    @inlineCallbacks
    def on_subscribe(self, session, subscription):
        """
        Event on subscribe to check if the user is subscribing to his private channel, restricted only to the specific user. If the user is allowed to connect to his private channel than add the user to the connection dictionary for passing it back to the PHP backend for furthur checks.

        :param session:
        :param subscription:
        :return:
        """
        topic = self.topics[subscription]
        users = self.user_sessions

        subscribers = yield self.call('wamp.subscription.list_subscribers', subscription)
        for subs in subscribers:
            for user_id, user_socket_id in users.items():
                for sock_ids in user_socket_id:
                    if session == sock_ids == subs and topic.startswith('system.private.') and topic != 'system.private.' + str(user_id):
                        # TODO: Here when the remove subscriber is called because it is async a frontend JS error occurs stating: "Uncaught DOMException: Failed to execute 'close' on 'WebSocket': The code must be either 1000, or between 3000 and 4999. 1002 is neither.". This only occurs when a hacker tries to subscribe to a private channel so not highest priority but investigate this when can.
                        yield self.call("wamp.subscription.remove_subscriber", subscription_id=subscription, subscriber_id=session)
                        return
                    elif session == sock_ids == subs:
                        self.add_topics_to_users(topic, user_id)

    def get_laravel_session(self, session_details):
        """
        Get the Laravel Session Cookie for using with the AUTH server.

        :param session_details:
        :return:
        """
        cookie = SimpleCookie()
        cookie.load(session_details.get('transport', {}).get('http_headers_received', {}).get('cookie', {}))

        user_session_id = session_details.get('session', {})
        cookies = {}
        encrypted_cookies = {}
        r = redis.StrictRedis(host='localhost', port=6379, db=0)

        for key, morsel in cookie.items():
            encrypted_cookies[key] = morsel.value
            if key == 'laravel_oauth_session':
                if r.exists(morsel.value):
                    morsel.value = r.get(morsel.value).decode("utf-8")
                else:
                    token = PandaXAuthenticator.get_auth_token()

                    headers = {
                        'content-type': 'application/json',
                        'Authorization': 'Bearer ' + token
                    }
                    payload = {
                        "cookie": urllib.parse.unquote(morsel.value)
                    }

                    response = requests.post('http://localhost/api/cookie/decrypt',
                                             data=simplejson.dumps(payload), headers=headers).json()

                    if response and 'error' in response:
                        return self.get_laravel_session(self, session_details)

                    if response['status']:
                        r.set(morsel.value, response['cookie'])
                        morsel.value = response['cookie']

            cookies[key] = morsel.value
        self.cookies[user_session_id] = cookies
        self.encryptedCookies[user_session_id] = encrypted_cookies
        return cookies

    def on_session_join(self, session_details):
        """
        We store the cookies here in the this session variable foreach session.

        :param session_details: 
        :return: 
        """
        cookies = self.get_laravel_session(session_details)
        session_id = session_details.get('session')
        logged_user = PandaXAuthenticator.is_logged_in(cookies)
        if logged_user is False:
            return False
        logged_user_request_status = logged_user.get('status')
        if logged_user_request_status:
            user_id = logged_user['user']['id']
            if self.user_sessions.get(user_id) is None:
                self.user_sessions[user_id] = {}
            self.user_sessions[user_id][session_id] = session_id

            if self.logged_users.get(session_id) is None:
                self.logged_users[session_id] = {}
            self.logged_users[session_id] = logged_user['user']

        self.update_user_sessions_redis()

    def http_request(self, url, method, params, details=None):
        """
        Make a Async HTTP Request.

        :param url:
        :param method:
        :param params:
        :param details:
        :return:
        """
        user_session_id = details.caller
        token = PandaXAuthenticator.get_auth_token()

        is_logged_in = self.logged_users.get(user_session_id)
        if is_logged_in is False:
            return False

        procedure = details.procedure
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer ' + token
        }
        payload = {
            "params": simplejson.dumps(params),
            "jsonrpc": "2.0",
            "user": simplejson.dumps(is_logged_in)
        }

        self.async_request(url, payload, headers, self.encryptedCookies[user_session_id], method, procedure)

    def async_request(self, url, payload, headers, cookies, method, procedure):
        """
        Async Request using treq.

        :param url:
        :param payload:
        :param headers:
        :param cookies:
        :param method:
        :param procedure:
        :return:
        """
        if method == 'get':
            d = treq.get(url, params=payload, headers=headers, cookies=cookies)
        elif method == 'post':
            d = treq.post(url, params=payload, headers=headers, cookies=cookies)
        else:
            return False

        def get_response(resp):
            """
            Get response from async Request using treq.

            :param resp:
            :return:
            """
            deferred = treq.json_content(resp)

            def get_json_from_response(response):
                """
                Get JSON from async Response using treq and publish to channel if allowed.
                :param response:
                :return:
                """
                if response and 'publish' in response or response and 'error' in response:
                    self.publish(procedure, response)

            deferred.addCallback(get_json_from_response)

        d.addCallback(get_response)

    def jsonrpc(self, url, method, params, details=None):
        """
        This is the main method that is used to send the URL via the request.
        After that it will publish to all subscribers the result.
        When the request is made the cookies of the current user are attached.
        Cookies are fetched on join of the user to the socket connection.
        
        :param url: 
        :param method: 
        :param params: 
        :param details:
        :param recurse: 
        :return: 
        """
        self.http_request(url=url, method=method, params=params, details=details)

    def system_private(self, url, method, params, details=None):
        """
        Make a call to the private channel.

        :param url:
        :param method:
        :param params:
        :param details:
        :param recurse:
        :return:
        """
        self.http_request(url=url, method=method, params=params, details=details)
