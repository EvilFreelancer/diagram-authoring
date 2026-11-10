// Arrows for the documentation diagrams. A diagram lays its boxes out with
// HTML and CSS, then names the arrows between them:
//
//   wires([
//     { from: "#b1", to: "#m1", color: "blue" },
//     { from: "#req", to: "#b3", fromSide: "bottom", toSide: "top", label: "writes" },
//   ]);
//
// Each arrow leaves the middle of one side of its first element and ends with
// an arrowhead at the middle of a side of its second. Sides default to right
// and left. route is "straight" or "elbow" (the default when the sides do not
// face each other on one line): an elbow runs along the first side's axis to
// halfway, turns, and finishes along the second side's axis; bend (0..1,
// default 0.5) moves that turn nearer the start or the end, so two elbows
// between the same columns do not run on one line. fromShift and
// toShift move an end along its side by a fraction of the side's length
// (-0.5..0.5). dash draws a dashed line. label is drawn on the longest
// segment, labelShift moves it by [dx, dy] pixels.
//
// Once the arrows are drawn the page records its height on <html
// data-height>, which scripts/render_diagram.py reads to size the picture.
// When the drawing throws - an invalid side, an element that is not in the
// page - the error is stamped on <html data-diagram-error> instead, so the
// renderer reports what went wrong rather than a missing height.

