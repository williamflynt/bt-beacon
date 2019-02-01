import os

from bottle import route, run, template, request
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub

INTERNAL_POST = "/locate"
POST_TO = "https://localhost:8765/locate"
FILE_DIR = os.path.dirname(os.path.abspath(__file__))
ACTIVATE_DIR = os.path.join(FILE_DIR, "..", "..", "venv", "bin", "activate")


@route('/')
def index():
    x = os.environ.get("NODE_X", "X")
    y = os.environ.get("NODE_Y", "Y")
    return template(
        """
        <html>
        <head><title>Node Registration</title></head>
        <body>
        <div style="width: 400px;">
        
            <h1>BLE Scanner Location</h1>
            <hr/>
            
            <form action="{INTERNAL_POST}" method="post">
              <fieldset>
              <legend>Raspberry Pi Relative Location: </legend>
              <input type="text" name="x" placeholder="{x}" />
              <br />
              <input type="text" name="y" placeholder="{y}" />
              <br/>
              <input type="submit" name="submit" value="Set Pi Location" />
              </fieldset>
            </form>
        
        </div>
        
        </body>
        </html>
        """.format(INTERNAL_POST=INTERNAL_POST, x=x, y=y)
    )


@route(INTERNAL_POST, method="POST")
def set_pi_location():
    x = request.forms.get('x')
    y = request.forms.get('y')
    success_msg = "<h1>Success</h1>" \
                  "<p>This Raspberry Pi will use new coordinates on reboot.</p>"

    try:
        os.environ["NODE_X"] = x
        os.environ["NODE_Y"] = y
        with open(ACTIVATE_DIR, "a") as f:
            f.writelines([
                "\n", "\n", "# Set BLE scanner coordinates in meters\n",
                "export NODE_X={}\n".format(x), "export NODE_X={}\n".format(y), "\n",
            ])

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
                .sync()

            return template(
                """
                <html>
                <body>
                    {}
                </body>
                </html>
                """.format("<h1>Success</h1>"
                           "<p>This Raspberry Pi has published new coords.</p>"))

    except:
        pass

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
