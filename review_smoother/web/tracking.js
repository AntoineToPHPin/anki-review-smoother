// Tracking card of Review Smoother: a graph and a table drawn from the
// note's history (JSON in #rs-history, see tracking.py). Runs in Anki's
// card webview (desktop and AnkiDroid): plain ES5-friendly code, no library,
// wrapped so that the desktop reviewer can run it again on the same page.
(function () {
  "use strict";
  var S = /*STRINGS*/null;
  var root = document.getElementById("rs-tracking");
  var source = document.getElementById("rs-history");
  if (!root || !source || !S) return;
  var SVG = "http://www.w3.org/2000/svg";

  var data;
  try {
    data = JSON.parse(source.textContent);
  } catch (e) {
    try {
      // &nbsp; added between values by the editor: not JSON whitespace.
      data = JSON.parse(source.textContent.replace(/\u00a0/g, " "));
    } catch (e2) {
      root.textContent = S.invalid;
      return;
    }
  }
  var tables = (data && data.tables) || [];
  if (!tables.length) {
    root.textContent = S.empty;
    return;
  }

  var numberFormat = new Intl.NumberFormat(S.locale, { maximumFractionDigits: 4 });
  var dateFormat = new Intl.DateTimeFormat(S.locale, {
    day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC",
  });
  var monthFormat = new Intl.DateTimeFormat(S.locale, {
    month: "short", year: "2-digit", timeZone: "UTC",
  });
  var DAY = 86400000;

  function time(text) {
    return Date.UTC(+text.slice(0, 4), +text.slice(5, 7) - 1, +text.slice(8, 10));
  }
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function svg(tag, attrs, parent) {
    var node = document.createElementNS(SVG, tag);
    for (var k in attrs) node.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(node);
    return node;
  }
  function format(value) {
    if (value === null || value === undefined) return "";
    return typeof value === "number" ? numberFormat.format(value) : String(value);
  }
  function store(key, value) {
    try {
      if (value === undefined) return window.localStorage.getItem("rs-tracking-" + key);
      window.localStorage.setItem("rs-tracking-" + key, value);
    } catch (e) {
      return null;
    }
  }
  // Columns holding at least one number can be drawn.
  function numericColumns(t) {
    var result = [];
    for (var c = 0; c < t.columns.length; c++) {
      for (var r = 0; r < t.rows.length; r++) {
        if (typeof t.rows[r][c + 1] === "number") {
          result.push(c);
          break;
        }
      }
    }
    return result;
  }

  var state = { table: +(store("table") || 0), range: +(store("range") || 0), column: {} };
  if (!(state.table < tables.length)) state.table = 0;

  root.innerHTML = "";
  var tabs = el("div", "rs-tabs");
  var controls = el("div", "rs-controls");
  var headline = el("div", "rs-headline");
  var chart = el("div", "rs-chart");
  var tip = el("div", "rs-tip");
  var tableWrap = el("div", "rs-table");
  if (tables.length > 1) root.appendChild(tabs);
  root.appendChild(controls);
  root.appendChild(headline);
  chart.appendChild(tip);
  root.appendChild(chart);
  root.appendChild(tableWrap);

  var select = el("select");
  var label = el("label", "rs-label");
  label.appendChild(el("span", "", S.column));
  label.appendChild(select);
  var ranges = el("div", "rs-ranges");
  controls.appendChild(label);
  controls.appendChild(ranges);

  select.addEventListener("change", function () {
    state.column[state.table] = +select.value;
    store("column-" + state.table, select.value);
    drawChart();
  });

  function current() {
    return tables[state.table];
  }

  function buildTabs() {
    tabs.innerHTML = "";
    tables.forEach(function (t, i) {
      var button = el("button", i === state.table ? "rs-on" : "", t.title);
      button.type = "button";
      button.addEventListener("click", function () {
        state.table = i;
        store("table", String(i));
        show();
      });
      tabs.appendChild(button);
    });
  }

  function buildRanges() {
    ranges.innerHTML = "";
    S.ranges.forEach(function (range) {
      var button = el("button", range[0] === state.range ? "rs-on" : "", range[1]);
      button.type = "button";
      button.addEventListener("click", function () {
        state.range = range[0];
        store("range", String(range[0]));
        buildRanges();
        drawChart();
      });
      ranges.appendChild(button);
    });
  }

  function buildSelect() {
    var t = current();
    var columns = numericColumns(t);
    select.innerHTML = "";
    columns.forEach(function (c) {
      var option = el("option", "", t.columns[c]);
      option.value = String(c);
      select.appendChild(option);
    });
    var saved = state.column[state.table];
    if (saved === undefined) saved = +(store("column-" + state.table) || columns[0]);
    if (columns.indexOf(saved) < 0) saved = columns[0];
    state.column[state.table] = saved;
    select.value = String(saved);
  }

  function buildTable() {
    var t = current();
    tableWrap.innerHTML = "";
    var tableNode = el("table");
    var head = el("thead");
    var row = el("tr");
    row.appendChild(el("th", "", S.date));
    t.columns.forEach(function (name) {
      row.appendChild(el("th", "", name));
    });
    head.appendChild(row);
    tableNode.appendChild(head);
    var body = el("tbody");
    for (var r = t.rows.length - 1; r >= 0; r--) {
      var values = t.rows[r];
      var tr = el("tr");
      tr.appendChild(el("td", "rs-date", dateFormat.format(time(values[0]))));
      for (var c = 1; c <= t.columns.length; c++) {
        var value = values[c];
        tr.appendChild(el("td", typeof value === "number" ? "rs-num" : "rs-text", format(value)));
      }
      body.appendChild(tr);
    }
    tableNode.appendChild(body);
    tableWrap.appendChild(tableNode);
  }

  // Round tick values covering [low, high], about `count` of them.
  // Whole steps only for whole values (cards).
  function ticks(low, high, count, whole) {
    var span = high - low;
    var step = Math.pow(10, Math.floor(Math.log(span / count) / Math.LN10));
    var error = span / count / step;
    if (error >= 7.5) step *= 10;
    else if (error >= 3.5) step *= 5;
    else if (error >= 1.5) step *= 2;
    if (whole) step = Math.max(step, 1);
    var result = [];
    for (var v = Math.ceil(low / step) * step; v <= high + step * 1e-9; v += step) {
      result.push(Math.round(v / step) * step);
    }
    return result;
  }

  // First day of each month in [start, end], thinned to at most `count`.
  function monthTicks(start, end, count) {
    var date = new Date(start);
    var months = [];
    var y = date.getUTCFullYear();
    var m = date.getUTCMonth() + (date.getUTCDate() > 1 ? 1 : 0);
    for (;;) {
      var t = Date.UTC(y, m, 1);
      if (t > end) break;
      months.push(t);
      m++;
    }
    var every = Math.max(1, Math.ceil(months.length / count));
    return months.filter(function (_, i) {
      return i % every === 0;
    });
  }

  function points() {
    var t = current();
    var c = state.column[state.table] + 1;
    var list = [];
    var last = t.rows.length ? time(t.rows[t.rows.length - 1][0]) : 0;
    var from = state.range ? last - (state.range - 1) * DAY : -Infinity;
    t.rows.forEach(function (row) {
      var at = time(row[0]);
      if (at >= from) list.push({ t: at, v: typeof row[c] === "number" ? row[c] : null });
    });
    return list;
  }

  function drawHeadline(list) {
    headline.innerHTML = "";
    for (var i = list.length - 1; i >= 0; i--) {
      if (list[i].v !== null) {
        headline.appendChild(el("span", "rs-value", format(list[i].v)));
        headline.appendChild(el("span", "rs-when", dateFormat.format(list[i].t)));
        return;
      }
    }
  }

  function drawChart() {
    var list = points();
    drawHeadline(list);
    var old = chart.querySelector("svg");
    if (old) chart.removeChild(old);
    tip.style.display = "none";
    var known = list.filter(function (p) {
      return p.v !== null;
    });
    if (!known.length) return;

    var width = Math.max(chart.clientWidth || 600, 280);
    var height = 220;
    var m = { top: 10, right: 14, bottom: 24, left: 8 };
    var low = Infinity;
    var high = -Infinity;
    known.forEach(function (p) {
      low = Math.min(low, p.v);
      high = Math.max(high, p.v);
    });
    if (low === high) {
      low -= 1;
      high += 1;
    }
    var whole = known.every(function (p) {
      return p.v % 1 === 0;
    });
    var yTicks = ticks(low, high, 4, whole);
    low = Math.min(low, yTicks[0]);
    high = Math.max(high, yTicks[yTicks.length - 1]);
    var labels = yTicks.map(format);
    var longest = 0;
    labels.forEach(function (text) {
      longest = Math.max(longest, text.length);
    });
    m.left = 10 + longest * 7;
    var start = list[0].t;
    var end = list[list.length - 1].t;
    var span = Math.max(end - start, DAY);
    function x(t) {
      return m.left + ((t - start) / span) * (width - m.left - m.right);
    }
    function y(v) {
      return m.top + (1 - (v - low) / (high - low)) * (height - m.top - m.bottom);
    }

    var graph = svg("svg", {
      viewBox: "0 0 " + width + " " + height, width: width, height: height,
    });
    var axis = svg("g", { class: "rs-axis" }, graph);
    yTicks.forEach(function (v, i) {
      svg("line", { x1: m.left, x2: width - m.right, y1: y(v), y2: y(v), class: "rs-grid" }, axis);
      var text = svg("text", { x: m.left - 6, y: y(v), "text-anchor": "end", dy: "0.32em" }, axis);
      text.textContent = labels[i];
    });
    monthTicks(start, end, Math.max(2, Math.floor((width - m.left) / 70))).forEach(function (t) {
      var text = svg("text", { x: x(t), y: height - 6, "text-anchor": "middle" }, axis);
      text.textContent = monthFormat.format(t);
    });

    var path = "";
    var pen = false;
    list.forEach(function (p) {
      if (p.v === null) {
        pen = false;
        return;
      }
      path += (pen ? "L" : "M") + x(p.t).toFixed(1) + "," + y(p.v).toFixed(1);
      pen = true;
    });
    svg("path", { d: path, class: "rs-line" }, graph);
    var lastPoint = known[known.length - 1];
    svg("circle", { cx: x(lastPoint.t), cy: y(lastPoint.v), r: 4, class: "rs-dot" }, graph);

    var cross = svg("line", { y1: m.top, y2: height - m.bottom, class: "rs-cross" }, graph);
    var mark = svg("circle", { r: 4, class: "rs-dot rs-hover" }, graph);
    cross.style.display = mark.style.display = "none";
    var hit = svg("rect", {
      x: m.left, y: 0, width: Math.max(width - m.left - m.right, 1), height: height,
      class: "rs-hit",
    }, graph);

    function hide() {
      cross.style.display = mark.style.display = tip.style.display = "none";
    }
    function move(event) {
      var box = graph.getBoundingClientRect();
      var px = ((event.clientX - box.left) / box.width) * width;
      var best = null;
      known.forEach(function (p) {
        if (!best || Math.abs(x(p.t) - px) < Math.abs(x(best.t) - px)) best = p;
      });
      var cx = x(best.t);
      cross.setAttribute("x1", cx);
      cross.setAttribute("x2", cx);
      mark.setAttribute("cx", cx);
      mark.setAttribute("cy", y(best.v));
      cross.style.display = mark.style.display = "";
      tip.innerHTML = "";
      tip.appendChild(el("strong", "", format(best.v)));
      tip.appendChild(el("span", "", dateFormat.format(best.t)));
      tip.style.display = "block";
      var left = (cx / width) * box.width;
      var room = chart.clientWidth - tip.offsetWidth;
      tip.style.left = Math.max(0, Math.min(room, left - tip.offsetWidth / 2)) + "px";
    }
    hit.addEventListener("pointermove", move);
    hit.addEventListener("pointerdown", move);
    hit.addEventListener("pointerleave", hide);
    chart.appendChild(graph);
  }

  function show() {
    buildTabs();
    buildSelect();
    buildRanges();
    buildTable();
    drawChart();
  }

  show();
  var pending = false;
  window.addEventListener("resize", function () {
    if (pending || !document.body.contains(chart)) return;
    pending = true;
    setTimeout(function () {
      pending = false;
      drawChart();
    }, 100);
  });
})();
