// Before/after preview graphs, styled after Anki's "Future Due" statistics
// graph (written from scratch: Anki's own code is AGPL, this add-on is MIT).
// Entry point: render({ before: [...], after: [...], strings: {...} }), where
// each array holds one count per day (index 0 = tomorrow) and `strings` holds
// the translated labels (see Translator.graph_strings in i18n.py).

const SVG_NS = "http://www.w3.org/2000/svg";
const WIDTH = 600;
const HEIGHT = 200;
const MARGIN = { top: 20, right: 40, bottom: 25, left: 40 };

// ColorBrewer "Greens", as used by Anki for this graph: darker for the
// nearest days (0.7 on the scale) to lighter for the farthest (0.3).
const GREENS = [
    "#f7fcf5", "#e5f5e0", "#c7e9c0", "#a1d99b", "#74c476",
    "#41ab5d", "#238b45", "#006d2c", "#00441b",
];

const hexToRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));

const greens = (t) => {
    const position = Math.min(Math.max(t, 0), 1) * (GREENS.length - 1);
    const index = Math.min(Math.floor(position), GREENS.length - 2);
    const from = hexToRgb(GREENS[index]);
    const to = hexToRgb(GREENS[index + 1]);
    const ratio = position - index;
    const rgb = from.map((c, i) => Math.round(c + (to[i] - c) * ratio));
    return `rgb(${rgb.join(",")})`;
};

// Round tick values (1, 2, 5 × 10^n) from 0 up to at least `max`.
const niceTicks = (max, count) => {
    const raw = Math.max(max, 1) / count;
    const power = 10 ** Math.floor(Math.log10(raw));
    const step = Math.max(1, [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw));
    const ticks = [];
    for (let value = 0; value < max + step; value += step) {
        ticks.push(value);
    }
    return ticks;
};

const svgElement = (parent, name, attributes = {}) => {
    const element = document.createElementNS(SVG_NS, name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    parent.appendChild(element);
    return element;
};

// Translated labels, set by render().
let strings = {};

const dayLabel = (day) => (day === 1 ? strings.tomorrow : strings.inDays.replace("{days}", day));

const cardsLabel = (count) => {
    const singular = count === 1 || (count === 0 && strings.zeroIsSingular);
    return (singular ? strings.cardOne : strings.cardOther).replace("{count}", count);
};

const tooltip = () => document.getElementById("tooltip");

// Next to the cursor, kept inside the visible area: flipped above or to the
// left of the cursor when there is no room below or to the right.
const showTooltip = (event, html) => {
    const box = tooltip();
    box.innerHTML = html;
    box.style.opacity = 1;
    const gap = 15;
    const width = box.offsetWidth;
    const height = box.offsetHeight;
    const viewWidth = document.documentElement.clientWidth;
    const viewHeight = document.documentElement.clientHeight;
    const x = event.clientX + gap + width <= viewWidth
        ? event.clientX + gap
        : event.clientX - gap - width;
    const y = event.clientY + gap + height <= viewHeight
        ? event.clientY + gap
        : event.clientY - gap - height;
    box.style.left = `${Math.max(0, x)}px`;
    box.style.top = `${Math.max(0, y)}px`;
};

const hideTooltip = () => {
    tooltip().style.opacity = 0;
};

const renderChart = (container, title, counts, yMax) => {
    const section = document.createElement("div");
    section.className = "graph";
    section.innerHTML = `<h1>${title}</h1>`;
    container.appendChild(section);

    const svg = svgElement(section, "svg", { viewBox: `0 0 ${WIDTH} ${HEIGHT}` });
    const horizon = counts.length;
    const innerWidth = WIDTH - MARGIN.left - MARGIN.right;
    const bottom = HEIGHT - MARGIN.bottom;
    const innerHeight = bottom - MARGIN.top;

    // Days are bins [day, day + 1), from tomorrow (1) to the horizon.
    const x = (day) => MARGIN.left + ((day - 1) / horizon) * innerWidth;

    const countTicks = niceTicks(yMax, 4);
    const countTop = countTicks[countTicks.length - 1];
    const y = (value) => bottom - (value / countTop) * innerHeight;

    const cumulative = [];
    counts.reduce((total, count) => {
        cumulative.push(total + count);
        return total + count;
    }, 0);
    const total = cumulative[cumulative.length - 1] || 0;
    const totalTicks = niceTicks(total, 4);
    const totalTop = totalTicks[totalTicks.length - 1];
    const y2 = (value) => bottom - (value / totalTop) * innerHeight;

    // Left axis: card counts, with grid lines.
    countTicks.forEach((value) => {
        const tick = svgElement(svg, "g", { class: "tick" });
        svgElement(tick, "line", { x1: MARGIN.left, x2: WIDTH - MARGIN.right, y1: y(value), y2: y(value) });
        svgElement(tick, "text", { x: MARGIN.left - 6, y: y(value), "text-anchor": "end", dy: "0.32em" })
            .textContent = value;
    });

    // Right axis: running total.
    totalTicks.forEach((value) => {
        const tick = svgElement(svg, "g", { class: "tick" });
        svgElement(tick, "text", { x: WIDTH - MARGIN.right + 6, y: y2(value), dy: "0.32em" })
            .textContent = value;
    });

    // Bottom axis: days from today.
    niceTicks(horizon, 9)
        .filter((day) => day >= 1 && day <= horizon + 1)
        .forEach((day) => {
            const tick = svgElement(svg, "g", { class: "tick" });
            svgElement(tick, "line", { x1: x(day), x2: x(day), y1: bottom, y2: bottom + 6 });
            svgElement(tick, "text", { x: x(day), y: bottom + 9, "text-anchor": "middle", dy: "0.71em" })
                .textContent = day;
        });

    // Bars.
    counts.forEach((count, index) => {
        const day = index + 1;
        if (!count) {
            return;
        }
        svgElement(svg, "rect", {
            x: x(day) + 1,
            width: Math.max(x(day + 1) - x(day) - 1, 0.5),
            y: y(count),
            height: bottom - y(count),
            fill: greens(0.7 - (0.4 * index) / Math.max(horizon - 1, 1)),
        });
    });

    // Running total, as a translucent area.
    if (total) {
        const points = [[x(1), y2(0)]].concat(cumulative.map((value, index) => [x(index + 2), y2(value)]));
        const line = points.map(([px, py]) => `${px},${py}`).join(" L");
        svgElement(svg, "path", {
            class: "cumulative-overlay",
            d: `M${x(1)},${bottom} L${line} L${x(horizon + 1)},${bottom} Z`,
        });
    }

    // Full-height hover columns, one per day.
    const hover = svgElement(svg, "g", { class: "hover-columns" });
    counts.forEach((count, index) => {
        const day = index + 1;
        const column = svgElement(hover, "rect", {
            x: x(day),
            width: x(day + 1) - x(day),
            y: MARGIN.top,
            height: innerHeight,
        });
        const html = `${dayLabel(day)}${strings.colon}<br>${cardsLabel(count)}<br>`
            + `${strings.runningTotal}${strings.colon} ${cumulative[index]}`;
        column.addEventListener("mousemove", (event) => showTooltip(event, html));
        column.addEventListener("mouseout", hideTooltip);
    });
};

const render = (data) => {
    strings = data.strings;
    const container = document.getElementById("charts");
    container.innerHTML = "";
    hideTooltip();
    // Same vertical scale on both graphs, so that they compare at a glance.
    const yMax = Math.max(1, ...data.before, ...data.after);
    renderChart(container, strings.before, data.before, yMax);
    renderChart(container, strings.after, data.after, yMax);
};
