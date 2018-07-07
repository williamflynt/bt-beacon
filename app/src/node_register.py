import os
import requests
import subprocess
import sys
import uuid

from bottle import route, run, template, request

INTERNAL_POST = "/getkeys"
# POST_TO = "https://flock.starlingiot.com/register/{}".format(str(uuid.getnode()))
POST_TO = "http://localhost:8000/nodes/register/{}".format(str(uuid.getnode()))
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
        with open(os.path.join(FILE_DIR, 'pubnub.env'), 'wb') as envfile:
            envfile.writelines([bytes(s.encode('utf-8')) for s in [
                "PUB_KEY={}".format(pub),
                "\n",
                "SUB_KEY={}".format(sub)
            ]])
        os.environ['PUB_KEY'] = pub
        os.environ['SUB_KEY'] = sub

        # Start the node
        script_path = os.path.join(FILE_DIR, "node.py")
        subprocess.Popen(["nohup",
                          os.path.join(FILE_DIR, "..", "..", "venv", "bin", "python"),
                          script_path, "/dev/ttyACM0", "--pub", pub, "--sub", sub])

        # TODO: Kill bottle (also do this check on startup)
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
