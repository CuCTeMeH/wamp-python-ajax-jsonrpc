try {
   var autobahn = require('autobahn');
} catch (e) {
   // when running in browser, AutobahnJS will
   // be included without a module system
}

var connection = new autobahn.Connection({
   url: 'ws://127.0.0.1:8080/ws',
   realm: 'crossbardemo'}
);

connection.onopen = function (session) {

   function on_heartbeat(args, kwargs, details) {
      console.log("Got heartbeat (publication ID )");
   }


        session.subscribe("call.rest.jsonrpc", function (args, kwargs) {
               console.log("got event:", args);
            }).then(
               function (sub) {
                   // console.log(sub);
                  console.log("subscribed", sub.id);
                  session.call('call.rest.jsonrpc', [url = 'http://dev-marketplace.probidder.com/api/sales', method = 'get', params = []]);
               },
               function (err) {
                  console.log("error:", err);
               }
            );
        //           session.call('call.rest.jsonrpc', [url = 'http://dev-marketplace.probidder.com/api/sales', method = 'get', params = []]);

   // session.subscribe('com.call.sexydemo');
   // session.call('call.rest.jsonrpc', 'test1');
   // session.publish('com.call.sexydemo', 'test2');
   // session.publish('com.call.sexydemo', 'test3');
   // session.publish('com.call.sexydemo', 'test4');
   // session.publish('com.call.sexydemo', 'test5');
};

connection.open();
