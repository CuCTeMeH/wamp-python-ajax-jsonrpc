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

    def onConnect(self):
        self.join(self.config.realm)

    @inlineCallbacks
    def onJoin(self, details):
        yield self.subscribe(self.on_session_join, u'wamp.session.on_join')
        yield self.register(self.jsonrpc, u"jsonrpc.", options=RegisterOptions(match=u"prefix", details_arg="details"))

    def on_session_join(self, session_details):
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
                token = PandaXAuthenticator.get_auth_token()
                # print(token)
                headers = {
                    'content-type': 'application/json',
                    'Authorization': 'Bearer ' + token
                }
                payload = {
                    "cookie": urllib.parse.unquote(morsel.value)
                }
                # print(payload)

                response = requests.post('https://dev-auth.probidder.com/api/cookie/decrypt',
                                         data=json.dumps(payload), headers=headers).json()

                if response and 'error' in response:
                    raise ApplicationError(u'call.rest.authenticate.jwt',
                                           'could not authenticate jwt {}'.format(authid))

                if response['status']:
                    morsel.value = response['cookie']

            cookies[key] = morsel.value

        self.cookies = cookies

    def jsonrpc(self, url, method, params, publish=True, details=None):
        # print(details)
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
                "jsonrpc": "2.0",
                "id": 0,
            }

            if method == 'get':
                response = requests.get(url, data=json.dumps(payload), headers=headers, cookies=self.cookies).json()
            elif method == 'post':
                response = requests.post(url, data=json.dumps(payload), headers=headers, cookies=self.cookies).json()

            if response and 'error' in response:
                return self.jsonrpc(self, url, method, params, publish, details)

            if publish:
                self.publish(procedure, response)

        return response
