from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner, ApplicationSessionFactory
from autobahn.wamp.types import RegisterOptions
from autobahn.wamp.exception import ApplicationError
from twisted.internet.defer import inlineCallbacks
from authenticator import PandaXAuthenticator
from http.cookies import SimpleCookie
import requests
import json
import urllib


class PandaX(ApplicationSession):
    def __init__(self, config=None):
        ApplicationSession.__init__(self, config)
        self.cookies = None
        self.oauthCookie = None

    def onConnect(self):
        self.join(self.config.realm)

    @inlineCallbacks
    def onJoin(self, details):
        yield self.subscribe(self.on_session_join, u'wamp.session.on_join')
        yield self.register(self.jsonrpc, u"jsonrpc.", options=RegisterOptions(match=u"prefix", details_arg="details"))

    def on_session_join(self, session_details):
        """
        We store the cookies here in the this session variable foreach session.
        
        Todo: Maybe refactor this to use redis because self can be overwritten any time. But if not needed there is no need to overcomplicate stuff with adding a redis set and get and cleanup when the cookie expires.
        
        :param session_details: 
        :return: 
        """
        # print("WAMP session has joined:")
        # print(session_details)
        # print(session_details.get('transport', {}).get('http_headers_received', {}).get('cookie', {}))

        cookie = SimpleCookie()
        cookie.load(session_details.get('transport', {}).get('http_headers_received', {}).get('cookie', {}))

        # Even though SimpleCookie is dictionary-like, it internally uses a Morsel object
        # which is incompatible with requests. Manually construct a dictionary instead.
        cookies = {}

        for key, morsel in cookie.items():
            if key == 'laravel_oauth_session':
                if self.oauthCookie:
                    morsel.value = self.oauthCookie
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
                        return self.on_session_join(self, session_details)

                    if response['status']:
                        self.oauthCookie = response['cookie']
                        morsel.value = response['cookie']

            cookies[key] = morsel.value
        # print(cookies)
        self.cookies = cookies

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
        token = PandaXAuthenticator.get_auth_token()
        is_logged_in = PandaXAuthenticator.is_logged_in(self.cookies)
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

            if response.publish:
                self.publish(procedure, response)

        return response
