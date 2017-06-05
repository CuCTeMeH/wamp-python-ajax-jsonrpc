from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner, ApplicationSessionFactory
from autobahn.wamp.types import RegisterOptions
from autobahn.wamp.exception import ApplicationError
from twisted.internet.defer import inlineCallbacks
from authenticator import PandaXAuthenticator
from http.cookies import SimpleCookie
import requests
import json
import urllib
import redis


class PandaX(ApplicationSession):
    def __init__(self, config=None):
        ApplicationSession.__init__(self, config)
        self.cookies = None
        self.oauthCookie = None
        self.topics = {}
        self.topic_ids = {}
        self.user_sessions = {}

    def onConnect(self):
        self.join(self.config.realm)

    @inlineCallbacks
    def onJoin(self, details):
        yield self.subscribe(self.on_session_join, u'wamp.session.on_join')
        yield self.subscribe(self.on_leave, u'wamp.session.on_leave')
        yield self.subscribe(self.on_subscribe, u'wamp.subscription.on_subscribe')
        yield self.subscribe(self.on_subscribe_create, u'wamp.subscription.on_create')
        yield self.register(self.jsonrpc, u"jsonrpc.", options=RegisterOptions(match=u"prefix", details_arg="details"))

    def on_leave(self, session):
        # print(session)
        user_sessions = self.user_sessions
        # print(type(user_sessions))
        # print('LEAVING SESSION')
        for user_id, sessions in user_sessions.items():
            for session_id, s_id in sessions.copy().items():
                if session_id == session:
                    sessions.pop(session_id)
                    # del(user_sessions[user_id][session_id])
            # print(v)
        # print(user_sessions)
        # print('LEAVING SESSION')
        self.user_sessions = user_sessions

    def on_subscribe_create(self, session, subscription_details):
        topic = subscription_details['uri']
        topic_id = subscription_details['id']
        self.topics[topic_id] = topic
        self.topic_ids[topic] = topic_id

    def on_subscribe(self, session, subscription):
        topic = self.topics[subscription]
        subscribers = self.call('wamp.subscription.list_subscribers', subscription)
        # print(topic)
        # print(subscribers)

    def get_laravel_session(self, session_details):
        cookie = SimpleCookie()
        cookie.load(session_details.get('transport', {}).get('http_headers_received', {}).get('cookie', {}))

        # Even though SimpleCookie is dictionary-like, it internally uses a Morsel object
        # which is incompatible with requests. Manually construct a dictionary instead.
        cookies = {}
        r = redis.StrictRedis(host='localhost', port=6379, db=0)

        for key, morsel in cookie.items():
            if key == 'laravel_oauth_session':
                if r.exists(morsel.value):
                    morsel.value = r.get(morsel.value).decode("utf-8")
                else:
                    token = PandaXAuthenticator.get_auth_token()
                    # print(token)
                    headers = {
                        'content-type': 'application/json',
                        'Authorization': 'Bearer ' + token
                    }
                    payload = {
                        "cookie": urllib.parse.unquote(morsel.value)
                    }

                    response = requests.post('https://dev-auth.probidder.com/api/cookie/decrypt',
                                             data=json.dumps(payload), headers=headers).json()

                    if response and 'error' in response:
                        return self.get_laravel_session(self, session_details)

                    if response['status']:
                        r.set(morsel.value, response['cookie'])
                        morsel.value = response['cookie']

            cookies[key] = morsel.value
            self.cookies = cookies
        return cookies

    def on_session_join(self, session_details):
        """
        We store the cookies here in the this session variable foreach session.

        :param session_details: 
        :return: 
        """
        # print("WAMP session has joined:")
        # print(session_details.get('session'))
        # print(session_details.get('transport', {}).get('http_headers_received', {}).get('cookie', {}))
        cookies = self.get_laravel_session(session_details)
        session_id = session_details.get('session')
        logged_user = PandaXAuthenticator.is_logged_in(cookies)
        # print(logged_user)
        logged_user_request_status = logged_user.get('status')
        if logged_user_request_status:
            user_id = logged_user['user']['id']
            # print(self.user_sessions)
            # print(session_id)
            # if(self.user_sessions.get(user_id).get(session_id) == None):
            if self.user_sessions.get(user_id) is None:
                self.user_sessions[user_id] = {}
            self.user_sessions[user_id][session_id] = session_id

        print(self.user_sessions)
        # print(logged_user)
        # if logged_user and 'user' in logged_user:
        #     self.user_sessions[logged_user['user']['id']][session_id] =  session_id

    def jsonrpc(self, url, method, params, publish=True, details=None, recurse=True):
        """
        This is the main method that is used to send the URL via the request.
        After that it will publish to all subscribers the result.
        When the request is made the cookies of the current user are attached.
        Cookies are fetched on join of the user to the socket connection.
        
        :param url: 
        :param method: 
        :param params: 
        :param publish: 
        :param details: 
        :param recurse: 
        :return: 
        """
        # print('jsonrpc')
        # print(params)
        # print(PandaXAuthenticator.get_auth_token())
        # print(self.cookies)
        # print(self.user_sessions)
        token = PandaXAuthenticator.get_auth_token()
        topic_ids = self.topic_ids[details.procedure]
        # print(topic_ids)
        is_logged_in = PandaXAuthenticator.is_logged_in(self.cookies)
        # print(is_logged_in)
        response = None

        if is_logged_in or params['allow_anonymous']:
            procedure = details.procedure
            headers = {
                'content-type': 'application/json',
                'Authorization': 'Bearer ' + token
            }
            payload = {
                "params": params,
                'publish': publish,
                "jsonrpc": "2.0",
                "id": 0,
            }

            if method == 'get':
                response = requests.get(url, data=json.dumps(payload), headers=headers, cookies=self.cookies).json()
            elif method == 'post':
                response = requests.post(url, data=json.dumps(payload), headers=headers, cookies=self.cookies).json()

            if response and 'error' in response:
                if recurse is False:
                    raise ApplicationError(u'call.rest.error.authenticate',
                                           'could not authenticate session')

                return self.jsonrpc(self, url, method, params, publish, details, False)

            if response and 'publish' in response:
                self.publish(procedure, response)

        return response
