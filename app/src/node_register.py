import os
import requests
import uuid

from bottle import route, run, template, request

INTERNAL_POST = "/getkeys"
NODE_ID = str(uuid.getnode())
# POST_TO = "https://localhost:8000/nodes/register/{}".format(NODE_ID)
POST_TO = "https://demo.starlingiot.com/nodes/register/{}".format(NODE_ID)
FILE_DIR = os.path.dirname(os.path.abspath(__file__))


@route('/')
def index():
    return template(
        """
        <html>
        <head><title>Node Registration</title></head>
        <body>
        <div style="width: 400px;">
        
            <h1>Node Registration</h1>
            <hr/>
            
            <form action="{post_to}" method="post">
              <fieldset>
              <legend>Login Information: </legend>
              <input type="text" name="username" placeholder="Username" />
              <br />
              <input type="password" name="passwd" placeholder="Password" />
              <br/>
              <input type="submit" name="submit" value="Register Node" />
              </fieldset>
            </form>
        
        </div>
        
        </body>
        </html>
        """.format(post_to=INTERNAL_POST)
    )


@route(INTERNAL_POST, method="POST")
def getkeys():
    username = request.forms.get('username')
    passwd = request.forms.get('passwd')
    data = {"username": username, "passwd": passwd}

    r = requests.post(POST_TO, data=data)
    content = r.json()
    keys = content.keys()

    if len(keys) == 2 and "pub" in keys and "sub" in keys:
        pub = content['pub']
        sub = content['sub']
        with open(os.path.join(FILE_DIR, '..', '..', 'pubnub.env'), 'wb') as envfile:
            envfile.writelines([bytes(s.encode('utf-8')) for s in [
                "PUB_KEY={}".format(pub),
                "\n",
                "SUB_KEY={}".format(sub)
            ]])
        os.environ['PUB_KEY'] = pub
        os.environ['SUB_KEY'] = sub

        # (Re)start the node
        # This works because user pi doesn't need a sudo password
        os.system("sudo systemctl stop node.service")
        os.system("sudo systemctl start node.service")
        os.system("sudo systemctl enable node.service")

        # TODO: Kill bottle
        # https://stackoverflow.com/questions/11282218/bottle-web-framework-how-to-stop

        return template(
            """
            <html>
            <body>
                <h1>Success</h1>
            </body>
            </html>
            """
        )


run(host='localhost', port=8765)
