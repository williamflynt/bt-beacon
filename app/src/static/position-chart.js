let expanderVar = 50;

let defaultWidth = 10 * expanderVar;
let defaultHeight = 5 * expanderVar;

let svgContainer = d3.select("#svgSpace").append("svg")
    .attr("width", defaultWidth)
    .attr("height", defaultHeight)
    .style("margin", "10px");

let c1 = svgContainer
    .append("circle");
let c2 = svgContainer
    .append("circle");

c2.attr("cx", svgContainer.attr("width") / 2)
    .attr("cy", svgContainer.attr("height") / 2)
    .attr("r", 20)
    .style("fill", "gray")
    .style("opacity", 0.5);

c1.attr("cx", svgContainer.attr("width") / 2)
    .attr("cy", svgContainer.attr("height") / 2)
    .attr("r", 5)
    .style("fill", "gray");

function updateSize(x, y, offset = 0) {
    x = (x * expanderVar) + offset;
    y = (y * expanderVar) + offset;

    if (defaultWidth < x) {
        defaultWidth = x;
        svgContainer.attr("width", x + 20)
    }
    if (defaultHeight < y) {
        defaultHeight = y;
        svgContainer.attr("height", y + 20)
    }
}