(function () {
  const data = window.PERLEARN_CHILDREN;
  if (!data || !data.children) {
    document.getElementById("narrative").textContent = "No trajectory data. Run build_demo_site.py.";
    return;
  }

  const picker = document.getElementById("child-picker");
  const slider = document.getElementById("week-slider");
  const canvas = document.getElementById("mastery-chart");
  const ctx = canvas.getContext("2d");
  const timeline = document.getElementById("timeline");

  let childId = data.default_child || Object.keys(data.children)[0];
  let week = 1;
  let timer = null;

  const METHOD_COLOR = {
    worked_example: "#1b7a5a",
    problem_first: "#9a4b1f",
    visual: "#2f6fed",
    story_analogy: "#7a5af8",
  };

  function child() {
    return data.children[childId];
  }

  function buildPicker() {
    picker.innerHTML = "";
    Object.keys(data.children).forEach((id) => {
      const c = data.children[id];
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "child-chip" + (id === childId ? " active" : "");
      btn.textContent = c.display_name;
      btn.addEventListener("click", () => {
        childId = id;
        week = 1;
        stopPlay();
        buildPicker();
        render();
      });
      picker.appendChild(btn);
    });
  }

  function stopPlay() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    document.getElementById("btn-play").textContent = "Play weeks";
  }

  function render() {
    const c = child();
    const sessions = c.sessions;
    slider.max = String(sessions.length);
    slider.value = String(week);
    const s = sessions[week - 1];

    document.getElementById("week-label").textContent = s.week_label;
    document.getElementById("child-name").textContent =
      c.display_name + " · " + c.skill_label;
    document.getElementById("child-blurb").textContent = c.blurb;
    document.getElementById("method-now").textContent = s.method_plain;
    document.getElementById("mastery-now").textContent =
      Math.round(s.mastery_after * 100) + "%";
    document.getElementById("delay-now").textContent =
      Math.round(s.delayed_score * 100) + "%";
    document.getElementById("narrative").textContent = s.narrative;
    document.getElementById("final-summary").textContent = c.final_summary;

    timeline.innerHTML = "";
    sessions.forEach((beat, i) => {
      const el = document.createElement("button");
      el.type = "button";
      el.className = "time-bead" + (i + 1 === week ? " active" : "");
      el.style.borderColor = METHOD_COLOR[beat.method] || "#12201a";
      el.title = beat.week_label + ": " + beat.method_plain;
      el.innerHTML =
        "<strong>" +
        beat.session +
        "</strong><span>" +
        beat.method.replaceAll("_", " ").split(" ")[0] +
        "</span>";
      el.addEventListener("click", () => {
        week = i + 1;
        stopPlay();
        render();
      });
      timeline.appendChild(el);
    });

    drawChart(sessions, week);
  }

  function drawChart(sessions, activeWeek) {
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || 920;
    const cssH = 280;
    canvas.width = Math.floor(cssW * dpr);
    canvas.height = Math.floor(cssH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    const pad = { l: 44, r: 18, t: 24, b: 36 };
    const w = cssW - pad.l - pad.r;
    const h = cssH - pad.t - pad.b;
    const n = sessions.length;

    function x(i) {
      return pad.l + (n === 1 ? w / 2 : (i / (n - 1)) * w);
    }
    function y(v) {
      return pad.t + (1 - v) * h;
    }

    // grid
    ctx.strokeStyle = "rgba(18,32,26,0.08)";
    ctx.lineWidth = 1;
    [0.25, 0.5, 0.75].forEach((v) => {
      ctx.beginPath();
      ctx.moveTo(pad.l, y(v));
      ctx.lineTo(pad.l + w, y(v));
      ctx.stroke();
      ctx.fillStyle = "rgba(18,32,26,0.45)";
      ctx.font = "12px Manrope, sans-serif";
      ctx.fillText(Math.round(v * 100) + "%", 8, y(v) + 4);
    });

    // mastery line
    ctx.beginPath();
    sessions.forEach((s, i) => {
      const px = x(i);
      const py = y(s.mastery_after);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.strokeStyle = "#12201a";
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // method dots
    sessions.forEach((s, i) => {
      const px = x(i);
      const py = y(s.mastery_after);
      ctx.beginPath();
      ctx.arc(px, py, i + 1 === activeWeek ? 8 : 5.5, 0, Math.PI * 2);
      ctx.fillStyle = METHOD_COLOR[s.method] || "#12201a";
      ctx.fill();
      if (i + 1 === activeWeek) {
        ctx.lineWidth = 3;
        ctx.strokeStyle = "#fff";
        ctx.stroke();
      }
    });

    // switch markers
    sessions.forEach((s, i) => {
      if (i === 0) return;
      if (s.method !== sessions[i - 1].method) {
        const px = x(i);
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = "rgba(154,75,31,0.55)";
        ctx.beginPath();
        ctx.moveTo(px, pad.t);
        ctx.lineTo(px, pad.t + h);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = "#9a4b1f";
        ctx.font = "600 11px Manrope, sans-serif";
        ctx.fillText("switch", px + 4, pad.t + 12);
      }
    });

    ctx.fillStyle = "rgba(18,32,26,0.55)";
    ctx.font = "12px Manrope, sans-serif";
    ctx.fillText("Mastery over weeks (dot colour = teaching method)", pad.l, cssH - 10);
  }

  slider.addEventListener("input", () => {
    week = Number(slider.value);
    stopPlay();
    render();
  });
  document.getElementById("btn-prev").addEventListener("click", () => {
    week = Math.max(1, week - 1);
    stopPlay();
    render();
  });
  document.getElementById("btn-next").addEventListener("click", () => {
    week = Math.min(child().sessions.length, week + 1);
    stopPlay();
    render();
  });
  document.getElementById("btn-play").addEventListener("click", () => {
    if (timer) {
      stopPlay();
      return;
    }
    document.getElementById("btn-play").textContent = "Pause";
    if (week >= child().sessions.length) week = 1;
    render();
    timer = setInterval(() => {
      if (week >= child().sessions.length) {
        stopPlay();
        return;
      }
      week += 1;
      render();
    }, 900);
  });

  window.addEventListener("resize", () => render());
  buildPicker();
  render();
})();
