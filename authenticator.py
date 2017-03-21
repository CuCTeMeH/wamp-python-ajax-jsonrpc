from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner, ApplicationSessionFactory
from autobahn import wamp
from autobahn.wamp.exception import ApplicationError
from twisted.internet.defer import inlineCallbacks
from twisted.python.failure import Failure
from http.cookies import SimpleCookie
import redis
import requests
import json
import jwt
import time
import urllib


class PandaXAuthenticator(ApplicationSession):
    redis_jwt_key = 'jwt-python'

    @inlineCallbacks
    def onJoin(self, details):
        # print("session joined")
        # print(details)

        results = []
        res = yield self.register(self)
        results.extend(res)

        for res in results:
            if isinstance(res, Failure):
                print("Failed to register procedure: {}".format(res.value))
            else:
                print("registration ID {}: {}".format(res.id, res.procedure))

    @wamp.register(u'call.rest.authenticate')
    def authenticate(self, realm, authid, details):
        # print("WAMP-CRA dynamic authenticator invoked: realm='{}', authid='{}'".format(realm, authid))
        # print(details)
        #
        cookie = SimpleCookie()
        cookie.load(details.get('transport', {}).get('http_headers_received', {}).get('cookie', {}))

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

        # print(cookies)
        user = self.is_logged_in(cookies)

        # print(user)

        if user['status'] and user['user']['username'] == authid:
            return {
                # these are required:
                'secret': str(user['user']['username']),  # the secret/password to be used
                'role': 'frontend'  # the auth role to be assigned when authentication succeeds
            }
        else:
            raise ApplicationError(u'call.rest.authenticate.no_such_user',
                                   'could not authenticate session - no such user {}'.format(authid))

    @staticmethod
    def get_auth_token():
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        token = r.get(PandaXAuthenticator.redis_jwt_key)

        if token:
            return token.decode("utf-8")

        encoding_payload = {
            'aud': 'https://dev-auth.probidder.com',
            'exp': int(time.time() + 1000),
            'iat': int(time.time()),
            'sub': 'CertSale',
            'iss': 'marketplace'
        }

        pem_file = open("../../marketplace.key", 'r')
        key_string = pem_file.read()
        pem_file.close()

        encoded_key = jwt.encode(encoding_payload, algorithm='RS512', key=key_string)

        # print(encoded_key)
        headers = {
            'content-type': 'application/json'
        }

        payload = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": encoded_key.decode("utf-8")
        }
        # print(payload)

        response = requests.post('https://dev-auth.probidder.com/api/oauth/token',
                                 data=json.dumps(payload), headers=headers).json()
        # print(response)
        r.set(PandaXAuthenticator.redis_jwt_key, response['access_token'])

        return response['access_token']

    @staticmethod
    def is_logged_in(cookies):
        token = PandaXAuthenticator.get_auth_token()
        # print(token)
        # return True

        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer ' + token
        }
        payload = {
            "jsonrpc": "2.0",
            "id": 0,
        }

        r = redis.StrictRedis(host='localhost', port=6379, db=0)

        try:
            response = requests.get('https://dev-auth.probidder.com/api/authenticate/check',
                                    data=json.dumps(payload), headers=headers, cookies=cookies).json()
        except Exception as e:
            r.delete(PandaXAuthenticator.redis_jwt_key)
            return PandaXAuthenticator.is_logged_in(cookies)

        if response and 'error' in response:
            r.delete(PandaXAuthenticator.redis_jwt_key)
            return PandaXAuthenticator.is_logged_in(cookies)

        return response
