const messages = document.getElementById("messages");
const sub_key = messages.getAttribute("data-sub-key");
let update = true;

let pubnub = new PubNub({
    subscribeKey: sub_key,
    ssl: true
});

function scrollToBottom(divId) {
    let element = document.getElementById(divId);
    element.scrollTop = element.scrollHeight;
}

let allowedError = 3.5;

function setAllowedError(val) {
    document.getElementById("allowed-error").value = val;
    allowedError = val;
}

function toggleUpdate() {
    update = !update;
    if (update) {
        document.getElementById("toggle").innerText = "Pause"
    } else {
        document.getElementById("toggle").innerText = "Play"
    }
}

window.onload = function () {
    document.getElementById("status").innerHTML = "Creating Listener...";

    let known_nodes = {};

    pubnub.addListener({
        message: function (m) {
            let channelName = m.channel; // The channel for which the message belongs
            let channelGroup = m.subscription; // The channel group or wildcard subscription match (if exists)
            let pubTT = m.timetoken; // Publish timetoken
            let msg = m.message; // The Payload

            if (update) {
                // Create a new <p> element for the message text
                let new_msg = document.createElement("p");
                new_msg.style.cssText = 'color: #777; font-size: 0.7em;';
                // Make sure message is going to render as text (not object Object)
                let msg_text;
                if (msg !== null && typeof msg === 'object') {
                    msg_text = JSON.stringify(msg)
                } else {
                    msg_text = msg
                }

                // Add the text to the new element and append it to the correct div
                new_msg.innerText = msg_text;
                let msg_element = document.getElementById(channelName);
                msg_element.appendChild(new_msg);

                // Broken: doesn't allow for scrolling up at all...
                let shouldScroll = msg_element.scrollHeight + msg_element.scrollTop >= msg_element.clientHeight;
                if (shouldScroll) {
                    scrollToBottom(channelName);
                }

                // Update circle positions
                if (channelName === "located") {
                    let x = msg[2][0];
                    let y = msg[2][1];
                    let r = msg[3]['avg_err'];

                    if (r <= allowedError) {
                        c1.attr("cx", x * expanderVar).attr("cy", y * expanderVar).style("fill", "blue");
                        c2.attr("cx", x * expanderVar).attr("cy", y * expanderVar).attr("r", r * expanderVar).style("fill", "steelBlue");
                        updateSize(x, y, r);
                    }
                }
                else if (channelName === "ranged") {
                    // Add a circle around the ranged node
                    let node = known_nodes[msg[4]]['node'];
                    // let ranged = known_nodes[msg[4]['ranged']];
                    node.select('circle#' + msg[4] + 'range').remove();
                    let range_circle = node.append("circle");
                    range_circle.attr("r", msg[3] * expanderVar).attr('id', msg[4] + 'range');
                    range_circle.style("fill", "none").style("stroke", "black").style("stroke-opacity", 0.2)
                }
                // Add nodes that come up / broadcast position
                else if (channelName === "nodes") {
                    svgContainer.select("#" + msg.name).remove();

                    // expanderVar is applied inside this function so don't apply it here
                    updateSize(msg.coords.x, msg.coords.y);

                    let new_node = svgContainer.append("g");
                    new_node.attr("id", msg.name)
                        .attr("transform", function (d) {
                            return "translate(" + [
                                msg.coords.x * expanderVar,
                                msg.coords.y * expanderVar
                            ] + ")";
                        });

                    let new_circle = new_node.append("circle");
                    new_circle.attr("r", 3)
                        .attr("fill", "black");

                    let new_text = new_node.append("text").text(msg.name)
                        .attr("x", -5).attr("y", 10).style("font-size", "0.6em");

                    known_nodes[msg.name] = {'node': new_node, 'ranged': []};
                }
            }
        },
        status: function (s) {
            let affectedChannelGroups = s.affectedChannelGroups;
            let affectedChannels = s.affectedChannels;
            let category = s.category;
            let operation = s.operation;
            document.getElementById("category").innerHTML = category;
        }
    });

    document.getElementById("status").innerHTML = "Subscribing...";

    pubnub.subscribe({
        channels: ['nodes', 'raw_channel', 'ranged', 'located'],
    });

    document.getElementById("status").innerHTML = "Subscribed";
}