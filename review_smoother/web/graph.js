// Before/after preview graphs, styled after Anki's "Future Due" statistics
// graph (written from scratch: Anki's own code is AGPL, this add-on is MIT).
// Entry point: render({ before: [...], after: [...], strings: {...} }), where
// each array holds one count per day (index 0 = tomorrow) and `strings` holds
// the translated labels (see Translator.graph_strings in i18n.py).

const SVG_NS = "http://www.w3.org/2000/svg";
const MARGIN = { top: 20, right: 40, bottom: 25, left: 40 };
// Below this, a graph is drawn at this size and the page scrolls.
const MIN_WIDTH = 300;
const MIN_HEIGHT = 120;

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

// Round step (1, 2, 5 × 10^n, at least 1) giving about `count` ticks over `range`.
const niceStep = (range, count) => {
    const raw = Math.max(range, 1) / count;
    const power = 10 ** Math.floor(Math.log10(raw));
    return Math.max(1, [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw));
};

// Round tick values from 0 up to at least `max`.
const niceTicks = (max, count) => {
    const step = niceStep(max, count);
    const ticks = [];
    for (let value = 0; value < max + step; value += step) {
        ticks.push(value);
    }
    return ticks;
};

// Round day numbers between `start` and `end` (both included), day 1 or later.
const dayTicks = (start, end, count) => {
    const step = niceStep(end - start, count);
    const ticks = [];
    for (let day = Math.max(Math.ceil(start / step) * step, step); day <= end; day += step) {
        ticks.push(day);
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

// A titled section with an empty svg element, sized by graph.css, and an
// optional legend (list of [class, label]) between them.
const addSection = (container, title, legend = []) => {
    const section = document.createElement("div");
    section.className = "graph";
    section.innerHTML = `<h1>${title}</h1>`;
    if (legend.length) {
        const list = document.createElement("div");
        list.className = "legend";
        list.innerHTML = legend
            .map(([kind, label]) => `<span><i class="swatch ${kind}"></i>${label}</span>`)
            .join("");
        section.appendChild(list);
    }
    container.appendChild(section);
    return svgElement(section, "svg");
};

// "+2" / "−1" (typographic minus).
const signed = (value) => (value > 0 ? `+${value}` : `−${-value}`);

// Days shown, as bins [day, day + 1): from `start` to `end` (exclusive).
// Both graphs share it; the mouse wheel zooms it, dragging pans it, a double
// click shows everything again (see the listeners at the end of the file).
let view = null;

const fullView = (horizon) => ({ start: 1, end: horizon + 1 });

// What the graphs show: `horizon`, the days shown (`view`), the shared count
// scale (`countTop`, `countTicks`), and for `before` and `after` the counts
// with their running-total scale (`totalTop`, `totalTicks`). The "after"
// graph also holds `reference`, the counts before smoothing (the difference
// is drawn on each day), and `curve`, the target curve when there is one
// (custom curve), or null. `final` is false while animating (fractional
// counts, no hover columns).
const sum = (values) => values.reduce((total, value) => total + value, 0);
const last = (values) => values[values.length - 1];

const scene = (data, shownView) => {
    // Same vertical scale on both graphs, so that they compare at a glance,
    // and over all days: zooming only narrows the days shown.
    const curve = data.curve || null;
    const countTicks = niceTicks(
        Math.max(1, ...data.before, ...data.after, ...(curve || [])),
        4,
    );
    const graph = (counts, reference = null, target = null) => {
        const totalTicks = niceTicks(sum(counts), 4);
        return { counts, totalTop: last(totalTicks), totalTicks, reference, curve: target };
    };
    return {
        horizon: data.before.length,
        view: shownView,
        countTop: last(countTicks),
        countTicks,
        before: graph(data.before),
        after: graph(data.after, data.before, curve),
        final: true,
    };
};

// Like Anki's statistics graphs: d3 transitions of 600 ms, eased with
// d3's default cubic in-out.
const ANIMATION_MS = 600;
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
const lerp = (from, to, t) => from + (to - from) * t;

// Between two scenes, day by day; ticks are those of the scene reached,
// shown once within the scale.
const between = (from, to, t) => {
    const mix = (from, to) => Array.from(
        { length: Math.max(from.length, to.length) },
        (_, i) => lerp(from[i] || 0, to[i] || 0, t),
    );
    const graph = (a, b) => ({
        counts: mix(a.counts, b.counts),
        totalTop: lerp(a.totalTop, b.totalTop, t),
        totalTicks: b.totalTicks,
        reference: b.reference && mix(a.reference || a.counts, b.reference),
        // A curve appearing grows out of the bars.
        curve: b.curve && mix(a.curve || a.counts, b.curve),
    });
    return {
        horizon: lerp(from.horizon, to.horizon, t),
        view: {
            start: lerp(from.view.start, to.view.start, t),
            end: lerp(from.view.end, to.view.end, t),
        },
        countTop: lerp(from.countTop, to.countTop, t),
        countTicks: to.countTicks,
        before: graph(from.before, to.before),
        after: graph(from.after, to.after),
        final: false,
    };
};

const renderChart = (svg, shown, chart, id) => {
    // Drawn at the size the page gives it (see graph.css), so that text keeps
    // its size whatever the window size; redrawn when the window is resized.
    const WIDTH = Math.max(svg.clientWidth, MIN_WIDTH);
    const HEIGHT = Math.max(svg.clientHeight, MIN_HEIGHT);
    svg.setAttribute("viewBox", `0 0 ${WIDTH} ${HEIGHT}`);
    svg.dataset.width = WIDTH;
    const { counts, totalTop } = chart;
    const { horizon, countTop } = shown;
    const innerWidth = WIDTH - MARGIN.left - MARGIN.right;
    const bottom = HEIGHT - MARGIN.bottom;
    const innerHeight = bottom - MARGIN.top;

    const { start, end } = shown.view;
    const x = (day) => MARGIN.left + ((day - start) / (end - start)) * innerWidth;
    const visible = (day) => day + 1 > start && day < end;

    // What is drawn in the plot area is cut at its edges when zoomed in.
    const clip = svgElement(svgElement(svg, "defs"), "clipPath", { id });
    svgElement(clip, "rect", { x: MARGIN.left, y: 0, width: innerWidth, height: HEIGHT });
    const plot = () => svgElement(svg, "g", { "clip-path": `url(#${id})` });

    const y = (value) => bottom - (value / countTop) * innerHeight;
    const within = (top) => (value) => value <= top * (1 + 1e-9);

    const cumulative = [];
    counts.reduce((total, count) => {
        cumulative.push(total + count);
        return total + count;
    }, 0);
    const total = last(cumulative) || 0;
    const y2 = (value) => bottom - (value / totalTop) * innerHeight;

    // Left axis: card counts, with grid lines.
    shown.countTicks.filter(within(countTop)).forEach((value) => {
        const tick = svgElement(svg, "g", { class: "tick" });
        svgElement(tick, "line", { x1: MARGIN.left, x2: WIDTH - MARGIN.right, y1: y(value), y2: y(value) });
        svgElement(tick, "text", { x: MARGIN.left - 6, y: y(value), "text-anchor": "end", dy: "0.32em" })
            .textContent = value;
    });

    // Right axis: running total.
    chart.totalTicks.filter(within(totalTop)).forEach((value) => {
        const tick = svgElement(svg, "g", { class: "tick" });
        svgElement(tick, "text", { x: WIDTH - MARGIN.right + 6, y: y2(value), dy: "0.32em" })
            .textContent = value;
    });

    // Bottom axis: days from today, over the days shown.
    dayTicks(start, end, 9).forEach((day) => {
        const tick = svgElement(svg, "g", { class: "tick" });
        svgElement(tick, "line", { x1: x(day), x2: x(day), y1: bottom, y2: bottom + 6 });
        svgElement(tick, "text", { x: x(day), y: bottom + 9, "text-anchor": "middle", dy: "0.71em" })
            .textContent = day;
    });

    // Bars.
    const bars = plot();
    counts.forEach((count, index) => {
        const day = index + 1;
        if (!count || !visible(day)) {
            return;
        }
        svgElement(bars, "rect", {
            x: x(day) + 1,
            width: Math.max(x(day + 1) - x(day) - 1, 0.5),
            y: y(count),
            height: bottom - y(count),
            fill: greens(0.7 - (0.4 * index) / Math.max(horizon - 1, 1)),
        });
    });

    // Difference with the counts before smoothing, day by day: cards added
    // as a coloured top of the bar, cards removed as a dashed outline up to
    // the former height.
    if (chart.reference) {
        const changes = plot();
        counts.forEach((count, index) => {
            const day = index + 1;
            const former = chart.reference[index] || 0;
            if (Math.abs(count - former) < 0.01 || !visible(day)) {
                return;
            }
            const high = Math.max(count, former);
            const low = Math.min(count, former);
            svgElement(changes, "rect", {
                class: count > former ? "added" : "removed",
                x: x(day) + 1,
                width: Math.max(x(day + 1) - x(day) - 1, 0.5),
                y: y(high),
                height: y(low) - y(high),
            });
        });
    }

    // Target curve, as steps: one level per day.
    if (chart.curve) {
        const steps = chart.curve
            .map((value, index) => `${index ? "L" : "M"}${x(index + 1)},${y(value)} L${x(index + 2)},${y(value)}`)
            .join(" ");
        svgElement(plot(), "path", { class: "target-curve", d: steps });
    }

    // Running total, as a translucent area.
    if (total && totalTop) {
        const points = [[x(1), y2(0)]].concat(cumulative.map((value, index) => [x(index + 2), y2(value)]));
        const line = points.map(([px, py]) => `${px},${py}`).join(" L");
        svgElement(plot(), "path", {
            class: "cumulative-overlay",
            d: `M${x(1)},${bottom} L${line} L${x(counts.length + 1)},${bottom} Z`,
        });
    }

    if (!shown.final) {
        return;
    }

    // Full-height hover columns, one per day.
    const hover = svgElement(plot(), "g", { class: "hover-columns" });
    counts.forEach((count, index) => {
        const day = index + 1;
        if (!visible(day)) {
            return;
        }
        const column = svgElement(hover, "rect", {
            x: x(day),
            width: x(day + 1) - x(day),
            y: MARGIN.top,
            height: innerHeight,
        });
        let html = `${dayLabel(day)}${strings.colon}<br>${cardsLabel(count)}`;
        const former = chart.reference ? chart.reference[index] || 0 : count;
        if (count !== former) {
            html += ` (${strings.vsBefore.replace("{diff}", signed(count - former))})`;
        }
        html += `<br>`;
        if (chart.curve) {
            html += `${strings.targetCurve}${strings.colon} ${chart.curve[index]}<br>`;
        }
        html += `${strings.runningTotal}${strings.colon} ${cumulative[index]}`;
        column.addEventListener("mousemove", (event) => {
            if (!drag) {
                showTooltip(event, html);
            }
        });
        column.addEventListener("mouseout", hideTooltip);
    });
};

// Last data given to render(), to redraw when the window is resized or the
// view changes.
let lastData = null;
// Scene last drawn, and the animation towards the current data, if running:
// { from: scene, start: time }.
let shown = null;
let animation = null;

const currentScene = () => {
    const goal = scene(lastData, view);
    if (!animation) {
        return goal;
    }
    const t = (performance.now() - animation.start) / ANIMATION_MS;
    if (t >= 1) {
        animation = null;
        return goal;
    }
    return between(animation.from, goal, ease(Math.max(t, 0)));
};

const draw = () => {
    shown = currentScene();
    const container = document.getElementById("charts");
    container.innerHTML = "";
    container.classList.toggle("zoomed", view.end - view.start < lastData.before.length);
    hideTooltip();
    // Legend of the "after" graph: only what the data shows (final data, so
    // that it does not change while animating).
    const data = lastData;
    const legend = [];
    if (data.after.some((count, i) => count > data.before[i])) {
        legend.push(["added", strings.addedCards]);
    }
    if (data.after.some((count, i) => count < data.before[i])) {
        legend.push(["removed", strings.removedCards]);
    }
    if (data.curve) {
        legend.push(["target-curve", strings.targetCurve]);
    }
    // Both sections first, so that each graph is measured at its final size.
    const beforeSvg = addSection(container, strings.before);
    const afterSvg = addSection(container, strings.after, legend);
    renderChart(beforeSvg, shown, shown.before, "clip-before");
    renderChart(afterSvg, shown, shown.after, "clip-after");
    if (animation) {
        requestDraw();
    }
};

// New data from Python (deck, horizon, option): animated from what is shown,
// like Anki's graphs when their period changes.
const render = (data) => {
    const horizon = data.before.length;
    // A new deck or option keeps the zoom; a new horizon shows everything.
    if (!lastData || lastData.before.length !== horizon) {
        view = fullView(horizon);
    }
    lastData = data;
    strings = data.strings;
    if (shown) {
        animation = { from: shown, start: performance.now() };
        requestDraw();
    } else {
        draw();
    }
};

// Redraw at most once per frame.
let drawPending = false;
const requestDraw = () => {
    if (!lastData || drawPending) {
        return;
    }
    drawPending = true;
    requestAnimationFrame(() => {
        drawPending = false;
        draw();
    });
};

window.addEventListener("resize", requestDraw);

// Zooming in no further than this many days.
const MIN_SPAN = 7;
const ZOOM_STEP = 1.25;

// Days shown, kept within the horizon, `span` days wide.
const setView = (start, span) => {
    const horizon = lastData.before.length;
    span = Math.min(Math.max(span, Math.min(MIN_SPAN, horizon)), horizon);
    start = Math.min(Math.max(start, 1), horizon + 1 - span);
    view = { start, end: start + span };
    animation = null; // zooming follows the mouse, without animation
    requestDraw();
};

// Day under the mouse, and the width of the plot area in screen pixels.
const pointer = (svg, event) => {
    const rect = svg.getBoundingClientRect();
    const scale = rect.width / Number(svg.dataset.width);
    const left = rect.left + MARGIN.left * scale;
    const width = rect.width - (MARGIN.left + MARGIN.right) * scale;
    const ratio = Math.min(Math.max((event.clientX - left) / width, 0), 1);
    return { day: view.start + ratio * (view.end - view.start), width };
};

const charts = document.getElementById("charts");

// Wheel: zoom the days in or out around the day under the mouse.
charts.addEventListener("wheel", (event) => {
    const svg = event.target.closest("svg");
    if (!svg || !lastData) {
        return;
    }
    event.preventDefault();
    const { day } = pointer(svg, event);
    const span = view.end - view.start;
    const newSpan = event.deltaY < 0 ? span / ZOOM_STEP : span * ZOOM_STEP;
    setView(day - ((day - view.start) * newSpan) / span, newSpan);
}, { passive: false });

// Drag: move the days shown, when zoomed in.
let drag = null;

charts.addEventListener("mousedown", (event) => {
    const svg = event.target.closest("svg");
    if (!svg || !lastData || event.button !== 0) {
        return;
    }
    event.preventDefault();
    drag = { x: event.clientX, start: view.start, width: pointer(svg, event).width };
    charts.classList.add("dragging");
    hideTooltip();
});

window.addEventListener("mousemove", (event) => {
    if (!drag) {
        return;
    }
    const span = view.end - view.start;
    setView(drag.start - ((event.clientX - drag.x) / drag.width) * span, span);
});

window.addEventListener("mouseup", () => {
    drag = null;
    charts.classList.remove("dragging");
});

// Double click: show all days again.
charts.addEventListener("dblclick", () => {
    if (lastData) {
        view = fullView(lastData.before.length);
        animation = null;
        requestDraw();
    }
});
