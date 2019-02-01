import os
from pathlib import Path

import dotenv
from bottle import route, run, template, request
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub

INTERNAL_POST = "/locate"
POST_TO = "https://localhost:8765/locate"
FILE_DIR = os.path.dirname(os.path.abspath(__file__))
ACTIVATE_DIR = os.path.join(FILE_DIR, "..", "..", "venv", "bin", "activate")
ENV_FILE = os.path.join(FILE_DIR, "..", "..", "pubnub.env")


@route('/')
def index():
    env = Path(ENV_FILE)
    if env.exists():
        dotenv.load_dotenv(str(env.absolute()))

    x = os.environ.get("NODE_X", "X")
    y = os.environ.get("NODE_Y", "Y")
    pub = os.environ.get("PUB_KEY", "Pub Key")
    sub = os.environ.get("SUB_KEY", "Sub Key")
    hostname = os.environ.get("HOSTNAME", "Hostname")
    return template(
        """
        <html>
        <head><title>Node Registration</title></head>
        <body>
        <div style="width: 400px;">
        
            <h1>BLE Scanner Location</h1>
            <hr/>
            {pub}<br />
            {sub}
            <br/><br/>
            
            <form action="{INTERNAL_POST}" method="post">
              <fieldset>
              <legend>Raspberry Pi Relative Location: </legend>
              <input type="text" name="x" placeholder="{x}" required />
              <br />
              <input type="text" name="y" placeholder="{y}" required />
              <br/>
              <input type="text" name="pub" placeholder="{pub}" required />
              <br/>
              <input type="text" name="sub" placeholder="{sub}" required />
              <br/>
              <input type="text" name="hostname" placeholder="{hostname}" required />
              <br/>
              <input type="submit" name="submit" value="Set Pi Details" />
              </fieldset>
            </form>
        
        </div>
        
        </body>
        </html>
        """.format(INTERNAL_POST=INTERNAL_POST, pub=pub, sub=sub, x=x, y=y,
                   hostname=hostname)
    )


@route(INTERNAL_POST, method="POST")
def set_pi_location():
    x = request.forms.get('x')
    y = request.forms.get('y')
    pub = request.forms.get('pub')
    sub = request.forms.get('sub')
    hostname = request.forms.get('hostname')
    success_msg = "<h1>Success</h1>" \
                  "<p>This Raspberry Pi will use new coordinates on reboot.</p>"

    try:
        a_lines = [
            "\n", "\n", "# Set BLE scanner coordinates in meters\n",
            "export NODE_X={}\n".format(x), "export NODE_Y={}\n".format(y), "\n",
            "\n", "\n", "# Set PubNub keys\n",
            "export PUB_KEY={}\n".format(pub), "export SUB_KEY={}\n".format(sub), "\n",
            "\n", "\n", "# Set desired hostname\n",
            "export HOSTNAME={}\n".format(hostname), "\n",
        ]
        e_lines = [
            "NODE_X={}\n".format(x), "NODE_Y={}\n".format(y),
            "PUB_KEY={}\n".format(pub), "SUB_KEY={}\n".format(sub),
            "HOSTNAME={}\n".format(hostname),
        ]

        with open(ACTIVATE_DIR, "a") as f:
            f.writelines(a_lines)
        with open(ENV_FILE, "a") as f:
            f.writelines(e_lines)

    except Exception as e:
        return template(
            """
            <html>
            <body>
                <h3>Oops</h3>
                <p>{e}</p>
            </body>
            </html>
            """.format(e=e)
        )

    try:
        init_message = {"name": os.environ["HOSTNAME"],
                        "coords": {
                            "x": x,
                            "y": y
                        }}
        env = Path(ENV_FILE)
        if env.exists():
            dotenv.load_dotenv(str(env.absolute()))
        pnconfig = PNConfiguration()
        pub_key = os.environ["PUB_KEY"]
        sub_key = os.environ["SUB_KEY"]
        if pub_key is not None and sub_key is not None:
            pnconfig.subscribe_key = sub_key
            pnconfig.publish_key = pub_key
            pnconfig.ssl = False
            pubnub = PubNub(pnconfig)
            pubnub.publish() \
                .channel('nodes') \
                .message(init_message) \
                .should_store(True) \
                .pn_async()

            return template(
                """
                <html>
                <body>
                    {}
                </body>
                </html>
                """.format("<h1>Success</h1>"
                           "<p>This Raspberry Pi has published new coords.</p>"))

    except Exception as e:
        success_msg = success_msg + "<p>{}</p>".format(e)

    return template(
        """
        <html>
        <body>
            {success_msg}
        </body>
        </html>
        """.format(success_msg=success_msg)
    )


run(host='0.0.0.0', port=8765)