(function () {
  const COLORS = {
    ink: "#374151",
    blue: "#2563eb",
    green: "#16a34a",
    gray: "#9ca3af",
    amber: "#d97706",
    purple: "#7c3aed",
    red: "#dc2626",
  };
  const NS = "http://www.w3.org/2000/svg";

  function el(name, attrs, parent) {
    const node = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  }

  function anchor(rect, side, shift, origin) {
    const allowed = ["left", "top", "right", "bottom"];
    if (!allowed.includes(side)) {
      throw new Error(
        `diagram: invalid side "${side}" - use one of ${allowed.join(", ")}`,
      );
    }
    const s = shift || 0;
    const x0 = rect.left - origin.left;
    const y0 = rect.top - origin.top;
    const box = {
      left: x0,
      top: y0,
      right: x0 + rect.width,
      bottom: y0 + rect.height,
    };
    switch (side) {
      case "left":
        return { x: x0, y: y0 + rect.height * (0.5 + s), axis: "h", dir: -1, rect: box };
      case "top":
        return { x: x0 + rect.width * (0.5 + s), y: y0, axis: "v", dir: -1, rect: box };
      case "bottom":
        return { x: x0 + rect.width * (0.5 + s), y: y0 + rect.height, axis: "v", dir: 1, rect: box };
      default:
        return { x: x0 + rect.width, y: y0 + rect.height * (0.5 + s), axis: "h", dir: 1, rect: box };
    }
  }

  // A wire whose other end lies behind the side it leaves must travel
  // outward first, or its first segment runs back across the box it
  // starts from. STUB is how far it leaves; CLEAR is the distance a
  // rerouted lane keeps off a box edge.
  const STUB = 24;
  const CLEAR = 24;

  // q lies behind the side p exits through when travelling from p toward
  // q would start against p's outward direction.
  function behind(p, q) {
    return p.axis === "h" ? (q.x - p.x) * p.dir < 0
                          : (q.y - p.y) * p.dir < 0;
  }

  // A point STUB px outside the anchor's side, along its exit direction.
  function stub(p) {
    return p.axis === "h" ? { x: p.x + p.dir * STUB, y: p.y }
                          : { x: p.x, y: p.y + p.dir * STUB };
  }

  // A height a wire may travel at without crossing either box: mid-gap
  // when the boxes are stacked, else just above or below both, whichever
  // costs the anchors less travel.
  function horizontalLane(ra, rb, aY, bY) {
    if (ra.bottom < rb.top) return (ra.bottom + rb.top) / 2;
    if (rb.bottom < ra.top) return (rb.bottom + ra.top) / 2;
    const up = Math.min(ra.top, rb.top) - CLEAR;
    const down = Math.max(ra.bottom, rb.bottom) + CLEAR;
    const upCost = Math.abs(aY - up) + Math.abs(bY - up);
    const downCost = Math.abs(aY - down) + Math.abs(bY - down);
    return upCost <= downCost ? up : down;
  }

  // The same for a vertical travel lane between side-by-side boxes.
  function verticalLane(ra, rb, aX, bX) {
    if (ra.right < rb.left) return (ra.right + rb.left) / 2;
    if (rb.right < ra.left) return (rb.right + ra.left) / 2;
    const left = Math.min(ra.left, rb.left) - CLEAR;
    const right = Math.max(ra.right, rb.right) + CLEAR;
    const leftCost = Math.abs(aX - left) + Math.abs(bX - left);
    const rightCost = Math.abs(aX - right) + Math.abs(bX - right);
    return leftCost <= rightCost ? left : right;
  }

  // Does a horizontal leg at height y between x1 and x2 pass through the
  // box's interior?
  function cutsH(y, x1, x2, rect) {
    return (
      y > rect.top &&
      y < rect.bottom &&
      Math.min(x1, x2) < rect.right &&
      Math.max(x1, x2) > rect.left
    );
  }

  // Both exits are horizontal. A side whose other end lies behind it
  // first leaves outward by a stub; then the route turns through a lane
  // that clears the boxes, or a plain jog when the leg cannot touch one.
  function outwardH(a, b, aBack, bBack) {
    const a1 = stub(a);
    const b1 = stub(b);
    if (aBack && bBack) {
      const lane = horizontalLane(a.rect, b.rect, a.y, b.y);
      return [a, a1, { x: a1.x, y: lane }, { x: b1.x, y: lane }, b1, b];
    }
    if (aBack) {
      // Only the source turns back: after its stub a vertical jog reaches
      // the entry side directly, unless that leg would cross the source
      // box at its own height - then the clear lane detours around it.
      if (b.y > a.rect.top && b.y < a.rect.bottom) {
        const lane = horizontalLane(a.rect, b.rect, a.y, b.y);
        return [a, a1, { x: a1.x, y: lane }, { x: b1.x, y: lane }, b1, b];
      }
      return [a, a1, { x: a1.x, y: b.y }, b];
    }
    // bBack only: the wire must reach the far side of the target. When
    // a's height is inside the target's span the straight leg would
    // cross it, so the route goes around through the lane.
    if (a.y > b.rect.top && a.y < b.rect.bottom) {
      const lane = horizontalLane(a.rect, b.rect, a.y, b.y);
      return [a, a1, { x: a1.x, y: lane }, { x: b1.x, y: lane }, b1, b];
    }
    return [a, { x: b1.x, y: a.y }, b1, b];
  }

  // The vertical-axis mirror of outwardH.
  function outwardV(a, b, aBack, bBack) {
    const a1 = stub(a);
    const b1 = stub(b);
    if (aBack && bBack) {
      const lane = verticalLane(a.rect, b.rect, a.x, b.x);
      return [a, a1, { x: lane, y: a1.y }, { x: lane, y: b1.y }, b1, b];
    }
    if (aBack) {
      // The horizontal jog back to b's column would cross the source when
      // that column is inside it; the lane detours around instead.
      if (b.x > a.rect.left && b.x < a.rect.right) {
        const lane = verticalLane(a.rect, b.rect, a.x, b.x);
        return [a, a1, { x: lane, y: a1.y }, { x: lane, y: b1.y }, b1, b];
      }
      return [a, a1, { x: b.x, y: a1.y }, b];
    }
    if (a.x > b.rect.left && a.x < b.rect.right) {
      const lane = verticalLane(a.rect, b.rect, a.x, b.x);
      return [a, a1, { x: lane, y: a1.y }, { x: lane, y: b1.y }, b1, b];
    }
    return [a, { x: a.x, y: b1.y }, b1, b];
  }

  // a exits horizontally, b is entered along a vertical side: after the
  // stubs the join is a vertical jog then a horizontal leg at b1's
  // height, which is already outside the target.
  function outwardHV(a, b) {
    const a1 = stub(a);
    const b1 = stub(b);
    if (!cutsH(b1.y, a1.x, b1.x, a.rect)) {
      return [a, a1, { x: a1.x, y: b1.y }, b1, b];
    }
    // The leg at b1's height would cross the source: move it to a lane
    // above or below both boxes on b1's side of the target.
    const lane = b1.y < b.rect.top
      ? Math.min(a.rect.top, b.rect.top) - CLEAR
      : Math.max(a.rect.bottom, b.rect.bottom) + CLEAR;
    return [a, a1, { x: a1.x, y: lane }, { x: b.x, y: lane }, b1, b];
  }

  // The mirror of outwardHV: a exits vertically, b horizontally.
  function outwardVH(a, b) {
    const a1 = stub(a);
    const b1 = stub(b);
    if (!cutsH(a1.y, a1.x, b1.x, b.rect)) {
      return [a, a1, { x: b1.x, y: a1.y }, b1, b];
    }
    // The leg at the stub's height would cross the target: keep travelling
    // on a's axis past both boxes and turn there instead.
    const y = a.dir > 0
      ? Math.max(a.rect.bottom, b.rect.bottom) + CLEAR
      : Math.min(a.rect.top, b.rect.top) - CLEAR;
    return [a, { x: a.x, y }, { x: b1.x, y }, b1, b];
  }

  function points(a, b, route, bend) {
    const t = bend === undefined ? 0.5 : bend;
    if (route === "straight") return [a, b];
    const aBack = behind(a, b);
    const bBack = behind(b, a);
    if (a.axis === "h" && b.axis === "h") {
      if (aBack || bBack) return outwardH(a, b, aBack, bBack);
      if (Math.abs(a.y - b.y) < 1) return [a, b];
      const mx = a.x + (b.x - a.x) * t;
      return [a, { x: mx, y: a.y }, { x: mx, y: b.y }, b];
    }
    if (a.axis === "v" && b.axis === "v") {
      if (aBack || bBack) return outwardV(a, b, aBack, bBack);
      if (Math.abs(a.x - b.x) < 1) return [a, b];
      const my = a.y + (b.y - a.y) * t;
      return [a, { x: a.x, y: my }, { x: b.x, y: my }, b];
    }
    if (!aBack && !bBack) {
      if (a.axis === "h") return [a, { x: b.x, y: a.y }, b];
      return [a, { x: a.x, y: b.y }, b];
    }
    if (a.axis === "h") return outwardHV(a, b);
    return outwardVH(a, b);
  }

  // Shift and bend move an anchor or a turn by a fraction of a side or a
  // span; outside their documented ranges the geometry is silently wrong,
  // so a bad value fails loudly instead of drawing a misplaced arrow.
  function range(label, value, min, max) {
    if (value === undefined) return undefined;
    if (
      typeof value !== "number" ||
      !isFinite(value) ||
      value < min ||
      value > max
    ) {
      throw new Error(
        `diagram: ${label} must be a number between ${min} and ${max}, ` +
          `got ${JSON.stringify(value)}`,
      );
    }
    return value;
  }

  function draw(list) {
    const body = document.body;
    const origin = body.getBoundingClientRect();
    const svg = el("svg", { class: "wires" });
    body.appendChild(svg);
    const defs = el("defs", {}, svg);
    for (const [name, color] of Object.entries(COLORS)) {
      const m = el(
        "marker",
        {
          id: "head-" + name,
          viewBox: "0 0 10 10",
          refX: "9",
          refY: "5",
          markerWidth: "7",
          markerHeight: "7",
          orient: "auto-start-reverse",
        },
        defs,
      );
      el("path", { d: "M0,0 L10,5 L0,10 z", fill: color }, m);
    }
    for (const w of list) {
      const from = document.querySelector(w.from);
      const to = document.querySelector(w.to);
      if (!from || !to) {
        throw new Error("diagram: no element for " + (from ? w.to : w.from));
      }
      const color = COLORS[w.color || "blue"] || w.color;
      const a = anchor(
        from.getBoundingClientRect(),
        w.fromSide || "right",
        range("fromShift", w.fromShift, -0.5, 0.5),
        origin,
      );
      const b = anchor(
        to.getBoundingClientRect(),
        w.toSide || "left",
        range("toShift", w.toShift, -0.5, 0.5),
        origin,
      );
      // Leave a hair of room so the arrowhead does not sit on the border.
      const gap = 3;
      if (b.axis === "h") b.x -= gap * -b.dir;
      else b.y -= gap * -b.dir;
      const pts = points(a, b, w.route, range("bend", w.bend, 0, 1));
      const d = pts.map((p, i) => (i ? "L" : "M") + p.x.toFixed(1) + "," + p.y.toFixed(1)).join(" ");
      const attrs = {
        d,
        fill: "none",
        stroke: color,
        "stroke-width": w.width || "2",
        "stroke-linejoin": "round",
        "marker-end": "url(#head-" + (w.color || "blue") + ")",
      };
      if (w.both) attrs["marker-start"] = attrs["marker-end"];
      if (w.dash) attrs["stroke-dasharray"] = "6 5";
      el("path", attrs, svg);
      if (w.label) {
        let best = 0;
        let len = -1;
        for (let i = 0; i + 1 < pts.length; i++) {
          const l = Math.hypot(pts[i + 1].x - pts[i].x, pts[i + 1].y - pts[i].y);
          if (l > len) {
            len = l;
            best = i;
          }
        }
        const p = pts[best];
        const q = pts[best + 1];
        const [dx, dy] = w.labelShift || [0, 0];
        const t = el(
          "text",
          {
            x: ((p.x + q.x) / 2 + dx).toFixed(1),
            y: ((p.y + q.y) / 2 + dy - 5).toFixed(1),
            fill: color,
            "text-anchor": "middle",
            stroke: "#ffffff",
            "stroke-width": "4",
            "paint-order": "stroke",
          },
          svg,
        );
        t.textContent = w.label;
      }
    }
  }

  function settle(list) {
    try {
      if (list && list.length) draw(list);
      const h = Math.ceil(document.body.getBoundingClientRect().height);
      document.documentElement.setAttribute("data-height", String(h));
    } catch (err) {
      document.documentElement.setAttribute(
        "data-diagram-error",
        String((err && err.message) || err),
      );
    }
  }

  window.wires = function (list) {
    const run = () => settle(list);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(run);
    else window.addEventListener("load", run);
  };
})();
