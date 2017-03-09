try {
   var autobahn = require('autobahn');
} catch (e) {
   // when running in browser, AutobahnJS will
   // be included without a module system
}

if (true) {
   // authenticate using authid "joe"
   var user = "joe";
   var key = "secret2";
} else {
   // authenticate using authid "peter", and using a salted password
   var user = "peter";
   var key = autobahn.auth_cra.derive_key("secret1", "salt123", 100, 16);
}

function onchallenge (session, method, extra) {

   console.log("onchallenge", method, extra);

   if (method === "wampcra") {

      console.log("authenticating via '" + method + "' and challenge '" + extra.challenge + "'");

      return autobahn.auth_cra.sign(key, extra.challenge);

   } else {
      // throw "don't know how to authenticate using '" + method + "'";
   }
}


var connection = new autobahn.Connection({
   url: 'ws://127.0.0.1:8080/ws',
   realm: 'realm1',

   // The following authentication information is for authenticating
   // our frontend component
   //
   authid: user,
   authmethods: ["cookie", "wampcra"],
   onchallenge: onchallenge
});

connection.onopen = function (session, details) {
    console.log("frontend connected");
    console.log("connected session with ID " + session.id);
    console.log("authenticated using method '" + details.authmethod + "' and provider '" + details.authprovider + "'");
    console.log("authenticated with authid '" + details.authid + "' and authrole '" + details.authrole + "'");

   function on_heartbeat(args, kwargs, details) {
      console.log("Got heartbeat (publication ID )");
   }


        // session.subscribe("call.rest.jsonrpc", function (args, kwargs) {
        //
        //
        //        console.log("got event:", args);
        // }).then(
        //     function (sub) {
        //         // console.log(sub);
        //         console.log("subscribed", sub.id);
        //         session.call('call.rest.jsonrpc', [url = 'http://dev-marketplace.probidder.com/api/sales', method = 'get', params = []]);
        //     },
        //     function (err) {
        //         console.log("error:", err);
        //     }
        // );

    // session.call('call.rest.jsonrpc', [url = 'http://dev-marketplace.probidder.com/api/sales', method = 'get', params = []]);

    session.call('call.rest.jsonrpc', [url = 'http://dev-marketplace.probidder.com/api/sales', method = 'get', params = []]).then(
         function (res) {
            console.log(res);
         },
         function (error) {
            console.log(error);
         }
    );

   // session.subscribe('com.call.sexydemo');
   // session.call('call.rest.jsonrpc', 'test1');
   // session.publish('com.call.sexydemo', 'test2');
   // session.publish('com.call.sexydemo', 'test3');
   // session.publish('com.call.sexydemo', 'test4');
   // session.publish('com.call.sexydemo', 'test5');
};

connection.open();
