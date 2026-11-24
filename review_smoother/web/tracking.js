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

  // The custom curve (smoothing.custom_curve), its totals over the first
  // `days` days, from one row's settings; null if one is missing.
  function curveTotals(set) {
    var keys = ["tomorrow", "drop_day2", "drop_day3", "floor", "strength", "slope_x10000"];
    for (var i = 0; i < keys.length; i++) {
      if (typeof set[keys[i]] !== "number") return null;
    }
    var aboveFloor = set.tomorrow - set.drop_day2 - set.drop_day3 - set.floor;
    var slope = set.slope_x10000 / 10000;
    var sums = {};
    var total = 0;
    for (var day = 1; day <= 365; day++) {
      var value;
      if (day === 1) value = set.tomorrow;
      else if (day === 2) value = set.tomorrow - set.drop_day2;
      else if (day <= 90) {
        value = set.floor + Math.floor(aboveFloor * Math.exp(-(day - 3) / Math.max(set.strength, 1e-9)));
      } else value = Math.floor(set.floor - slope * (day - 90) + 0.5);
      total += Math.max(0, value);
      sums[day] = total;
    }
    return sums;
  }

  // Totals computed from the settings, added after a table's own columns
  // (shown greyed, never stored); the remark always last.
  function addTotals(t) {
    var keyOf = [];
    var found = {};
    t.columns.forEach(function (name, c) {
      var key = S.keys[name.replace(/\s+/g, "").toLowerCase()];
      keyOf[c] = key;
      if (key) found[key] = true;
    });
    var withTotals = found.tomorrow && found.floor && found.slope_x10000;
    var order = [];
    var last = [];
    keyOf.forEach(function (key, c) {
      (key === "remark" ? last : order).push(c);
    });
    var columns = order.map(function (c) { return t.columns[c]; });
    t.computed = {};
    if (withTotals) {
      S.totals.forEach(function (total) {
        t.computed[columns.length] = true;
        columns.push(total[1]);
      });
    }
    last.forEach(function (c) { columns.push(t.columns[c]); });
    t.rows = t.rows.map(function (row) {
      var values = [row[0]];
      order.forEach(function (c) { values.push(row[c + 1]); });
      if (withTotals) {
        var set = {};
        keyOf.forEach(function (key, c) {
          if (key) set[key] = row[c + 1];
        });
        var sums = curveTotals(set);
        S.totals.forEach(function (total) {
          values.push(sums ? sums[total[0]] : null);
        });
      }
      last.forEach(function (c) { values.push(row[c + 1]); });
      return values;
    });
    t.columns = columns;
    t.keys = order.map(function (c) { return keyOf[c]; })
      .concat(withTotals ? S.totals.map(function () { return undefined; }) : [])
      .concat(last.map(function (c) { return keyOf[c]; }));
  }
  tables.forEach(addTotals);

  var numberFormat = new Intl.NumberFormat(S.locale, { maximumFractionDigits: 4 });
  var statFormat = new Intl.NumberFormat(S.locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  var slopeFormat = new Intl.NumberFormat(S.locale, { maximumFractionDigits: 2 });
  var wholeSlopeFormat = new Intl.NumberFormat(S.locale, { maximumFractionDigits: 0 });
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
      // "v2": choices remembered by name since 2026-11-19 (an index before).
      if (value === undefined) return window.localStorage.getItem("rs-tracking-v2-" + key);
      window.localStorage.setItem("rs-tracking-v2-" + key, value);
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

  // Shown by default: new cards of the day over 3 months (author, 2026-11-19).
  var DEFAULT_KEY = "new_cards";
  var DEFAULT_RANGE = 92;
  var storedRange = store("range");
  var state = {
    trend: store("trend") !== "0",
    table: +(store("table") || 0),
    range: storedRange === null || storedRange === undefined ? DEFAULT_RANGE : +storedRange,
    column: {},
  };
  if (!(state.table < tables.length)) state.table = 0;

  root.innerHTML = "";
  var tabs = el("div", "rs-tabs");
  var controls = el("div", "rs-controls");
  var headline = el("div", "rs-headline");
  var chart = el("div", "rs-chart");
  var tip = el("div", "rs-tip");
  var tableWrap = el("div", "rs-table");
  var legend = el("div", "rs-legend");
  if (tables.length > 1) root.appendChild(tabs);
  root.appendChild(controls);
  root.appendChild(headline);
  chart.appendChild(tip);
  root.appendChild(chart);
  root.appendChild(legend);
  root.appendChild(tableWrap);

  var select = el("select");
  var label = el("label", "rs-label");
  label.appendChild(el("span", "", S.column));
  label.appendChild(select);
  var ranges = el("div", "rs-ranges");
  var trendButton = el("button", "", S.trend);
  trendButton.type = "button";
  var buttons = el("div", "rs-ranges");
  buttons.appendChild(ranges);
  buttons.appendChild(trendButton);
  controls.appendChild(label);
  controls.appendChild(buttons);

  // Mean, median, moving average and trend line (asked 2026-11-23): over
  // the range shown; the trend shown or hidden by its button (remembered).
  function showTrendButton() {
    trendButton.className = state.trend ? "rs-on" : "";
    trendButton.setAttribute("aria-pressed", state.trend ? "true" : "false");
  }
  trendButton.addEventListener("click", function () {
    state.trend = !state.trend;
    store("trend", state.trend ? "1" : "0");
    showTrendButton();
    drawChart();
  });
  showTrendButton();

  select.addEventListener("change", function () {
    state.column[state.table] = +select.value;
    store("column-" + state.table, current().columns[+select.value]);
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
    if (saved === undefined) {
      saved = t.columns.indexOf(store("column-" + state.table));
      if (saved < 0) saved = t.keys.indexOf(DEFAULT_KEY);
      if (saved < 0) saved = columns[0];
    }
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
    t.columns.forEach(function (name, c) {
      row.appendChild(el("th", t.computed[c] ? "rs-computed" : t.keys[c] === "remark" ? "rs-text" : "", name));
    });
    head.appendChild(row);
    tableNode.appendChild(head);
    var body = el("tbody");
    for (var r = t.rows.length - 1; r >= 0; r--) {
      var values = t.rows[r];
      var tr = el("tr");
      tr.setAttribute("data-date", values[0]);
      tr.appendChild(el("td", "rs-date", dateFormat.format(time(values[0]))));
      for (var c = 1; c <= t.columns.length; c++) {
        var value = values[c];
        // Wide, wrapping cells for the remark only: an empty cell styled so
        // widened its whole column (no slope before 2025-03-08, so no totals).
        var cls = typeof value === "number" ? "rs-num" : t.keys[c - 1] === "remark" ? "rs-text" : "";
        if (t.computed[c - 1]) cls += " rs-computed";
        tr.appendChild(el("td", cls, format(value)));
      }
      body.appendChild(tr);
    }
    tableNode.appendChild(body);
    tableWrap.appendChild(tableNode);
    fitTable();
  }

  // No horizontal scroll bar for a few pixels of overflow (asked
  // 2026-11-24): what is hidden then is at most the last cell's right
  // padding (8px, tracking.css).
  function fitTable() {
    tableWrap.style.overflowX = "";
    tableWrap.style.overflowX = tableWrap.scrollWidth - tableWrap.clientWidth <= 8 ? "hidden" : "auto";
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

  // Days of the moving average: a week over 1 or 3 months, a month beyond.
  function movingDays() {
    return state.range && state.range <= 92 ? 7 : 30;
  }

  // The shown range's days, each with its value and its moving average
  // (mean of the known values of the `movingDays()` days ending there, taken
  // from the whole history, so the range's first days have one too; none
  // while fewer than half those days are known).
  function points() {
    var t = current();
    var c = state.column[state.table] + 1;
    var all = [];
    t.rows.forEach(function (row) {
      all.push({ t: time(row[0]), v: typeof row[c] === "number" ? row[c] : null });
    });
    var days = movingDays();
    var known = all.filter(function (p) {
      return p.v !== null;
    });
    var first = 0;
    var next = 0;
    var sum = 0;
    all.forEach(function (p) {
      while (next < known.length && known[next].t <= p.t) sum += known[next++].v;
      while (first < next && known[first].t <= p.t - days * DAY) sum -= known[first++].v;
      var count = next - first;
      p.avg = count && count * 2 >= days ? sum / count : null;
    });
    var last = all.length ? all[all.length - 1].t : 0;
    var from = state.range ? last - (state.range - 1) * DAY : -Infinity;
    return all.filter(function (p) {
      return p.t >= from;
    });
  }

  function median(values) {
    var sorted = values.slice().sort(function (a, b) {
      return a - b;
    });
    var middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  }

  // Least squares line through the known points: value = a + b x day.
  function regression(known) {
    var n = known.length;
    if (n < 2) return null;
    var mx = 0;
    var my = 0;
    known.forEach(function (p) {
      mx += p.t / DAY / n;
      my += p.v / n;
    });
    var sxy = 0;
    var sxx = 0;
    known.forEach(function (p) {
      var dx = p.t / DAY - mx;
      sxy += dx * (p.v - my);
      sxx += dx * dx;
    });
    if (!sxx) return null;
    var b = sxy / sxx;
    return {
      perDay: b,
      at: function (t) {
        return my + b * (t / DAY - mx);
      },
    };
  }

  function drawHeadline(list) {
    headline.innerHTML = "";
    var values = [];
    list.forEach(function (p) {
      if (p.v !== null) values.push(p.v);
    });
    for (var i = list.length - 1; i >= 0; i--) {
      if (list[i].v !== null) {
        headline.appendChild(el("span", "rs-value", format(list[i].v)));
        headline.appendChild(el("span", "rs-when", dateFormat.format(list[i].t)));
        break;
      }
    }
    if (values.length > 1) {
      var mean = values.reduce(function (a, b) {
        return a + b;
      }, 0) / values.length;
      headline.appendChild(el("span", "rs-stats",
        S.mean.replace("{value}", statFormat.format(mean)) + " \u00b7 " +
        S.median.replace("{value}", statFormat.format(median(values)))));
    }
  }

  // Shown with two series or more: the column, then each trend.
  function drawLegend(items) {
    legend.innerHTML = "";
    if (items.length < 2) return;
    items.forEach(function (item) {
      var entry = el("span", "rs-key");
      entry.appendChild(el("span", "rs-swatch " + item[0]));
      entry.appendChild(document.createTextNode(item[1]));
      legend.appendChild(entry);
    });
  }

  function drawChart() {
    var list = points();
    drawHeadline(list);
    var old = chart.querySelector("svg");
    if (old) chart.removeChild(old);
    tip.style.display = "none";
    drawLegend([]);
    var known = list.filter(function (p) {
      return p.v !== null;
    });
    if (!known.length) return;
    var trend = state.trend && known.length > 1;
    var line = trend ? regression(known) : null;

    var width = Math.max(chart.clientWidth || 600, 280);
    var height = 220;
    var m = { top: 10, right: 14, bottom: 24, left: 8 };
    var low = Infinity;
    var high = -Infinity;
    known.forEach(function (p) {
      low = Math.min(low, p.v);
      high = Math.max(high, p.v);
    });
    if (line) {
      [list[0].t, list[list.length - 1].t].forEach(function (t) {
        low = Math.min(low, line.at(t));
        high = Math.max(high, line.at(t));
      });
    }
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
    svg("path", { d: path, class: trend ? "rs-line rs-raw" : "rs-line" }, graph);
    var items = [["rs-raw", current().columns[state.column[state.table]]]];
    if (trend) {
      var avgPath = "";
      pen = false;
      list.forEach(function (p) {
        if (p.avg === null) {
          pen = false;
          return;
        }
        avgPath += (pen ? "L" : "M") + x(p.t).toFixed(1) + "," + y(p.avg).toFixed(1);
        pen = true;
      });
      if (avgPath) {
        svg("path", { d: avgPath, class: "rs-avg" }, graph);
        items.push(["rs-avg", S.moving.replace("{days}", movingDays())]);
      }
      if (line) {
        svg("line", {
          x1: x(start), y1: y(line.at(start)), x2: x(end), y2: y(line.at(end)), class: "rs-reg",
        }, graph);
        var perMonth = line.perDay * 365.25 / 12;
        var shown = (Math.abs(perMonth) >= 10 ? wholeSlopeFormat : slopeFormat).format(perMonth);
        if (perMonth > 0 && shown !== "0") shown = "+" + shown;
        items.push(["rs-reg", S.regression.replace("{value}", shown)]);
      }
    }
    drawLegend(items);
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
    function nearest(event) {
      var box = graph.getBoundingClientRect();
      var px = ((event.clientX - box.left) / box.width) * width;
      var best = null;
      known.forEach(function (p) {
        if (!best || Math.abs(x(p.t) - px) < Math.abs(x(best.t) - px)) best = p;
      });
      return best;
    }
    function move(event) {
      var box = graph.getBoundingClientRect();
      var best = nearest(event);
      var cx = x(best.t);
      cross.setAttribute("x1", cx);
      cross.setAttribute("x2", cx);
      mark.setAttribute("cx", cx);
      mark.setAttribute("cy", y(best.v));
      cross.style.display = mark.style.display = "";
      tip.innerHTML = "";
      tip.appendChild(el("strong", "", format(best.v)));
      tip.appendChild(el("span", "", dateFormat.format(best.t)));
      if (trend && best.avg !== null) {
        tip.appendChild(el("span", "rs-tip-avg", "~ " + statFormat.format(best.avg)));
      }
      tip.style.display = "block";
      var left = (cx / width) * box.width;
      var room = chart.clientWidth - tip.offsetWidth;
      tip.style.left = Math.max(0, Math.min(room, left - tip.offsetWidth / 2)) + "px";
    }
    hit.addEventListener("pointermove", move);
    hit.addEventListener("pointerdown", move);
    hit.addEventListener("pointerleave", hide);
    // A click (or tap) on a day shows its row in the table.
    hit.addEventListener("click", function (event) {
      showRow(new Date(nearest(event).t).toISOString().slice(0, 10));
    });
    chart.appendChild(graph);
  }

  // Scroll the table to a day's row, just under its header, and mark the
  // row; the page only scrolls as much as needed to show the table.
  function showRow(day) {
    var row = tableWrap.querySelector('tr[data-date="' + day + '"]');
    if (!row) return;
    var picked = tableWrap.querySelector("tr.rs-picked");
    if (picked) picked.className = "";
    row.className = "rs-picked";
    var head = tableWrap.querySelector("thead");
    var offset = row.getBoundingClientRect().top - tableWrap.getBoundingClientRect().top;
    var top = tableWrap.scrollTop + offset - (head ? head.offsetHeight : 0);
    if (tableWrap.scrollIntoView) tableWrap.scrollIntoView({ block: "nearest" });
    tableWrap.scrollTop = top;
  }

  function show() {
    buildTabs();
    buildSelect();
    buildRanges();
    buildTable();
    drawChart();
  }

  show();
  // Inter (tracking.css) may load after the table is drawn.
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitTable);
  var pending = false;
  window.addEventListener("resize", function () {
    if (pending || !document.body.contains(chart)) return;
    pending = true;
    setTimeout(function () {
      pending = false;
      drawChart();
      fitTable();
    }, 100);
  });
})();
